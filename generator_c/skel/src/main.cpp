#include "ros/ros.h"
#include "std_msgs/String.h"
#include "rosgraph_msgs/Log.h"

#include <exception>
#include <algorithm>
// #include <iostream>

#include <stdlib.h>
#include <sys/socket.h>
#include <netinet/in.h>

extern "C" {
#include <labcomm.h>
#include "lc_types.h"
#include "proto.h"
}

#include "conf.c"

class LabCommBridge {
	ros::NodeHandle n;
	int count;
	int sock;
	struct sockaddr_in addr;

public:
	LabCommBridge() : n(), count(0)
	{
		int ret = 0;

		/* Open socket */
		sock = socket(PF_INET, SOCK_STREAM, 0);
		if (sock < 0)
			throw std::runtime_error("socket() failed.");

		/* Set address, port and bind. */
		addr.sin_family      = AF_INET;
		addr.sin_port        = htons(PORT);
		addr.sin_addr.s_addr = htonl(INADDR_ANY);
		ret = bind(sock, (struct sockaddr *) &addr, sizeof(addr));
		if (ret) {
			close(sock);
			throw std::runtime_error("bind() failed.");
		}

		ret = listen(sock, 5);
		if (ret) {
			close(sock);
			throw std::runtime_error("listen() failed.");
		}
	}

	~LabCommBridge()
	{
		close(sock);
	}

	void serve();
};

void LabCommBridge::serve()
{
	setup_callbacks(n);

	ros::Publisher pong = n.advertise<std_msgs::String>("pong", 10);
	ros::Rate loop_rate(1);
	while (ros::ok()) {
		ROS_INFO("Bridge waiting...");
		std_msgs::String msg;

		std::stringstream ss;
		ss << "hello world " << (count++);
		msg.data = ss.str();

		ROS_INFO("Sending");

		pong.publish(msg);

		ros::spinOnce();
		loop_rate.sleep();
	}

}

void convert(const std_msgs::String::ConstPtr& msg)
{
	lc_types_std_msgsS__String s;
	
	s.data = strdup(msg->data.c_str());

	ROS_INFO("Converted: %s", s.data);
}

int main(int argc, char** argv)
{
	ros::init(argc, argv, PKG_NAME);

	LabCommBridge bridge;
	bridge.serve();

	return 0;
}
