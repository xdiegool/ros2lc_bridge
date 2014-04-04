#! /usr/bin/env python

PROJ_NAME = 'generator'       # TODO: Is there an api for this?

import roslib; roslib.load_manifest(PROJ_NAME)
from rosgraph.masterapi import Master
import re
from os.path import basename
from os.path import splitext
import os
import sys
import stat
import subprocess as sp
from optparse import OptionParser
from time import strftime
from tempfile import mkstemp
import platform
from tcol import *
from config_file import *
import shutil


SLASHSUB            = 'S__'
SRV_PAR_SUFFIX      = '_PAR'
SRV_RET_SUFFIX      = '_RET'
CONVERSION_FILENAME = 'conv.cpp'
CLIENT_FILENAME     = 'client.h'
CONFIG_FILENAME     = 'conf.h'


## Boilerplate content to output.
#################################

conf_content = '''
#ifndef {pkg_name}_CONF_C
#define {pkg_name}_CONF_C
#define PKG_NAME "{pkg_name}"
#define PORT     ({port})
#define SLASHSUB "{slash_substitute}"
//TOPICS_IN   = {topics_in}
//TOPICS_OUT  = {topics_out}
//TOPIC_TYPES = {topic_types}
//SERVICES    = {services}
//STATIC_CONNS = {static_connections}
//CONV        = {conversions}

#endif
'''

client_file_begin = '''
#ifndef {pkg_name}_CLIENT_C
#define {pkg_name}_CLIENT_C

#include "ros/ros.h"

#include <boost/thread/mutex.hpp>
#include <boost/thread/locks.hpp>

extern "C" {{
#include <labcomm.h>

#include "proto.h"
#include "lc_types.h"

void alloc_array(void **, size_t, size_t);
}}

'''

client_class_include = '''
#include "{topic_type}.h"
'''

client_lc_callback_def = '''
void {topic_name}_lc_callback(lc_types_{topic_name} *sample, void *ctx);
'''

client_service_callback_def = '''
static void handle_srv_{lc_name}(lc_types_{lc_par_type} *s, void* v);
'''


client_class_begin = '''
class client {
	int sock;
	ros::NodeHandle &n;
	struct labcomm_decoder *dec;
	struct labcomm_encoder *enc;
	boost::mutex enc_lock;

public:
'''

client_ros_subscriber_members = '''
	ros::Subscriber {topic_name}Sub;
	void {topic_name}_ros_callback(const {topic_type}::ConstPtr& msg);
'''

client_ros_service_members = '''
	void call_srv_{srv_name}(lc_types_{lc_par_type} *s);
'''

client_ros_publisher_member = '''
	ros::Publisher {topic_name}Pub;
'''

client_functions = '''
	client(int sock, ros::NodeHandle &n);
	~client()
	{
		labcomm_decoder_free(dec);
		labcomm_encoder_free(enc);
	}

	void run();
	void handle_subscribe(proto_subscribe *subs);
	void handle_publish(proto_publish *pub);

    void setup_exports() {
'''

client_subscribe_reg = '''
		{topic_name}Sub = n.subscribe("{ros_topic_name}", 1, &client::{topic_name}_ros_callback, this);
		labcomm_encoder_register_lc_types_{topic_name}(enc);
'''

setup_imports_fn_begin = '''
	void setup_imports() {
'''

setup_imports_fn = '''
		{topic_name}Pub = n.advertise<{topic_type}>("{topic}", 10);
		labcomm_decoder_register_lc_types_{topic_name}(dec, {topic_name}_lc_callback, this);
'''

subscriber_cb_fn_begin = '''
void client::{topic_name}_ros_callback(const {topic_type}::ConstPtr& msg)
{{
	// Convert received ROS data.
	lc_types_{topic_name} conv;
'''

lc2ros_cb_fn_begin = '''
void {topic_name}_lc_callback(lc_types_{topic_name} *sample, void *ctx)
{{
\t{cpp_topic_type} msg;
'''

