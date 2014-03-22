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


SLASHSUB       = 'S__'
SRV_PAR_SUFFIX = '_PAR'
SRV_RET_SUFFIX = '_RET'


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


def get_def(tnam):
    """Invoke the ros utility which returns the message type definitions."""
    ok, out = sh('rosmsg show %s' % tnam)
    for r in cleanup:
        out = r.sub('', out)
    return out.strip()


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


def create_pkg(ws, name, deps, force, lc_file, conf_file, mlc, mpy):
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

    depstr = ' '.join(['roslib', 'rospy'] + list(deps))
    sh('cd %s && roscreate-pkg %s %s' % (ws, name, depstr))
    try:
        lcdir = os.path.join(d, 'lc')
        srcdir = os.path.join(d, 'src')
        skel_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'skel')

        os.mkdir(lcdir)
        os.rename(lc_file, os.path.join(lcdir, 'lc_types.lc'))
        sh('cp %s/*.py %s/' % (skel_dir, srcdir))
        os.rename(conf_file, os.path.join(srcdir, 'conf.py'))

        lcc = os.environ.get('LABCOMMC')
        if not lcc:
            raise Exception("Env. $LABCOMMC not set, can't compile types.")
        sh('java -jar %s --python=%s/lc_types.py %s/lc_types.lc ' % (lcc, srcdir, lcdir))

        # Copy user stuff for manual conversion.
        for lc in mlc:
            shutil.copy(lc, lcdir)
            name = os.path.splitext(os.path.basename(lc))[0]
            sh('java -jar {jar} --python={dest}.py {src}.lc'.format(
                    jar=lcc,
                    dest=os.path.join(srcdir, name),
                    src=os.path.join(lcdir, name)))
        for py in mpy:
            shutil.copy(py, srcdir)

        os.chmod('%s/conf.py' % srcdir,
                 stat.S_IRUSR | stat.S_IWUSR |
                 stat.S_IRGRP | stat.S_IWGRP)
        os.chmod('%s/rwsock.py' % srcdir,
                 stat.S_IRUSR |
                 stat.S_IRGRP)
        os.chmod('%s/lc_types.py' % srcdir,
                 stat.S_IRUSR |
                 stat.S_IRGRP)
        os.chmod('%s/main.py' % srcdir,
                 stat.S_IRUSR | stat.S_IXUSR |
                 stat.S_IRGRP | stat.S_IXGRP)
    except Exception as e:
        # sh('rm -fr ' + d)       # Clean up
        raise e
    return d


def write_conf(f, bname, port, topics_in, topics_out, topics, services,
               static_conns, conversions):
    convs = []
    for conv in conversions:
        convs.append(conv.tuple_repr())
    f.write('''#!/usr/bin/env python

PKG_NAME    = '{name}'
PORT        = {port}
SLASHSUB    = '{slsub}'
TOPICS_IN   = {t_in}
TOPICS_OUT  = {t_out}
TOPIC_TYPES = {t_t}
SERVICES    = {srvs}
STATIC_CONNS = {stat_conns}
CONV        = {conv}
'''.format(name=bname,
           t_in=topics_in,
           t_out=topics_out,
           t_t=topics,
           port=port,
           slsub=SLASHSUB,
           srvs=services,
           stat_conns=static_conns,
           conv=convs))


def get_srv_types():
    slist = sh('rosservice list')[1]
    services = {}
    for sname in slist.strip().split('\n'):
        stype = sh('rosservice type %s' % sname)[1]
        services[sname] = stype.strip()
    return services


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
    services_used = cf.assert_defined_services(list(services))
    topics_types = { t: topics[t] for t in topics_in + topics_out }

    (cfd, cnam) = mkstemp('.xml')
    cfil = os.fdopen(cfd, 'w')
    write_conf(cfil, cf.name, cf.port,
               topics_in, topics_out, topics_types,
               services_used, cf.static, cf.conversions)
    cfil.close()

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

    deps = set()
    for dep in topics.itervalues():
        deps.add(dep[:dep.index('/')])

    return create_pkg(ws, cf.name, deps, force, tnam, cnam,
                      cf.lc_files(), cf.py_files())


if __name__ == '__main__':
    op = OptionParser()
    op.add_option('-c', '--config-file', dest='conf', default=None,
                  help='The bridge configuration file.')
    op.add_option('-w', '--workspace-path', dest='ws', default=None,
                  help='The directory in which the package will be created.')
    op.add_option('-f', '--force', action="store_true", dest="force",
                  help='Replace any existing directory in case of a name collision')
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
