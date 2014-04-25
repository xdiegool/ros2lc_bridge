#ifndef LABCOMM_BRIDGE_H
#define LABCOMM_BRIDGE_H

#include "ros/ros.h"

/* Other */
#include <stdexcept>
#include <cstdlib>

extern "C" {

#include <stdint.h>

/* Firefly includes */
#include <protocol/firefly_protocol.h>
#include <transport/firefly_transport_udp_posix.h>
#include <utils/firefly_event_queue.h>
#include <utils/firefly_event_queue_posix.h>

/* Generated LabComm types. */
#include "proto.h"
#include "lc_types.h"

int64_t conn_received(struct firefly_transport_llp *llp,
		const char *ip_addr, unsigned short port);
}

/* Generated config header. */
#include "conf.h"

static struct firefly_event_queue *eq;

static ros::NodeHandle *n;

class LabCommBridge {
	struct firefly_transport_llp *llp;

public:
	LabCommBridge()
	{
		int res;

		n = new ros::NodeHandle();

		eq = firefly_event_queue_posix_new(20);
		res = firefly_event_queue_posix_run(eq, NULL);
		if (res) {
			fprintf(stderr, "ERROR: starting event thread.");
		}

		llp = firefly_transport_llp_udp_posix_new(PORT, conn_received, eq);

		res = firefly_transport_udp_posix_run(llp);
		if (res) {
			fprintf(stderr, "ERROR: starting reader/resend thread.\n");
		}

		setup_static();
	}

	~LabCommBridge()
	{
		delete n;
		firefly_transport_udp_posix_stop(llp);
		firefly_transport_llp_udp_posix_free(llp);
		firefly_event_queue_posix_free(&eq);
	}

	void serve();
	void setup_static();
};

#endif