# TODO: Check if all types of arrays work properly.
lc2ros_convert_array = '''
	msg.{name}.assign(sample->{name}.n_0, sample->{name}.a);
'''
lc2ros_convert_array_start = '''
	msg.{name}.clear();
	for (int i = 0; i < sample->{name}.n_0; i++) {{
'''

lc2ros_convert_array_str = '''
		msg.{name}.push_back(sample->{name}.a[i]);
'''

lc2ros_cb_fn_end = '''
	((client *) ctx)->{topic_name}Pub.publish(msg);
}}'''

ros2lc_convert_array_start = '''
	conv.{name}.n_0 = msg->{name}.size();
	alloc_array((void **)&conv.{name}.a, conv.{name}.n_0,
				(msg->{name}[0]));
	for (size_t i = 0; i < msg->{name}.size(); i++) {{
'''

ros2lc_convert_string_array = '''
		conv.{name}.a[i] = strdup(msg->{name}[i].c_str());
'''

ros2lc_convert_string = '''
	conv.{name} = strdup(msg->{name}.c_str());
'''

ros2lc_convert_time_duration_array = '''
		conv.{name}.a[i].secs = msg->{name}[i].sec;
		conv.{name}.a[i].nsecs = msg->{name}[i].nsec;
'''

ros2lc_convert_time_duration = '''
	conv.{name}.secs = msg->{name}.sec;
	conv.{name}.nsecs = msg->{name}.nsec;
'''

convert_array_end = '\t\t}}\n'

service_call_func = '''
static void handle_srv_{lc_name}(lc_types_{lc_par_type} *s, void* v)
{{
	client *c = (client *) v;
	boost::thread call_service(&client::call_srv_{lc_name}, c, s);
}}
'''

end_fn = '}'

class_end = '''
};

#endif
'''

ros_prim = {
    'byte'     : 'byte',    # Deprecated alias for int8.
    'char'     : 'short',   # Deprecated alias for uint8.
                            # Bad for incoming messages.
    'bool'     : 'boolean',
    'int8'     : 'byte',
    'uint8'    : 'short',   # Bad for incoming messages.
    'int16'    : 'short',
    'uint16'   : 'int',     # Bad for incoming messages.
    'int32'    : 'int',
    'uint32'   : 'long',    # Bad for incoming messages.
    'int64'    : 'long',
    'uint64'   : 'long',    # Bad for outgoing messages.
    'float32'  : 'float',
    'float64'  : 'double',
    'string'   : 'string',
    'time'     : 'time',    # Handled as typedef.
    'duration' : 'duration' # Handled as typedef.
    }

re_array_suffix = re.compile(r'\[[0-9]*\]')
re_indent = re.compile(r'^(.+)$', re.MULTILINE)
# Precompiled regexps to be used on all .msg-files.
cleanup = []
# Nested members are shown indented.
cleanup.append(re.compile(r'^\s+[a-zA-Z]*.*$', re.MULTILINE))
# Treat aliases as distinct types for now.
cleanup.append(re.compile(r'^\[.*\]:$', re.MULTILINE))
cleanup.append(re.compile(r'#.*$', re.MULTILINE)) # Comments.
cleanup.append(re.compile(r'^\s+', re.MULTILINE)) # Leading whitespace.
cleanup.append(re.compile(r'\s+$', re.MULTILINE)) # Trailing whitespace.
cleanup.append(re.compile(r'\s{2,}', re.MULTILINE)) # Dup whitespace.


class GeneratorException(Exception):
    """Used to distinguish our exceptions from general python runtime errors."""
    pass


def msg2id(name):
    """Used to translate ROS path-style identifiers to something valid in labcomm."""
    # TODO: Introduce optional remapping?
    return name.replace('/', SLASHSUB)


def get_types():
    """Query the master about topics and their types."""
    master = Master('/' + PROJ_NAME)
    ttdict = dict(master.getTopicTypes())
    return ttdict

defs_cache = {}

