#include "ros/ros.h"
#include "std_msgs/String.h"
#include "rosgraph_msgs/Log.h"

#include "bridge.h"
#include "conv.cpp"

int main(int argc, char** argv)
{
	ros::init(argc, argv, PKG_NAME);

	LabCommBridgeImpl bridge;
	bridge.serve();

	return 0;
}
