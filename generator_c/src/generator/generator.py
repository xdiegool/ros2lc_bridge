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
GENBRIDGE__FILENAME = 'gen_bridge.cpp'


## Boilerplate content to output.
#################################

cmake_add_exec_begin = '''
rosbuild_add_executable(main
    src/hack.c
    src/lc_types.c
    src/proto.c'''

cmake_custom_conv = '''
    src/{f}'''

cmake_add_exec_end = '''
    src/client.cpp
    src/bridge.cpp
)
target_link_libraries(main {lc_lib})
include_directories({lc_inc})
'''

conf_content = '''
#ifndef {pkg_name}_CONF_C
#define {pkg_name}_CONF_C

#define PKG_NAME "{pkg_name}"
#define PORT     ({port})
#define SLASHSUB "{slash_substitute}"

#endif
'''

client_file_begin = '''
#ifndef {pkg_name}_CLIENT_C
#define {pkg_name}_CLIENT_C

#include "ros/ros.h"

#include <boost/thread.hpp>
#include <boost/thread/mutex.hpp>
#include <boost/thread/locks.hpp>
#include <set>
#include <string>
#include <vector>

extern "C" {{

#include <netinet/in.h>

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
	std::set<std::string> active_topics;

public:
'''

client_ros_subscriber_members = '''
	ros::Subscriber {topic_name}Sub;
	void {topic_name}_ros_callback(const {topic_type}::ConstPtr& msg);
'''

client_ros_service_members = '''
	void call_srv_{srv_name}({cpp_type} *msg);
'''

client_ros_publisher_member = '''
	ros::Publisher {topic_name}Pub;
'''

client_functions = '''
    client(int client_sock, ros::NodeHandle &n,
            struct sockaddr_in *stat_addr = NULL,
            std::vector<std::string> *subscribe_to = NULL,
            std::vector<std::string> *publish_on = NULL);
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
	if (active_topics.find("{topic_name}") != active_topics.end()) {{
'''

subscriber_cb_fn_end = '''
	}
}
'''

lc2ros_cb_fn_begin = '''
void {topic_name}_lc_callback(lc_types_{topic_name} *sample, void *ctx)
{{
	{cpp_topic_type} msg;
'''

lc2ros_cb_fn_end = '''
	((client *) ctx)->{topic_name}Pub.publish(msg);
}}'''

service_call_func = '''
static void handle_srv_{lc_name}(lc_types_{lc_par_type} *s, void* v)
{{
	client *c = (client *) v;
	{cpp_type} *msg = new {cpp_type}();
'''

service_call_start_thread = '''
	boost::thread call_service(&client::call_srv_{lc_name}, c, msg);
}}
'''

service_call_callback_begin = '''
void client::call_srv_{lc_name}({cpp_type} *msg)
{{
'''

service_call_callback_call_srv = '''
	ros::ServiceClient client;
	client = n.serviceClient<{cpp_type}>("{srv_name}");
	if (client.call(*msg)) {{
		// TODO: convert back to LC.
		lc_types_{lc_ret_type} res;
'''

service_call_callback_end = '''
		srv_response_{lc_name}(&res);
	}} else {{
		//TODO: Fail
	}}

    delete msg;
}}
'''