def get_def(tnam):
    """Invoke the ros utility which returns the message type definitions."""
    if tnam in defs_cache:
        return defs_cache[tnam]

    ok, out = sh('rosmsg show %s' % tnam)
    for r in cleanup:
        out = r.sub('', out)
    defs_cache[tnam] = out.strip()
    return defs_cache[tnam]


def get_srv_def(snam):
    """Invoke a ROS utility to get a service type definition."""
    ok, out = sh('rossrv show %s' % snam)
    for r in cleanup:
        out = r.sub('', out)
    b = out.index('---')
    params  = out[:b].strip()
    retvals = out[b+3:].strip()
    return (params, retvals)


def get_nested(defn):
    """Find the nested types used in a message type definition."""
    nested = set()
    for line in defn.split('\n'):
        t = re_array_suffix.sub('', line.split(' ')[0])
        if t and t not in ros_prim: # '' is not complex...
            nested.add(t)
    return nested


def convert_msg_body(defn, nam, f):
    f.write('typedef struct {\n')
    for line in defn.split('\n'):        # Iterate over members.
        typ, rest = line.split(' ', 2)      # Might not be scalar.
        styp = re_array_suffix.sub('', typ) # Most def. scalar.
        indices = re_array_suffix.findall(typ)
        lc_type = ros_prim.get(styp)
        if not lc_type:
            lc_type = msg2id(styp)
        name_val = rest.split('=', 2)
        lc_name = name_val[0].strip();
        if indices:
            # ROS doesn't have multidim. arrays (?)
            index = indices[0]
            n = index[1:-1]
            lc_n = n if n else '_'
            lc_name += '[%s]' % lc_n
        f.write('        %s %s;' % (lc_type, lc_name))
        if len(name_val) > 1:  # Definition of a constant.
            f.write(' /* = %s */' % name_val[1])
        f.write('\n')
    f.write('} %s;\n\n' % msg2id(nam));


def convert_def(nam, defn, f):
    """Convert a ROS message definition to an approximately equivalent labcomm typedef."""
    convert_msg_body(defn, nam, f);


def convert_service_def(nam, defn, f):
    pnam = nam + SRV_PAR_SUFFIX
    rnam = nam + SRV_RET_SUFFIX
    if defn[0]:
        convert_msg_body(defn[0], '%s' % pnam, f);
    else:
        f.write('typedef dummy %s;\n\n' % msg2id(pnam))

    if defn[1]:
        convert_msg_body(defn[1], '%s' % rnam, f);
    else:
        f.write('typedef dummy %s;\n\n' % msg2id(rnam))


def longest_id(itr):
    maxlen = 0
    for name in itr:
        maxlen = max(maxlen, len(msg2id(name)))
    return maxlen


def write_lc(topics, defs, services, service_defs, f):
    """Create a labcomm file for the topics in the system."""
    # http://www.ros.org/wiki/msg
    # http://wiki.cs.lth.se/moin/LabCommProtocolBNF
    f.write('/* Generated %s on \'%s\' */\n' %
            (strftime('%Y-%m-%d %H:%M'), platform.node()))
    f.write('''
typedef struct { int secs; int nsecs; } time;        /* ROS primitive */
typedef struct { int secs; int nsecs; } duration;    /* ROS primitive */
typedef struct { byte __dummy__; } dummy;                                  /* TODO: void cannot be typedef:ed */
''')

    # Message types
    f.write('\n\n/* Message types: */\n')
    for typ, defn in defs.iteritems():
        convert_def(typ, defn, f) # Write lc definitions.

    # Topics
    f.write('\n/* Topics: */\n')
    w = longest_id(topics.itervalues())
    for (topic, typ) in topics.iteritems():
        f.write('sample %s %s;\n' % (msg2id(typ).ljust(w), msg2id(topic)))

    # Services types
    f.write('\n\n/* Service types: */\n')
    for (typ, defn) in service_defs.iteritems():
        convert_service_def(typ, defn, f)
    # Services
    f.write('\n/* Services: */\n')
    w = longest_id(services.itervalues()) + max(len(SRV_PAR_SUFFIX),
                                                len(SRV_RET_SUFFIX))
    for (service, typ) in services.iteritems():
        atyp = typ + SRV_PAR_SUFFIX
        rtyp = typ + SRV_RET_SUFFIX
        anam = service + SRV_PAR_SUFFIX
        rnam = service + SRV_RET_SUFFIX
        f.write('sample %s %s;\n' % (msg2id(atyp).ljust(w), msg2id(anam)))
        f.write('sample %s %s;\n' % (msg2id(rtyp).ljust(w), msg2id(rnam)))


