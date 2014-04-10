#ifndef LABCOMM_BRIDGE_H
#define LABCOMM_BRIDGE_H

#include "ros/ros.h"

/* Boost */
#include <boost/thread.hpp>
/* Network */
#include <sys/socket.h>
#include <netinet/in.h>
/* Other */
#include <stdexcept>
#include <cstdlib>

extern "C" {

/* LabComm includes */
#include <labcomm.h>
#include <labcomm_default_memory.h>
#include <labcomm_default_error_handler.h>
#include <labcomm_default_scheduler.h>
#include <labcomm_fd_reader.h>
#include <labcomm_fd_writer.h>

/* Generated LabComm types. */
#include "proto.h"
#include "lc_types.h"

}

/* Generated config header. */
#include "conf.h"

class LabCommBridge {
protected:
	ros::NodeHandle n;
	int sock;

public:
	LabCommBridge() : n()
	{
		int ret = 0;
		struct sockaddr_in addr;

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

		/* Try to listen. */
		ret = listen(sock, 5);
		if (ret) {
			close(sock);
			throw std::runtime_error("listen() failed.");
		}

		setup_static();
	}

	~LabCommBridge()
	{
		close(sock);
	}

	void serve();
	void setup_static();
};

#endif
