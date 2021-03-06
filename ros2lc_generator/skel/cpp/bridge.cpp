#include "bridge.h"

#include <labcomm.h>

#include "gen_bridge.cpp"

static void subscribe_callback(proto_subscribe *v, void *ctx)
{
	((client *) ctx)->handle_subscribe(v);
}

static void publish_callback(proto_publish *v, void *ctx)
{
	((client *) ctx)->handle_publish(v);
}

void chan_opened(struct firefly_channel *chan)
{
	struct firefly_connection *conn;
	struct labcomm_decoder *dec;
	struct labcomm_encoder *enc;
	client *c;

	ROS_INFO("Channel opened");

	/* Get connection from channel to get to context (i.e. client). */
	conn = firefly_channel_get_connection(chan);
	c = (client *) firefly_connection_get_context(conn);

	/* get encoder/decoder from channel to set on client. */
	dec = firefly_protocol_get_input_stream(chan);
	enc = firefly_protocol_get_output_stream(chan);

	c->set_encoder(enc);
	c->set_decoder(dec);
}

bool chan_recv(struct firefly_channel *chan)
{
	struct firefly_connection *conn;
	client *c;
	struct firefly_channel_types types = FIREFLY_CHANNEL_TYPES_INITIALIZER;

	ROS_INFO("Channel recieved");

	conn = firefly_channel_get_connection(chan);
	c = (client *) firefly_connection_get_context(conn);

	/* Get encoder/decoder from channel and set on client. */
	c->set_encoder(firefly_protocol_get_output_stream(chan));
	c->set_decoder(firefly_protocol_get_input_stream(chan));

	/* Use firefly's safe way to register types. */
	firefly_channel_types_add_decoder_type(&types,
			(labcomm_decoder_register_function)labcomm_decoder_register_proto_subscribe,
			(void (*)(void *, void *)) subscribe_callback, c);
	firefly_channel_types_add_decoder_type(&types,
			(labcomm_decoder_register_function)labcomm_decoder_register_proto_publish,
			(void (*)(void *, void *)) publish_callback, c);

	c->setup_imports(&types);
	c->setup_exports(&types);
	c->setup_services(&types);

	firefly_channel_set_types(chan, types);

	/* Always accept channel. */
	return true;
}

void chan_closed(struct firefly_channel *chan)
{
	client *c;
	struct firefly_connection *conn;

	/* Close connection when close channel and free client.*/
	conn = firefly_channel_get_connection(chan);
	c = (client *) firefly_connection_get_context(conn);

	if (c->close) {
		firefly_connection_close(conn);
	}

	delete c;

	ROS_INFO("Channel closed");
}

bool chan_restrict(struct firefly_channel *chan)
{
	return true;
}

void chan_restrict_info(struct firefly_channel *chan,
		enum restriction_transition restr)
{
	switch (restr) {
		case UNRESTRICTED:
			ROS_INFO("Channel un-restricted.");
			break;
		case RESTRICTED:
			ROS_INFO("Channel restricted.");
			break;
		case RESTRICTION_DENIED:
			ROS_INFO("Channel restriction denied.");
			break;
	}
}

void conn_opened(struct firefly_connection *conn)
{
	client *c;
	struct firefly_channel_types types = FIREFLY_CHANNEL_TYPES_INITIALIZER;
	void *old_ctx;

	ROS_INFO("Got connection");

	old_ctx = firefly_connection_get_context(conn);

	init_signatures();

	if (old_ctx) {
		// This is a static connection and old_ctx is the already existing
		// client subclass.
		c = (client *) old_ctx;
		c->setup_imports(&types);
		c->setup_exports(&types);
		c->setup_services(&types);

		// Open a channel to the other side.
		firefly_channel_open_auto_restrict(conn, types);
	} else {
		// Otherwise this is a dynamic connection so create new client and
		// attach it to the connection.
		c = new client(n);
		firefly_connection_set_context(conn, c);
		clients->push_back(c);
	}
}

int64_t conn_received(struct firefly_transport_llp *llp, const char *addr,
		unsigned short port)
{
	int64_t res;
	struct firefly_transport_connection *ftc;

	ROS_INFO("Got client: %s", addr);

	ftc = firefly_transport_connection_udp_posix_new(llp, addr, port,
								FIREFLY_TRANSPORT_UDP_POSIX_DEFAULT_TIMEOUT);

	res = firefly_connection_open(&actions, NULL, eq, ftc, NULL);

	// TODO: Remove?
	init_signatures();

	return res;
}

void LabCommBridge::serve()
{
	ROS_INFO("Bridge listening...");
	ros::spin();
	ROS_INFO("Bridge exiting...");
}

int main(int argc, char** argv)
{
	ros::init(argc, argv, PKG_NAME);

	LabCommBridge bridge;
	bridge.serve();

	return 0;
}