def sh(cmd, crit=True, echo=True, pr=True, col=normal, ocol=blue, ecol=red):
    """Run a shell script in the specified way and make sure the user is aware of any errors."""
    if echo:
        print(col(cmd))
    p = sp.Popen(cmd, stdout=sp.PIPE, stderr=sp.PIPE, shell=True)
    out, err = p.communicate()
    if pr:
        # sys.stdout.write(ocol(re_indent.sub(r'\t\1', out)))
        # sys.stderr.write(ecol(re_indent.sub(r'\t\1', err)))
        sys.stdout.write(ocol(out))
        sys.stderr.write(ecol(err))
    ok = not p.returncode and not err
    if not ok and crit:
        if err and pr:          # Program printed its error properly.
            raise GeneratorException("")
        else:                   # It did not.
            raise GeneratorException("Command failed: '%s': '%s'" % (cmd, err))
    return (ok, out)


def create_pkg(ws, name, deps, force, lc_file, conf_file, conv_file,
               client_file, mlc, mpy):
    """Create ROS package in the first dicectory in $ROS_PACKAGE_PATH, or /tmp/, unless explicitly specified."""
    if not ws:
        pkg_path = os.environ.get('ROS_PACKAGE_PATH')
        for path in pkg_path.split(':'):
            if 'home' in path.split(os.sep):
                ws = path
                break
    if not ws:
        ws = '/tmp'
        print(orange("Defaulting to /tmp as workspace."))

    d = os.path.join(ws, name)
    if force and os.path.exists(d):
        shutil.rmtree(d)

    depstr = ' '.join(['roslib', 'roscpp'] + list(deps))
    sh('cd %s && roscreate-pkg %s %s' % (ws, name, depstr))
    try:
        lcdir = os.path.join(d, 'lc')
        srcdir = os.path.join(d, 'src')
        skeldir = os.path.join(os.path.dirname(__file__), '..', '..', 'skel')
        skelcodedir = os.path.join(skeldir, 'src')
        skeltypesdir = os.path.join(skeldir, 'lc')

        # Move created type definitions to generated package.
        os.mkdir(lcdir)
        os.rename(lc_file, os.path.join(lcdir, 'lc_types.lc'))
        # Copy skeleton code to package.
        for f in os.listdir(skelcodedir):
            shutil.copy2(os.path.join(skelcodedir, f), srcdir);
        # Copy types for bridge commands to package.
        for f in os.listdir(os.path.join(skeldir, 'lc')):
            shutil.copy2(os.path.join(skeltypesdir, f), lcdir);
        # Move generated configuration code to package.
        os.rename(conf_file, os.path.join(srcdir, CONFIG_FILENAME))
        # Move generated conversion code to package.
        os.rename(conv_file, os.path.join(srcdir, CONVERSION_FILENAME))
        # Move generated client definition to package.
        os.rename(client_file, os.path.join(srcdir, CLIENT_FILENAME))

        # Make sure LabComm library env exists.
        lclibpath = os.environ.get('LABCOMM')
        if not lclibpath:
            raise GeneratorException('Env. $LABCOMM not set, won\'t be able to'
                                     ' comile node. (Should be set to LabComm'
                                     ' C library path.)')

        lcc = os.environ.get('LABCOMMC')
        if not lcc:
            raise GeneratorException("Env. $LABCOMMC not set, can't compile types."
                                     " (Should be path to labcomm compiler jar-file.)")
        for lc in mlc:
            shutil.copy(lc, lcdir)
        # Compile LabComm files.
        for f in os.listdir(lcdir):
            name = os.path.splitext(f)[0]
            sh('java -jar {jar} -C --c={dest}.c --h={dest}.h {src}.lc'.format(
                    jar=lcc,
                    dest=os.path.join(srcdir, name),
                    src=os.path.join(lcdir, name)))

        # Copy user stuff for manual conversion.
        for py in mpy:
            shutil.copy(py, srcdir)

        # TODO: Ugly. Fix better way...
        with open('%s/CMakeLists.txt' % d, 'a') as buildfile:
            buildfile.write('''
rosbuild_add_executable(main
    src/hack.c
    src/lc_types.c
    src/proto.c
    src/client.cpp
    src/bridge.cpp
)
target_link_libraries(main {lc_lib})
include_directories({lc_inc})'''.format(lc_lib=lclibpath + '/liblabcomm.a',
                                        lc_inc=lclibpath))

        # Fix permissions
        # os.chmod(('%s/' + CONFIG_FILENAME) % srcdir,
        #          stat.S_IRUSR | stat.S_IWUSR |
        #          stat.S_IRGRP | stat.S_IWGRP)
        # os.chmod('%s/lc_types.py' % srcdir,
        #          stat.S_IRUSR |
        #          stat.S_IRGRP)
    except Exception as e:
        # sh('rm -fr ' + d)       # Clean up
        raise e
    return d


