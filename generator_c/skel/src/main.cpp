#include "ros/ros.h"
#include "std_msgs/String.h"
#include "rosgraph_msgs/Log.h"

#include "bridge.h"

int main(int argc, char** argv)
{
	ros::init(argc, argv, PKG_NAME);

	LabCommBridge bridge;
	bridge.serve();

	return 0;
}