service_call_respond = '''
	void srv_response_{lc_name}(lc_types_{lc_ret_type} *res)
	{{
		boost::lock_guard<boost::mutex> enc_guard(enc_lock);
		labcomm_encode_lc_types_{lc_ret_type}(enc, res);
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


srv_defs_cache = {}
def get_srv_def(snam):
    """Invoke a ROS utility to get a service type definition."""
    if snam in srv_defs_cache:
        return srv_defs_cache[snam]
    ok, out = sh('rossrv show %s' % snam)
    for r in cleanup:
        out = r.sub('', out)
    b = out.index('---')
    params  = out[:b].strip()
    retvals = out[b+3:].strip()
    srv_defs_cache[snam] = (params, retvals)
    return srv_defs_cache[snam]


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
               client_file, static_conns_file, mlc, mpy):
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
        # Move generated client definition to package.
        os.rename(static_conns_file, os.path.join(srcdir, GENBRIDGE__FILENAME))

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
        with open('%s/CMakeLists.txt' % d, 'a') as bf:
            bf.write(cmake_add_exec_begin)
            bf.write(cmake_add_exec_end.format(lc_lib=lclibpath+'/liblabcomm.a',
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

def write_conf(f, bname, port):
    '''Writes the conf.h header file.

    :param f: the file to write the defines to.
    :param bname: the name of the created package.
    :param port: the port the bridge should run on.
    '''
    f.write(conf_content.format(pkg_name=bname, port=port,
                                slash_substitute=SLASHSUB))

def write_conv(clientf, convf, pkg_name, topics_in, topics_out,
               topics_types, services, service_defs, conversions):
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

    # Write includes for service types.
    for service in services:
        clientf.write('#include "{name}.h"\n'
                      .format(name=get_srv_type(service)))

    # Write one function declaration (LC callback) per service.
    for service in services:
        lc_name = msg2id(service)
        lc_par_type = lc_name + SRV_PAR_SUFFIX
        clientf.write(client_service_callback_def.format(lc_name=lc_name,
                                                         lc_par_type=lc_par_type))

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
    for service in services:
        lc_name = msg2id(service)
        lc_ret_type = lc_name + SRV_RET_SUFFIX
        cpp_type = get_srv_type(service).replace('/', '::')
        clientf.write(client_ros_service_members.format(srv_name=lc_name,
                                                        cpp_type=cpp_type))
        clientf.write(service_call_respond.format(lc_name=lc_name,
                                                  lc_ret_type=lc_ret_type))

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

    clientf.write('\n\tvoid setup_services() {\n')
    for service in services:
        name = msg2id(service)
        clientf.write('\t\tlabcomm_encoder_register_lc_types_{name}_RET(enc);\n'
                      .format(name=name))
        clientf.write('\t\tlabcomm_decoder_register_lc_types_{name}_PAR(dec, handle_srv_{name}, this);\n'
                      .format(name=name))
    clientf.write('\t' + end_fn)

    clientf.write(class_end)

    # Write LC callbacks for services.
    for service in services:
        lc_name = msg2id(service)
        lc_par_type = lc_name + SRV_PAR_SUFFIX
        lc_ret_type = lc_name + SRV_RET_SUFFIX
        cpp_type = get_srv_type(service).replace('/', '::')
        clientf.write(service_call_func.format(lc_name=lc_name,
                                               lc_par_type=lc_par_type,
                                               lc_ret_type=lc_ret_type,
                                               cpp_type=cpp_type,
                                               ros_name=service))
        definition = service_defs[get_srv_type(service)]
        convert_type(clientf, definition[0], 'to_ros', lc_ptr=False,
                     ros_ptr=False, ros_varname='msg->request', lc_varname='s')
        clientf.write(service_call_start_thread.format(lc_name=lc_name))
        # clientf.write('}\n')

    # Write subscriber callbacks that converts to LabComm samples.
    for topic in topics_out:
        topic_name = msg2id(topic)
        topic_type = topics_types[topic]
        topic_type_cpp = topic_type.replace('/', '::')
        convf.write(subscriber_cb_fn_begin.format(topic_name=topic_name,
                                                  topic_type=topic_type_cpp))
        # Write conversion from ROS to LabComm.
        free_list = convert_type(convf, get_def(topic_type), 'to_lc',
                                 lc_ptr=False, ros_ptr=True, ros_varname='msg',
                                 lc_varname='conv')
        write_send(convf, topic)
        write_free(convf, free_list)
        convf.write(subscriber_cb_fn_end)

    # Write LabComm callbacks that converts to ROS msgs.
    for topic in topics_in:
        definition = get_def(topics_types[topic])
        topic_type_cpp = topics_types[topic].replace('/', '::')
        convf.write(lc2ros_cb_fn_begin.format(topic_name=msg2id(topic),
                                              cpp_topic_type=topic_type_cpp))
        convert_type(convf, definition, 'to_ros', lc_ptr=True, ros_ptr=False,
                     ros_varname='msg', lc_varname='sample')
        convf.write(lc2ros_cb_fn_end.format(topic_name=msg2id(topic)))

    # Write LabComm callbacks that converts to ROS msgs.
    for service in services:
        ros_type = get_srv_type(service)
        definition = service_defs[ros_type]
        lc_name = msg2id(service)
        lc_par_type = lc_name + SRV_PAR_SUFFIX
        lc_ret_type = lc_name + SRV_RET_SUFFIX
        cpp_type = ros_type.replace('/', '::')
        convf.write(service_call_callback_begin.format(lc_name=lc_name,
                                                       lc_par_type=lc_par_type,
                                                       cpp_type=cpp_type))
        convf.write(service_call_callback_call_srv.format(srv_name=service,
                                                          cpp_type=cpp_type,
                                                          lc_ret_type=lc_ret_type,
                                                          lc_name=lc_name))
        convert_type(convf, definition[1], 'to_lc', lc_ptr=False,
                ros_ptr=False, ros_varname='msg->response', lc_varname='res')
        convf.write(service_call_callback_end.format(lc_name=lc_name))



conversions = {
    'to_ros': {
        '': ('', False),
        'default': ('\t{ros}.{name} = {lc}->{name};\n', False),
        'ddefault': ('\t{ros}.{rosname} = {lc}->{lcname};\n', False),
        'array': {
            'default': ('\t{ros}.{name}[i] = {lc}->{name}.a[i];\n', False),
            'string': ('\t\t{ros}.{name}.push_back({lc}->{name}.a[i]);\n', False),
            'time': (('\t\t{ros}.{name}[i].sec = {lc}->{name}.a[i].secs;\n'
                      '\t\t{ros}.{name}[i].nsec = {lc}->{name}.a[i].nsecs;\n'),
                      False),
            'alloc': (('\t{ros}.{name}.clear();\n'
                       '\tfor (int i = 0; i < {lc}->{name}.n_0; i++) {{\n'),
                       False),
            'end': ('\t}}', False)
        },
        'time': (('\t{ros}.{name}.sec = {lc}->{name}.secs;\n'
                  '\t{ros}.{name}.nsec = {lc}->{name}.nsecs;\n'), False),
        'ttime': (('\t{ros}.{rosname}.sec = {lc}->{lcname}.secs;\n'
                  '\t{ros}.{rosname}.nsec = {lc}->{lcname}.nsecs;\n'), False),
        'string': ('\t{ros}.{name} = {lc}->{name};\n', False),
        'sstring': ('\t{ros}.{rosname} = {lc}->{lcname};\n', False)
    },
    'to_lc': {
        '': ('', False),
        'default': ('\t{lc}.{name} = {ros}.{name};\n', False),
        'ddefault': ('\t{lc}.{lcname} = {ros}.{rosname};\n', False),
        'array': {
            'default': ('\t{lc}.{name}.a[i] = {ros}.{name}[i];\n', False),
            'string': ('\t\t{lc}.{name}.a[i] = strdup({ros}.{name}[i].c_str());\n', True),
            'time': (('\t\t{lc}.{name}.a[i].secs = {ros}.{name}[i].sec;\n'
                      '\t\t{lc}.{name}.a[i].nsecs = {ros}.{name}[i].nsec;\n'),
                      False),
            'alloc': (('\t{lc}.{name}.n_0 = {ros}.{name}.size();\n'
                       '\talloc_array((void **)&{lc}.{name}.a, {lc}.{name}.n_0,\n'
                       '\t            sizeof({ros}.{name}[0]));\n'
                       '\tfor (size_t i = 0; i < {ros}.{name}.size(); i++) {{\n'),
                       True),
            'end': ('\t}}\n', False)
        },
        'time': (('\t{lc}.{name}.secs = {ros}.{name}.sec;\n'
                  '\t{lc}.{name}.nsecs = {ros}.{name}.nsec;\n'), False),
        'ttime': (('\t{lc}.{lcname}.secs = {ros}.{rosname}.sec;\n'
                  '\t{lc}.{lcname}.nsecs = {ros}.{rosname}.nsec;\n'), False),
        'string': ('\t{lc}.{name} = strdup({ros}.{name}.c_str());\n', True),
        'sstring': ('\t{lc}.{lcname} = strdup({ros}.{rosname}.c_str());\n', True)
    }
}


def get_code(direction, key, array = False, ros_ptr = False, lc_ptr = False):
    conv = ''
    if array:
        conv = conversions[direction]['array'][key]
    else:
        conv = conversions[direction][key]
    st = conv[0]
    if ros_ptr:
        st = st.replace('{ros}.', '{ros}->')
    if lc_ptr:
        st = st.replace('{lc}.', '{lc}->')

    return (st, conv[1])


splitter = re.compile(r'[ =]')
def convert_type(f, definition, direction, ros_varname = '', lc_varname = '', 
                 prefix = '', lc_ptr = False, ros_ptr = False, in_array = False):
    '''Writes the conversion code for types.

    :param f: the file to write to.
    :param definition: the ROS type definition to convert to/from.
    :param direction: the direction to convert to (e.g. 'to_ros' or 'to_lc').
    :param ros_varname: the ROS variable name to use in the generated code.
    :param lc_varname: the LabComm variable name to use in the generated code.
    :param prefix: a possible prefix to prepend to the name, mostly only used
                   internally when writing non-primitive types.
    :param lc_ptr: boolean whether the generated code uses pointers for the
                   LabComm variable.
    :param ros_ptr: boolean whether the generated code uses pointers for the
                    ROS variable.
    :param in_array: used internally to keep state when writing arrays.
    '''
    conv_map = conversions[direction]

    free_list = []

    def append_free(stmt, rosvar, lcvar, name):
        if stmt[1]:
            defined = stmt[0].split('=')[0].strip()
            if 'alloc_array' in stmt[0]:
                defined = '{lc}.{name}.a' #TODO: This should be extracted from stmt[0]
            free_list.append(defined.format(ros=rosvar,lc=lcvar,lcname=name,name=name))

    def write_string(f, conv_map, rosvar, lcvar, name, in_array_local = False):
        '''Helper function for writing conversion code for strings.'''
        if in_array: # Not a nice hack... Should probably do better
            res = get_code(direction, 'sstring', in_array_local, ros_ptr, lc_ptr)
            parts = name.split('.')
            lcname = parts[0] + '.a[i].' + parts[1]
            rosname = parts[0] + '[i].' + parts[1]
            append_free(res, rosvar, lcvar, lcname)
            f.write(res[0].format(ros=rosvar,lc=lcvar,lcname=lcname,rosname=rosname))
        else:
            res = get_code(direction, 'string', in_array_local, ros_ptr, lc_ptr)
            append_free(res, rosvar, lcvar, name)
            f.write(res[0].format(ros=rosvar,lc=lcvar,name=name))

    def write_time_duration(f, conv_map, rosvar, lcvar, name, in_array_local = False):
        '''Helper function for writing conversion code for Time or Duration
        (which are primitive types in ROS msgs).
        '''
        if in_array: # Not a nice hack... Should probably do better
            res = get_code(direction, 'ttime', in_array_local, ros_ptr, lc_ptr)
            parts = name.split('.')
            lcname = parts[0] + '.a[i].' + parts[1]
            rosname = parts[0] + '[i].' + parts[1]
            append_free(res, rosvar, lcvar, lcname)
            f.write(res[0].format(ros=rosvar,lc=lcvar,lcname=lcname,rosname=rosname))
        else:
            res = get_code(direction, 'time', in_array_local, ros_ptr, lc_ptr)
            append_free(res, rosvar, lcvar, name)
            f.write(res[0].format(ros=rosvar,lc=lcvar,name=name))

    def write_array(f, conv_map, rosvar, lcvar, name, typ):
        '''Helper function for writing conversion code for arrays.'''
        res = get_code(direction, 'alloc', True, ros_ptr, lc_ptr)
        append_free(res, rosvar, lcvar, name)
        f.write(res[0].format(ros=rosvar,lc=lcvar,name=name))
        res = ('',False)
        if typ == 'string':
            write_string(f, conv_map, rosvar, lcvar, name, True)
        elif typ == 'time' or typ == 'duraiton':
            write_time_duration(f, conv_map, rosvar, lcvar, name, True)
        elif len(get_nested(typ)) > 0:
            convert_type(f, get_def(clean_type), direction, ros_varname=rosvar,
                         lc_varname=lcvar, prefix=name, lc_ptr=lc_ptr,
                         ros_ptr=ros_ptr, in_array=True)
        else:
            res = get_code(direction, 'default', True, ros_ptr, lc_ptr)
        append_free(res, rosvar, lcvar, name)
        f.write(res[0].format(ros=rosvar,lc=lcvar,name=name))
        res = conv_map['end']
        append_free(res, rosvar, lcvar, name)
        f.write(res[0].format(ros=rosvar,lc=lcvar,name=name))

    for d in definition.split('\n'):
        # Extract type info from definition.
        (typ, tail) = (lambda x: (x[0], x[1:]))(splitter.split(d))
        clean_type = typ.replace('[]', '')
        name = ''
        if len(tail) > 0:
            name = tail[0]
            if len(tail) > 1: # Skip enums
                continue
        if prefix:
            name = prefix + '.' + name
        if len(get_nested(typ)) > 0 and '[]' not in typ: # non-primitive type, recurse
            free_list += convert_type(f, get_def(clean_type), direction,
                                      ros_varname=ros_varname,
                                      lc_varname=lc_varname,
                                      lc_ptr=lc_ptr, ros_ptr=ros_ptr,
                                      prefix=name)
        else: # primitive type
            if '[]' in typ:
                # array_type = typ.replace('[]', '')
                write_array(f, conv_map['array'], ros_varname, lc_varname,
                            name, clean_type)
            elif typ == 'string':
                write_string(f, conv_map, ros_varname, lc_varname, name)
            elif typ == 'time' or typ == 'duration':
                write_time_duration(f, conv_map, ros_varname, lc_varname, name)
            elif typ == '':
                res = get_code(direction, '', False, ros_ptr, lc_ptr)
                f.write(res[0].format(ros=ros_varname,lc=lc_varname,name=name))
            else: # primitive types, just copy
                if in_array: # Not a nice hack... Should probably do better
                    res = get_code(direction, 'ddefault', False, ros_ptr, lc_ptr)
                    parts = name.split('.')
                    lcname = parts[0] + '.a[i].' + parts[1]
                    rosname = parts[0] + '[i].' + parts[1]
                    append_free(res, ros_varname, lc_varname, lcname)
                    f.write(res[0].format(ros=ros_varname,lc=lc_varname,
                                          lcname=lcname,rosname=rosname))
                else:
                    res = get_code(direction, 'default', False, ros_ptr, lc_ptr)
                    append_free(res, ros_varname, lc_varname, name)
                    f.write(res[0].format(ros=ros_varname,lc=lc_varname,name=name))

    return free_list

def write_send(f, topic, name, lc_prefix='lc_types', indent=1):
    '''Writes the code to send the converted data.
    
    :param f: the file handle to write to.
    :param topic: the topic being converted.
    '''
    lc_topic = msg2id(topic)
    tabs = '\t'*indent
    f.write(tabs+'boost::lock_guard<boost::mutex> enc_guard(enc_lock);\n')
    f.write(tabs+'labcomm_encode_{lc_prefix}_{lc_topic}(enc, {name});\n'
            .format(lc_topic=lc_topic, lc_prefix=lc_prefix,name=name))


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

static_conns_begin = '''
#include <cstring>

