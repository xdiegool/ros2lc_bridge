#include "bridge.h"
#include "client.h"

#include <sys/types.h>
#include <sys/socket.h>
#include <arpa/inet.h>
#include <stdio.h>

static void start_client(int csock, struct sockaddr_in *client_addr,
		ros::NodeHandle &n)
{
	char	addr[INET_ADDRSTRLEN];
	client	*c;

	/* Convert and print the client's address. */
	inet_ntop(AF_INET, &client_addr->sin_addr, addr, INET_ADDRSTRLEN);
	ROS_INFO("Got client: %s", addr);

	/* Create a new client and start in a new thread. */
	c = new client(csock, n);
	c->run();

	delete c;
}

static void accept_thread(int sock, ros::NodeHandle &n)
{
	socklen_t addrlen;

	addrlen = sizeof(struct sockaddr_in);

	ROS_INFO("Bridge waiting...");
	while (ros::ok()) {
		struct sockaddr_in	client_addr;
		int					csock;

		csock = accept(sock, (struct sockaddr *) &client_addr, &addrlen);

		/* Start thread to handle the client. */
		boost::thread client_thread(start_client, csock, &client_addr, n);
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
