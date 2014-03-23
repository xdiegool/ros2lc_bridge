#!/usr/bin/env python

import roslib; roslib.load_manifest("generator")
import rospy
import sys
from generator.srv import *
from generator import config_file


def main():
    """Takes the path to a config file as argument. Calls the
    generate_bridge service which in turn runs the bridge
    generator. All files referenced in the config file will be read
    and sent to the service. In this way it will work over system
    boundaries as well.
    """

    # See calls to rospy.loginfo for comments.
    rospy.init_node('ros_bridge_gen_client_node')
    if len(sys.argv) < 2:
        rospy.logerr("Please specify config file")
        rospy.signal_shutdown("Missing argument.")
        sys.exit(1)
    conf_path = sys.argv[1]
    rospy.loginfo("Reading configuration file...")
    cont = open(conf_path).read()
    rospy.loginfo("Reading referenced files...")
    files = config_file.collect_referenced_files(conf_path)

    rospy.loginfo("Waiting for service...")
    rospy.wait_for_service('generate_bridge')
    resp = None
    try:
        rospy.loginfo("Creating service proxy...")
        bridge_gen_proxy = rospy.ServiceProxy('generate_bridge', GenerateBridge)
        rospy.loginfo("Invoking service...")
        resp = bridge_gen_proxy(cont, files.keys(), files.values())
        if resp.done:
            rospy.loginfo("Bridge created successfully at %s", resp.path)
        else:
            rospy.logerr("Generator failed.")
    except rospy.ServiceException as e:
        rospy.logerr("Call to generator service failed.")


if __name__ == '__main__':
    main()
