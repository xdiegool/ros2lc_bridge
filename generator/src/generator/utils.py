from rosgraph.masterapi import Master
import re
import sys
import subprocess as sp
from time import strftime
import platform
from tcol import *
from collections import OrderedDict
from tempfile import mkstemp
import os


PROJ_NAME = 'generator'       # TODO: Is there an api for this?

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


def get_topic_types(tlist):
    """Query the master about topics and their types."""
    master = Master('/' + PROJ_NAME)
    ttdict = dict(master.getTopicTypes())
    want = set(tlist)
    have = set(ttdict.keys())
    missing = want - have
    if missing:
        raise GeneratorException("Unknown topics(s): %s" % ', '.join(missing))

    return {to: ttdict[to] for to in (set(ttdict.keys()) & set(tlist))}


defs_cache = {}
def get_msg_def(tnam):
    """Invoke the ros utility which returns the message type definitions."""
    if tnam in defs_cache:
        return defs_cache[tnam]

    ok, out = sh('rosmsg show %s' % tnam)
    for r in cleanup:
        out = r.sub('', out)
    defs_cache[tnam] = out.strip()
    return defs_cache[tnam]


srv_defs_cache = {}
def get_srv_def(srv):
    """Invoke a ROS utility to get a service type definition."""
    out = ''
    stype = srv['type']
    if stype in srv_defs_cache:
        return srv_defs_cache[stype]
    if srv['direction'] == 'export':
        ok, out = sh('rossrv show %s' % stype)
    else:
        with open(srv['file'], 'r') as f:
            for line in f:
                out += line
    for r in cleanup:
        out = r.sub('', out)
    b = out.index('---')
    params  = out[:b].strip()
    retvals = out[b+3:].strip()
    srv_defs_cache[stype] = (params, retvals)
    return srv_defs_cache[stype]


def get_nested(defn):
    """Find the nested types used in a message type definition."""
    nested = set()
    for line in defn.split('\n'):
        t = re_array_suffix.sub('', line.split(' ')[0])
        if t and t not in ros_prim: # '' is not complex...
            nested.add(t)
    return nested


def get_srv_types(slist):
    services = {}
    missing = set()
    for srv in slist:
        sname = srv['name']
        if srv['direction'] == 'export':
            ok, stype = sh('rosservice type %s' % sname, crit=False)
            if ok:
                srv['type'] = stype.strip()
                services[sname] = srv
            else:
                missing.add(sname)
        else:
            srv['type'] = os.path.basename(srv['file']).replace('.srv', '')
            services[sname] = srv
    if missing:
        raise GeneratorException("Unknown service(s): %s" % ', '.join(missing))
    return services


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
        f.write('typedef void %s;\n\n' % msg2id(pnam))

    if defn[1]:
        convert_msg_body(defn[1], '%s' % rnam, f);
    else:
        f.write('typedef void %s;\n\n' % msg2id(rnam))


def longest_id(itr):
    maxlen = 0
    for name in itr:
        if type(name) == str:
            maxlen = max(maxlen, len(msg2id(name)))
        else:
            maxlen = max(maxlen, len(msg2id(name['name'])))
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
''')

    # Message types
    f.write('\n\n/* Message types: */\n')
    try:
        while True:
            typ,defn = defs.popitem(True)
            convert_def(typ, defn, f) # Write lc definitions.
    except KeyError:
        pass # end of dict

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
    for (name, srv) in services.iteritems():
        atyp = srv['type'] + SRV_PAR_SUFFIX
        rtyp = srv['type'] + SRV_RET_SUFFIX
        anam = name + SRV_PAR_SUFFIX
        rnam = name + SRV_RET_SUFFIX
        f.write('sample %s %s;\n' % (msg2id(atyp).ljust(w), msg2id(anam)))
        f.write('sample %s %s;\n' % (msg2id(rtyp).ljust(w), msg2id(rnam)))


def sh(cmd, crit=True, echo=True, pr=True, col=normal, ocol=blue,
       ecol=red, nopipe=False):
    """Run a shell script in the specified way and make sure the user is aware of any errors."""
    if echo:
        print(col(cmd))

    kwarg = {}
    if not nopipe:
        kwarg = {'stdout': sp.PIPE, 'stderr': sp.PIPE}

    p = sp.Popen(cmd, shell=True, **kwarg)
    out, err = p.communicate()
    if pr and not nopipe:
            sys.stdout.write(ocol(out))
            sys.stderr.write(ecol(err))
    ok = not p.returncode # and not err
    if not ok and crit:
        if err and pr:          # Program printed its error properly.
            raise GeneratorException("")
        else:                   # It did not.
            raise GeneratorException("Command failed: '%s': '%s'" % (cmd, err))
    return (ok, out)


def resolve(conf):
    topics = conf.imports + conf.exports
    for conv in conf.conversions:
        topics += conv.topic_srcs
        topics += conv.topic_dsts
    topic_types = get_topic_types(topics) # tname -> msg type
    service_types = get_srv_types(conf.services)             # sname -> srv type

    types = []
    msg_defs = OrderedDict()                               # msg type -> def
    srv_defs = {}                                          # srv type -> def
    for t in service_types.itervalues():
        defn = get_srv_def(t)
        srv_defs[t['type']] = defn
        types.extend(list(get_nested(defn[0]) | get_nested(defn[1]) - set(srv_defs.keys())))
    for msg_type in topic_types.itervalues():
        types.append(msg_type)

    while types:
        t = types.pop(0)
        defn = get_msg_def(t)
        if t in msg_defs:
            msg_defs.pop(t)
        msg_defs[t] = defn
        types.extend(list(get_nested(defn) - set(msg_defs.keys())))

    (tfd, tmp_lc_name) = mkstemp('.lc')
    tfil = os.fdopen(tfd, 'w')
    write_lc(topic_types, msg_defs, service_types, srv_defs, tfil)
    tfil.close()

    deps = set()
    for type_str in topic_types.values():
        deps.add(type_str[:type_str.index('/')])

    for srv in service_types.values():
        if srv['direction'] == 'export':
            typ = srv['type']
            deps.add(typ[:typ.index('/')])


    return (topic_types, service_types, srv_defs, tmp_lc_name, deps)