def write_conf(f, bname, port, topics_in, topics_out, topics, services,
               static_conns, conversions):
    convs = [conv.tuple_repr() for conv in conversions]

    f.write(conf_content.format(pkg_name=bname,
                                topics_in=topics_in,
                                topics_out=topics_out,
                                topic_types=topics,
                                port=port,
                                slash_substitute=SLASHSUB,
                                services=services,
                                static_connections=static_conns,
                                conversions=convs))

def write_conv(clientf, convf, pkg_name, topics_in, topics_out,
               topics_types, services, service_defs, static_conns, conversions):
    '''Writes the definition of the client class as well as conversion code.

    The client class handles subscribing to and publishing on topics as well as
    converting received messages/samples and sending them out the opposite way
    (i.e.  ROS->LC or LC->ROS).

    :param clientf: the file to write the client definition to.
    :param convf: the file to write converision code to.
    :param pkg_name: string with the name of the package.
    :param topics_in: a list topics imported into the ROS system.
    :param topics_out: a list topics exported from the ROS system.
    :param topics_types: a dict of topic names => topic types.
    :param services: a list of services that should be exported.
    :param service_defs: a dict of a service=>type mappings
    :param static_conns: a list of static connections(probably obsolete in C++)
    :param conversions: a list of conversions specified by the user (obsolete in C++)
    '''
    # Write define stuff
    clientf.write(client_file_begin.format(pkg_name=pkg_name))

    # Write one function declaration (LC callback) per publisher
    for topic in topics_in:
        topic_name = msg2id(topic)
        clientf.write(client_lc_callback_def.format(topic_name=topic_name))

    # Write one include per msg needed.
    for topic in topics_out + topics_in:
        topic_type = topics_types[topic]
        clientf.write(client_class_include.format(topic_type=topic_type))

    # Write class definition
    clientf.write(client_class_begin)

    # Write class members (ROS callback) for each subscriber.
    for topic in topics_out:
        topic_name = msg2id(topic)
        topic_type_cpp = topics_types[topic].replace('/', '::')
        clientf.write(client_ros_subscriber_members.format(topic_name=topic_name,
                                                       topic_type=topic_type_cpp))

    for topic in topics_in:
        topic_name = msg2id(topic)
        topic_type = topics_types[topic].replace('/', '::')
        clientf.write(client_ros_publisher_member.format(topic_name=topic_name,
                                                         topic_type=topic_type))

    # Write setup in constructor.
    clientf.write(client_functions)
    for topic in topics_out:
        clientf.write(client_subscribe_reg.format(topic_name=msg2id(topic),
                                                  ros_topic_name=topic))
    clientf.write('\t' + end_fn)

    clientf.write(setup_imports_fn_begin)
    for topic in topics_in:
        topic_name = msg2id(topic)
        # Get corresponding C++ type.
        topic_type = topics_types[topic].replace('/', '::')
        clientf.write(setup_imports_fn.format(topic_name=topic_name,
                                              topic_type=topic_type,
                                              topic=topic))
    clientf.write('\t' + end_fn)

    clientf.write(class_end)

    # Write subscriber callbacks that converts to LabComm samples.
    for topic in topics_out:
        topic_name = msg2id(topic)
        topic_type = topics_types[topic]
        topic_type_cpp = topic_type.replace('/', '::')
        convf.write(subscriber_cb_fn_begin.format(topic_name=topic_name,
                                                  topic_type=topic_type_cpp))
        # Write conversion from ROS to LabComm.
        free_list = write_conversion(convf, topic, get_def(topic_type))
        write_send(convf, topic)
        write_free(convf, free_list)
        convf.write(end_fn)

    # Write LabComm callbacks that converts to ROS msgs.
    for topic in topics_in:
        definition = get_def(topics_types[topic])
        topic_type_cpp = topics_types[topic].replace('/', '::')
        convf.write(lc2ros_cb_fn_begin.format(topic_name=msg2id(topic),
                                              cpp_topic_type=topic_type_cpp))
        lc2ros_conversion(convf, topic, definition)
        convf.write(lc2ros_cb_fn_end.format(topic_name=msg2id(topic)))


