#ifndef LABCOMM_BRIDGE_H
#define LABCOMM_BRIDGE_H

#include "ros/ros.h"

#include "client.h"

/* Other */
#include <stdexcept>
#include <cstdlib>
#include <vector>

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

void chan_opened(struct firefly_channel *chan);
bool chan_recv(struct firefly_channel *chan);
void chan_closed(struct firefly_channel *chan);
bool chan_restrict(struct firefly_channel *chan);
void chan_restrict_info(struct firefly_channel *chan,
		enum restriction_transition restr);
static void conn_opened(struct firefly_connection *conn);


int64_t conn_received(struct firefly_transport_llp *llp,
		const char *ip_addr, unsigned short port);
}

/* Generated config header. */
#include "conf.h"

static struct firefly_event_queue *eq;
static struct firefly_connection_actions actions;

static ros::NodeHandle *n;
static std::vector<client *> *clients;
static std::set<client *> statics;

class LabCommBridge {
	struct firefly_transport_llp *llp;

public:
	LabCommBridge()
	{
		int res;

		n = new ros::NodeHandle();
		clients = new std::vector<client *>();

		/* Populate firefly_connection_actions struct. */
		actions.channel_opened			= chan_opened;
		actions.channel_closed			= chan_closed;
		actions.channel_recv			= chan_recv;
		actions.channel_restrict		= chan_restrict;
		actions.channel_restrict_info	= chan_restrict_info;
		actions.connection_opened		= conn_opened;

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
		std::vector<client *>::iterator it;
		for (it = clients->begin(); it != clients->end(); ++it) {
			(*it)->close = false;
		}
		delete clients;
		firefly_transport_udp_posix_stop(llp);
		firefly_transport_llp_udp_posix_free(llp);
		firefly_event_queue_posix_free(&eq);
		delete n;
	}

	void serve();
	void setup_static();
};

#endif
