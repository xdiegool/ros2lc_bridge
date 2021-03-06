import stat
import shutil
from config_file import *
from collections import OrderedDict

from utils import *


def create_pkg(ws, name, deps, force, lc_file, conf_file, mlc, mpy, msrv):
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

    depstr = ' '.join(['roslib', 'rospy', 'message_generation'] + list(deps))
    sh('cd %s && catkin_create_pkg %s %s' % (ws, name, depstr))
    try:
        lcdir = os.path.join(d, 'lc')
        srvdir = os.path.join(d, 'srv')
        srcdir = os.path.join(d, 'src')
        skeldir = os.path.join(os.path.dirname(__file__), '..', '..', '..',
                               'skel')
        skelcodedir = os.path.join(skeldir, 'python')
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
        os.rename(conf_file, os.path.join(srcdir, 'conf.py'))

        lcpath = os.environ.get('LABCOMM')
        if not lcpath:
            raise GeneratorException("Env. $LABCOMM not set, can't compile types."
                                     " (Should be path to LabComm directory.)")
        for f in os.listdir(lcdir):
            name = os.path.splitext(f)[0]
            lcfile = os.path.join(lcdir, f)
            pyfile = os.path.join(srcdir, name + '.py')
            sh('java -jar %s --python=%s %s' %
               (lcpath + '/compiler/labComm.jar', pyfile, lcfile))

        # Copy user stuff for manual conversion.
        for lc in mlc:
            shutil.copy(lc, lcdir)
            name = os.path.splitext(os.path.basename(lc))[0]
            sh('java -jar {jar} --python={dest}.py {src}.lc'.format(
                    jar=lcpath + '/compiler/labComm.jar',
                    dest=os.path.join(srcdir, name),
                    src=os.path.join(lcdir, name)))
        for py in mpy:
            shutil.copy(py, srcdir)

        # Copy any custom service files.
        if len(msrv) > 0:
            os.mkdir(srvdir)

        with open('%s/CMakeLists.txt' % d, 'r+') as bf:
            cmake_content = bf.read()
            if len(msrv) > 0:
                cmake_content = cmake_content.replace("# generate_messages(",
                        "generate_messages()")

            srv_files_string = ""
            for srv in msrv:
                srv_files_string += os.path.basename(srv) + "\n"
                shutil.copy(srv, srvdir)

            if not srv_files_string == "":
                cmake_content = cmake_content.replace("# add_service_files(",
                        "add_service_files(FILES\n" + srv_files_string + ")")

            bf.seek(0)
            bf.write(cmake_content)
            bf.truncate()

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


def write_conf(f, bname, port, autopubsub, exports, imports, topics, services,
        static_conns, conversions):
    convs = []
    for conv in conversions:
        convs.append(conv.tuple_repr())
    f.write('''#!/usr/bin/env python

PKG_NAME     = '{name}'
PORT         = {port}
AUTOPUBSUB   = {autopubsub}
SLASHSUB     = '{slsub}'
EXPORTS      = {exports}
IMPORTS      = {imports}
TOPIC_TYPES  = {t_t}
SERVICES     = {srvs}
STATIC_CONNS = {stat_conns}
CONV         = {conv}
'''.format(name=bname,
           exports=exports,
           imports=imports,
           t_t=topics,
           port=port,
           autopubsub=autopubsub,
           slsub=SLASHSUB,
           srvs=services,
           stat_conns=static_conns,
           conv=convs))


def run(conf, ws, force):
    """Run the tool and put a generated package in ws."""
    cf = ConfigFile(conf)
    (topics_types, services_used, _, tnam, deps) = resolve(cf)

    (cfd, cnam) = mkstemp('.py')
    cfil = os.fdopen(cfd, 'w')
    write_conf(cfil, cf.name, cf.port, cf.autopubsub,
               cf.exports, cf.imports, topics_types,
               services_used, cf.static, cf.conversions)
    cfil.close()

    srv_files = []
    for name, srv in services_used.iteritems():
        if srv['direction'] == 'import':
            srv_files.append(srv['file'])

    return create_pkg(ws, cf.name, deps, force, tnam, cnam,
                      cf.lc_files(), cf.py_files(), srv_files)
