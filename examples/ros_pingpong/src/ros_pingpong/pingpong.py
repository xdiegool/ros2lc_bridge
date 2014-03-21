#!/usr/bin/env python

import roslib; roslib.load_manifest('ros_pingpong')
import rospy
from std_msgs.msg import String


def callback(data, pub):
    """Callback for receiving data."""
    rospy.loginfo("I heard %s" % data.data)
    pub.publish(String(data.data))


def run():
    rospy.init_node('pingpong')
    pub = rospy.Publisher('pong', String)
    sub = rospy.Subscriber('ping', String, callback, callback_args=pub)
    rospy.spin()


if __name__ == '__main__':
    try:
        run()
    except rospy.ROSInterruptException:
        pass

