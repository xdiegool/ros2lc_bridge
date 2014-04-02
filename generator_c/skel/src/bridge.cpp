#include "ros/ros.h"
#include "std_msgs/String.h"

#include "sys/types.h"
#include "sys/socket.h"
#include <iostream>

#include "bridge.h"
#include "client.h"

static void spinny()
{
	ros::spin();
}

static void start_client(client *c)
{
	c->run();
}

void LabCommBridge::serve()
{
	// ros::Publisher pong = n.advertise<std_msgs::String>("pong", 10);

	// Call ros::spin() from another thread.
	boost::thread spinner(spinny);

	while (ros::ok()) {
		ROS_INFO("Bridge waiting...");
		struct sockaddr_in client_addr;
		socklen_t addrlen = sizeof(struct sockaddr_in);
		int csock = accept(sock, (struct sockaddr *) &client_addr, &addrlen);

		// boost::thread run_decoder_thread(run_decode, dec);

		client *c = new client(csock, n);
		boost::thread client_thread(start_client, c);

		std::cout << "Got client: " << csock << std::endl;

		// TODO: Impl. more.
	}

}

