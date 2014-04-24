#include "bridge.h"
#include "client.h"

#include <labcomm.h>

static void subscribe_callback(proto_subscribe *v, void *ctx)
{
	((client *) ctx)->handle_subscribe(v);
}

static void publish_callback(proto_publish *v, void *ctx)
{
	((client *) ctx)->handle_publish(v);
}

static void chan_opened(struct firefly_channel *chan)
{
	ROS_INFO("Channel opened");
	struct firefly_connection *conn;
	client *c;

	/* Get connection from channel to get to context (i.e. client). */
	conn = firefly_channel_get_connection(chan);
	if (!conn) {
		ROS_ERROR("Got channel without connection.");
	}
	c = (client *) firefly_connection_get_context(conn);

	c->setup_services();
}

static bool chan_recv(struct firefly_channel *chan)
{
	ROS_INFO("Channel recieved");
	struct firefly_connection *conn;
	struct labcomm_decoder *dec;
	struct labcomm_encoder *enc;
	client *c;
	struct firefly_channel_types types = FIREFLY_CHANNEL_TYPES_INITIALIZER;

	/* Get encoder/decoder from channel to set on client. */
	dec = firefly_protocol_get_input_stream(chan);
	enc = firefly_protocol_get_output_stream(chan);

	conn = firefly_channel_get_connection(chan);
	c = (client *) firefly_connection_get_context(conn);

	c->set_encoder(enc);
	c->set_decoder(dec);

	/* Use firefly's safe way to register types. */
	firefly_channel_types_add_decoder_type(&types,
			(labcomm_decoder_register_function)labcomm_decoder_register_proto_subscribe,
			(void (*)(void *, void *)) subscribe_callback, c);
	firefly_channel_types_add_decoder_type(&types,
			(labcomm_decoder_register_function)labcomm_decoder_register_proto_publish,
			(void (*)(void *, void *)) publish_callback, c);

	c->setup_imports(&types);
	c->setup_exports(&types);
	firefly_channel_set_types(chan, types);

	/* Always accept channel. */
	return true;
}

static void chan_closed(struct firefly_channel *chan)
{
	client *c;
	struct firefly_connection *conn;

	/* Close connection when close channel and free client.*/
	conn = firefly_channel_get_connection(chan);
	c = (client *) firefly_connection_get_context(conn);

	firefly_connection_close(conn);

	delete c;

	ROS_INFO("Channel closed");
}

static bool chan_restrict(struct firefly_channel *chan)
{
	return true;
}

static void chan_restrict_info(struct firefly_channel *chan,
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

static void conn_opened(struct firefly_connection *conn)
{
	client *c;

	ROS_INFO("Got connection");

	/* Create new client and attach it to the connection. */
	c = new client(conn, n);
	firefly_connection_set_context(conn, c);
}

static struct firefly_connection_actions actions;

int64_t conn_received(struct firefly_transport_llp *llp, const char *addr,
		unsigned short port)
{
	int64_t res;
	struct firefly_transport_connection *ftc;

	ROS_INFO("Got client: %s", addr);

	ftc = firefly_transport_connection_udp_posix_new(llp, addr, port,
								FIREFLY_TRANSPORT_UDP_POSIX_DEFAULT_TIMEOUT);

	res = firefly_connection_open(&actions, NULL, eq, ftc);

	return res;
}

void LabCommBridge::serve()
{
	actions.channel_opened			= chan_opened;
	actions.channel_closed			= chan_closed;
	actions.channel_recv			= chan_recv;
	actions.channel_restrict		= chan_restrict;
	actions.channel_restrict_info	= chan_restrict_info;
	actions.connection_opened		= conn_opened;

	ROS_INFO("Bridge listening...");
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
