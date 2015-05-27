#!/usr/bin/env python

import roslib; roslib.load_manifest('ros2lc_example_forcetorque')
import rospy
from ros2lc_example_forcetorque.msg import forcetorque


def pub():
    pub = rospy.Publisher('force_torque', forcetorque)
    rospy.init_node('ft_pub')
    cnt = 0.0
    while not rospy.is_shutdown():
        ft = forcetorque()
        ft.force.x = cnt
        ft.force.y = cnt + 1
        ft.force.z = cnt + 2
        ft.torque.x = cnt + 2
        ft.torque.y = cnt + 1
        ft.torque.z = cnt
        rospy.loginfo("\n%s", ft)
        pub.publish(ft)
        cnt += 1
        rospy.sleep(1.0)


if __name__ == '__main__':
    try:
        pub()
    except rospy.ROSInterruptException:
        pass