# TODO: Practically identical to write_conversion below. Merge these.
def lc2ros_conversion(f, topic, definition, prefix = ''):

    def write_string(f, full_name, in_array = False):
        '''Helper function for writing conversion code for strings.'''
        if in_array: # string in array
            res = lc2ros_convert_array_str
        else: # nested string
            res = '\tmsg.{name} = sample->{name};\n'
        f.write(res.format(name=full_name))

    def write_time_duration(f, full_name, in_array = False):
        '''Helper function for writing conversion code for Time or Duration
        (which are primitive types in ROS msgs).
        '''
        if in_array:
            res = ('\t\tmsg.{name}[i].sec = sample->{name}.a[i].secs;\n'
                   '\t\tmsg.{name}[i].nsec = sample->{name}.a[i].nsecs;\n')
        else:
            res = ('\tmsg.{name}.sec = sample->{name}.secs;\n'
                   '\tmsg.{name}.nsec = sample->{name}.nsecs;\n')
        f.write(res.format(name=full_name))

    def write_array(f, full_name, typ):
        '''Helper function for writing conversion code for arrays.'''
        # free_list.append('conv.{name}.a'.format(name=full_name))
        # res = ''
        if typ == 'string':
            f.write(lc2ros_convert_array_start.format(name=full_name))
            write_string(f, full_name, True)
            f.write('\t' + end_fn)
        elif typ == 'time' or typ == 'duraiton':
            f.write(lc2ros_convert_array_start.format(name=full_name))
            write_time_duration(f, full_name, True)
            f.write('\t' + end_fn)
        else:
            f.write(lc2ros_convert_array.format(name=full_name))
        # f.write(res.format(name=full_name))

    for d in definition.split('\n'):
        # Extract type info from definition.
        (typ, tail) = (lambda x: (x[0], x[1:]))(splitter.split(d))
        name = tail[0]
        if len(tail) > 1: # Skip enum
            continue
        if prefix:
            name = prefix + '.' + name
        if len(get_nested(typ)) > 0: # non-primitive type, recurse
            lc2ros_conversion(f, topic, get_def(typ), name)
        else: # primitive type
            if typ == 'string':
                write_string(f, name)
            elif '[]' in typ:
                write_array(f, name, typ.replace('[]', '').lower())
            elif typ == 'time' or typ == 'duration':
                write_time_duration(f, name)
            else: # primitive types, just copy
                res = '\tmsg.{name} = sample->{name};\n'
                f.write(res.format(name=name))


