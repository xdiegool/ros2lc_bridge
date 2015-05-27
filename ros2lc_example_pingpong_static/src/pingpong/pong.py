#!/usr/bin/env python

import roslib; roslib.load_manifest('ros2lc_example_pingpong_static')
import rospy
from ros2lc_example_pingpong_static import msg


def callback(data, pub):
    """Callback for receiving data."""
    rospy.loginfo("I heard %s" % data.s)
    pub.publish(data)


def run():
    rospy.init_node('pingpong')
    pub = rospy.Publisher('pong', msg.pingpong)
    sub = rospy.Subscriber('ping', msg.pingpong, callback, callback_args=pub)
    rospy.spin()


if __name__ == '__main__':
    try:
        run()
    except rospy.ROSInterruptException:
        pass

