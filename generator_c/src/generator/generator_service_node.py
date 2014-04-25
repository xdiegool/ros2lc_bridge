#!/usr/bin/env python

import roslib; roslib.load_manifest('generator')
import rospy
from generator.srv import *
from generator import generator, config_file
from tempfile import mkstemp, mkdtemp
import os
from os.path import join, dirname, exists
from shutil import rmtree


def handle_generate_bridge(req):
    # Recreate the file system relative the configuration file. (This
    # was the most painless way to support the remote use of a config
    # file. Otherwise the configuration file would have to be
    # rewritten.)

    rospy.loginfo("Got request to generate package. Recreating tree...")
    td = mkdtemp('', 'ros_bridge_gen_service_') # Base dir for temp tree.
    (cfd, cnam) = mkstemp('.xml', '', td)       # Temp config file.
    cfil = os.fdopen(cfd, 'w')
    cfil.write(req.config)
    cfil.close()
    for fname, fcont in zip(req.file_names, req.file_contents):
        fpath = join(td, fname)
        dpath = dirname(fpath)
        if not exists(dpath):
            os.makedirs(dpath)                   # Recreate subtree.
        print "wrtint", fname, len(fcont)
        f = open(fpath, 'w')
        f.write(fcont)                           # Write the file used in config.
        f.close()
    rospy.loginfo("Running bridge generator...")
    pkg_dir = generator.run(cnam, None, True)    # Run generator on temp tree.
    rmtree(td)                                   # Remove temp tree.
    rospy.loginfo("Created package: %s", pkg_dir)
    return GenerateBridgeResponse(True, pkg_dir)


def main():
    rospy.init_node('ros_bridge_gen_service_node')
    s = rospy.Service('generate_bridge', GenerateBridge, handle_generate_bridge)
    rospy.loginfo("Waiting...")
    rospy.spin()


if __name__ == '__main__':
    main()
