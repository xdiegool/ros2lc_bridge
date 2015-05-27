#!/usr/bin/env python

import roslib; roslib.load_manifest('ros2lc_example_external_service')
import rospy

import sys

from ext_service_bridge.srv import *


def test_caller_client(x):
    rospy.wait_for_service('/ext_service')

    try:
        func = rospy.ServiceProxy('/ext_service', ExtServer)
        res = func(x)
        return res.status
    except rospy.ServiceException, e:
        print "Service call failed: %s" % e


if __name__ == "__main__":
    controller_id = 0
    if len(sys.argv) == 2:
        controller_id = int(sys.argv[1])

    print "Requesting controller_id: %s" % controller_id
    print "Response status: %s" % test_caller_client(controller_id)