void LabCommBridge::setup_static()
{{
'''

static_conns_decl = '''
	struct sockaddr_in addr;
	std::vector<std::string> subs;
	std::vector<std::string> pubs;
	client *c;

'''

static_conns_content = '''
	memset(&addr, 0, sizeof(addr));
	addr.sin_family = AF_INET;
	inet_pton(AF_INET, "{addr}", &addr.sin_addr);
	addr.sin_port = htons({port});
'''

static_conns_loop = '''
	for (int j = 0; j < {ln}; j++) {{'''

static_conns_pubsub = '''
		{method}.push_back("{name}");
'''

static_conns_content_end = '''
	c = new client(-1, n, &addr, &subs, &pubs);
	boost::thread client_thread{n}(start_client, c);
	subs.clear();
	pubs.clear();

'''

def write_statics(f, pkg_name, static_connections):
    f.write(static_conns_begin.format(ln=len(static_connections)))

    if len(static_connections) > 0:
        # Write declarations.
        f.write(static_conns_decl)

        i = 0
        for conn in static_connections:
            addr = conn.split(':')[0]
            port = conn.split(':')[1]
            subs = static_connections[conn]['subscribe']
            pubs = static_connections[conn]['publish']

            f.write(static_conns_content.format(addr=addr,port=port))
            f.write(static_conns_loop.format(ln=len(subs)))
            # Populate subscriber list.
            for sub in subs:
                f.write(static_conns_pubsub.format(method='subs',name=sub))
            f.write('\t' + end_fn)

            # Populate publisher list.
            f.write(static_conns_loop.format(ln=len(pubs)))
            for pub in pubs:
                f.write(static_conns_pubsub.format(method='pubs',name=sub))
            f.write('\t' + end_fn)

            f.write(static_conns_content_end.format(n=i))
            i += 1

    f.write(end_fn)


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
    write_conf(cfil, cf.name, cf.port)
    cfil.close()

    # C++ conversions
    (clientfd, clientnam) = mkstemp('.h')
    (convfd, convnam) = mkstemp('.cpp')
    clientfil = os.fdopen(clientfd, 'w')
    convfil = os.fdopen(convfd, 'w')
    write_conv(clientfil, convfil, cf.name,
               topics_in, topics_out, topics_types,
               services_used, service_defs, cf.conversions)
    convfil.close()

    # C++ static connections.
    (statfd, statnam) = mkstemp('.cpp')
    statfil = os.fdopen(statfd, 'w')
    write_statics(statfil, cf.name, cf.static)
    statfil.close()

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
                      statnam, cf.lc_files(), cf.py_files())


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
        sys.exit(1)
    except ET.ParseError as e:
        sys.stderr.write(red("Parse error in config file '%s': %s\n" %
                             (opt.conf, e)))
        sys.exit(1)
