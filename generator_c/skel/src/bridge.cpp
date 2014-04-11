#include "bridge.h"
#include "client.h"

#include <sys/types.h>
#include <sys/socket.h>
#include <arpa/inet.h>
#include <stdio.h>

static void start_client(client *c)
{
	c->run();
	delete c;
}

static void accept_thread(int sock, ros::NodeHandle &n)
{
	ROS_INFO("Bridge waiting...");
	while (ros::ok()) {
		socklen_t addrlen;
		struct sockaddr_in client_addr;
		int csock;
		char addr[INET_ADDRSTRLEN];

		addrlen = sizeof(struct sockaddr_in);
		csock = accept(sock, (struct sockaddr *) &client_addr, &addrlen);
		inet_ntop(AF_INET, &client_addr.sin_addr, addr, INET_ADDRSTRLEN);
		ROS_INFO("Got client: %s", addr);

		/* Create a new client and start in a new thread. */
		client *c = new client(csock, n);
		boost::thread client_thread(start_client, c);
	}
}

void LabCommBridge::serve()
{
	boost::thread accepter(accept_thread, sock, n);
	ros::spin();
}

int main(int argc, char** argv)
{
	ros::init(argc, argv, PKG_NAME);

	LabCommBridge bridge;
	bridge.serve();

	return 0;
}

#include "gen_bridge.cpp"
