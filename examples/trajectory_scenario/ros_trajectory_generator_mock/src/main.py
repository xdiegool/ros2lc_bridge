#!/usr/bin/env python

import roslib; roslib.load_manifest("ros_trajectory_generator_mock")
import rospy
from std_msgs.msg import Float32
from threading import Lock


class TrajComp(object):
    """Just a mock up for testing."""
    def __init__(self):
        self.lock = Lock()
        self.x = None
        self.y = None
        self.z = None
        self.i = 0
        self.xsub = rospy.Subscriber('posX', Float32, self.setxp)
        self.ysub = rospy.Subscriber('posY', Float32, self.setyp)
        self.zsub = rospy.Subscriber('posZ', Float32, self.setzp)
        self.xpub = rospy.Publisher('velX', Float32)
        self.ypub = rospy.Publisher('velY', Float32)
        self.zpub = rospy.Publisher('velZ', Float32)
        self.tpub = rospy.Publisher('velT', Float32)

    def setxp(self, msg):
        print "got x"
        with self.lock:
            self.x = msg.data
            self._send()

    def setyp(self, msg):
        print "got y"
        with self.lock:
            self.y = msg.data
            self._send()

    def setzp(self, msg):
        print "got z"
        with self.lock:
            self.z = msg.data
            self._send()

    def _send(self):
        if self.x is None or self.y is None or self.z is None:
            return
        self.xpub.publish(Float32(self.x))
        self.ypub.publish(Float32(self.y))
        self.zpub.publish(Float32(self.z))
        self.tpub.publish(self.i)
        self.i += 1
        self.x = self.y = self.z = None


if __name__ == '__main__':
    rospy.init_node('mock_trajectory_generator')
    rospy.loginfo("Starting...")
    tc = TrajComp()
    rospy.loginfo("Running")
    rospy.spin()