splitter = re.compile(r'[ =]')
def write_conversion(f, topic, definition, prefix = ''):
    '''Writes the conversion from ROS to LC.
    
    :param f: the file handle to write to.
    :param topic: the topic being converted.
    :param definition: the definition of the type for the topic.
    :param prefix: possible prefix to print before the name of the variable
                   (should only be used when recursively writing conversion
                   code for non-primitive types).
    '''
    free_list = []
    def write_string(f, full_name, in_array = False):
        '''Helper function for writing conversion code for strings.'''
        if in_array: # string in array
            res = ros2lc_convert_string_array
        else:
            free_list.append('conv.{name}'.format(name=full_name))
            res = ros2lc_convert_string
        f.write(res.format(name=full_name))

    def write_time_duration(f, full_name, in_array = False):
        '''Helper function for writing conversion code for Time or Duration
        (which are primitive types in ROS msgs).
        '''
        if in_array:
            res = ros2lc_convert_time_duration_array
        else:
            res = ros2lc_convert_time_duration
        f.write(res.format(name=full_name))

    def write_array(f, full_name, typ):
        '''Helper function for writing conversion code for arrays.'''
        free_list.append('conv.{name}.a'.format(name=full_name))
        f.write(ros2lc_convert_array_start.format(name=full_name))
        res = ''
        if typ == 'string':
            write_string(f, full_name, True)
            # must free strings because of strdup
            free_list.append('conv.{name}.a[i]'.format(name=full_name))
        elif typ == 'time' or typ == 'duraiton':
            write_time_duration(f, full_name, True)
        else:
            res = '\t\tconv.{name}.a[i] = msg->{name}[i];\n'
        res += convert_array_end
        f.write(res.format(name=full_name))

    for d in definition.split('\n'):
        # Extract type info from definition.
        (typ, tail) = (lambda x: (x[0], x[1:]))(splitter.split(d))
        name = tail[0]
        if prefix:
            name = prefix + '.' + name
        if len(get_nested(typ)) > 0: # non-primitive type, recurse
            free_list += write_conversion(f, topic, get_def(typ), name)
        else: # primitive type
            if typ == 'string':
                write_string(f, name)
            elif '[]' in typ:
                write_array(f, name, typ.replace('[]', '').lower())
            elif typ == 'time' or typ == 'duration':
                write_time_duration(f, name)
            else: # primitive types, just copy
                res = '\tconv.{name} = msg->{name};\n'
                f.write(res.format(name=name))

    return free_list


def write_send(f, topic):
    '''Writes the code to send the converted data.
    
    :param f: the file handle to write to.
    :param topic: the topic being converted.
    '''
    lc_topic = msg2id(topic)
    f.write(('\t// Send converted data (use boost::lock_guard for locking).\n'
             '\tboost::lock_guard<boost::mutex> enc_guard(enc_lock);\n'
             '\tlabcomm_encode_lc_types_{lc_topic}(enc, &conv);\n'
	         '\tstd::cout << "send LC" << std::endl;\n')
             .format(lc_topic=lc_topic))


def write_free(f, free_list):
    '''Writes the code to free any allocated data structures from the
    conversion code.
    
    :param f: the file handle to write to.
    :param free_list: the list of names that should be freed.
    '''
    f.write('\t// Free the allocated stuff\n')
    free_list.reverse() # free in reverse order of alloc
    for name in free_list:
        if '[i]' in name: # Detect array.
            size = name.replace('a[i]', 'n_0')
            f.write(('\tfor (int i = 0; i < {size}; i++) {{\n'
                     '\t\tfree({name});\n'
                     '\t}}\n').format(name=name,size=size))
        else:
            f.write('\tfree({name});\n'.format(name=name))


