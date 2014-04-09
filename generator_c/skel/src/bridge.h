#ifndef LABCOMM_BRIDGE_H
#define LABCOMM_BRIDGE_H

#include "ros/ros.h"

#include <stdexcept>
#include <cstdlib>
#include <boost/thread.hpp>

extern "C" {

#include <labcomm.h>
#include <labcomm_default_memory.h>
#include <labcomm_default_error_handler.h>
#include <labcomm_default_scheduler.h>
#include <labcomm_fd_reader.h>
#include <labcomm_fd_writer.h>

#include <sys/socket.h>
#include <netinet/in.h>
#include "lc_types.h"
#include "proto.h"

}

#include "conf.h"

class LabCommBridge {
protected:
	ros::NodeHandle n;
	int sock;
	struct sockaddr_in addr;

public:
	LabCommBridge() : n()
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

#endif