def get_srv_types():
    slist = sh('rosservice list')[1]
    services = {}
    for sname in slist.strip().split('\n'):
        stype = sh('rosservice type %s' % sname)[1]
        services[sname] = stype.strip()
    return services

srv_type_cache = {}
def get_srv_type(srv):
    if srv in srv_type_cache:
        return srv_type_cache[srv]
    typ = sh('rosservice type %s' % srv)
    if typ[0]:
        srv_type_cache[srv] = typ[1].strip()
        return srv_type_cache[srv]
    else:
        return None



def run(conf, ws, force):
    """Run the tool and put a generated package in ws."""
    cf = ConfigFile(conf)

    # topic, service with a common base class would be prettier.

    # Topics
    topics = get_types()        # name -> type
    defs = {}                   # type -> definition
    types = set(topics.itervalues())
    while types:
        t = types.pop()
        defn = get_def(t)
        defs[t] = defn
        types |= get_nested(defn) - set(defs.keys())

    # Services
    services = get_srv_types()
    service_defs = {}
    for t in services.itervalues():
        defn = get_srv_def(t)
        service_defs[t] = defn
        types |= get_nested(defn[0]) | get_nested(defn[1]) - set(defs.keys())
    # types -= set(defs.keys())
    while types:     # Services can include complex types. Resolve again.
        t = types.pop()
        defn = get_def(t)
        defs[t] = defn
        types |= get_nested(defn) - set(defs.keys())
    del types

    topics_in, topics_out = cf.assert_defined(list(topics))
    services_used = {s: services[s] for s in
                     cf.assert_defined_services(list(services))}
    topics_types = { t: topics[t] for t in topics_in + topics_out }

    # C++ configuration
    (cfd, cnam) = mkstemp('.h')
    cfil = os.fdopen(cfd, 'w')
    write_conf(cfil, cf.name, cf.port,
               topics_in, topics_out, topics_types,
               services_used, cf.static, cf.conversions)
    cfil.close()

    # C++ conversions
    (clientfd, clientnam) = mkstemp('.h')
    (convfd, convnam) = mkstemp('.cpp')
    clientfil = os.fdopen(clientfd, 'w')
    convfil = os.fdopen(convfd, 'w')
    write_conv(clientfil, convfil, cf.name,
               topics_in, topics_out, topics_types,
               services_used, service_defs, cf.static, cf.conversions)
    convfil.close()

    req_topics = {}
    for t in topics_in + topics_out:
        req_topics[t] = topics[t]

    req_services = {}
    for s in services:
        req_services[s] = services[s]

    (tfd, tnam) = mkstemp('.lc')
    tfil = os.fdopen(tfd, 'w')
    write_lc(req_topics, defs, req_services, service_defs, tfil)
    tfil.close()

    union = dict(topics.items() + services_used.items())
    deps = set()
    for dep in union.itervalues():
        deps.add(dep[:dep.index('/')])

    return create_pkg(ws, cf.name, deps, force, tnam, cnam, convnam, clientnam,
                      cf.lc_files(), cf.py_files())


if __name__ == '__main__':
    op = OptionParser()
    op.add_option('-c', '--config-file', dest='conf', default=None,
                  help='The bridge configuration file.')
    op.add_option('-w', '--workspace-path', dest='ws', default=None,
                  help='The directory in which the package will be created.')
    op.add_option('-f', '--force', action="store_true", dest="force",
                  help='Replace any existing directory in case of a name collision')
    op.add_option('-l', '--lang', dest="lang", default="python",
                  help='Specify what language the bridge should be in.')
    (opt, args) = op.parse_args(sys.argv)
    if not opt.conf:
        sys.stderr.write(red("Specify config file.\n"))
        sys.exit(1)
    try:
        run(opt.conf, opt.ws, opt.force)
    except (GeneratorException, ConfigException, IOError) as e:
        sys.stderr.write(red(e) + '\n')
    except ET.ParseError as e:
        sys.stderr.write(red("Parse error in config file '%s': %s\n" %
                             (opt.conf, e)))
