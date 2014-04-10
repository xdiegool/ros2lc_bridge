#include "client.h"

extern "C" {

/* LabComm includes */
#include <labcomm_default_error_handler.h>
#include <labcomm_fd_reader.h>
#include <labcomm_fd_writer.h>
#include <labcomm_default_memory.h>
#include <labcomm_default_scheduler.h>

/* C stuff */
#include <stdio.h> /* For perror(). */
}

/* Networking */
#include <sys/socket.h>
#include <sys/types.h>

/* Other */
#include <stdexcept>
#include <vector>
#include <string>

static void subscribe_callback(proto_subscribe *v, void *ctx)
{
	((client *) ctx)->handle_subscribe(v);
}

static void publish_callback(proto_publish *v, void *ctx)
{
	((client *) ctx)->handle_publish(v);
}

client::client(int client_sock, ros::NodeHandle &n,
		struct sockaddr_in *stat_addr,
		std::vector<std::string> *subscribe_to,
		std::vector<std::string> *publish_on)
	: sock(client_sock),
	  n(n),
	  enc_lock(),
	  active_topics()
{
	struct labcomm_reader *r;
	struct labcomm_writer *w;

	/* Check if we got a static address to connect to. */
	if (stat_addr) {
		int ret;
		socklen_t len;

		sock = socket(AF_INET, SOCK_STREAM, 0);
		if (sock < 0) {
			perror(NULL);
			throw std::runtime_error("stat_conn: socket() failed.");
		}

		len = (socklen_t) sizeof(struct sockaddr_in);
		ret = connect(sock, (struct sockaddr *) stat_addr, len);
		if (ret) {
			close(sock);
			perror(NULL);
			throw std::runtime_error("stat_conn: connect() failed.");
		}
	}

	/* TODO: Other reader/writer? */
	r = labcomm_fd_reader_new(labcomm_default_memory, sock, 1);
	w = labcomm_fd_writer_new(labcomm_default_memory, sock, 1);
	if (!w | !r) {
		free(w);
		free(r);
		throw std::runtime_error("Failed to create reader/writer.");
	}

	enc = labcomm_encoder_new(w, labcomm_default_error_handler,
							  labcomm_default_memory,
							  labcomm_default_scheduler);
	dec = labcomm_decoder_new(r, labcomm_default_error_handler,
							  labcomm_default_memory,
							  labcomm_default_scheduler);
	if (!enc | !dec) {
		labcomm_encoder_free(enc);
		labcomm_decoder_free(dec);
		throw std::runtime_error("Failed to create encoder/decoder.");
	}

	labcomm_decoder_register_proto_subscribe(dec, subscribe_callback, this);
	labcomm_decoder_register_proto_publish(dec, publish_callback, this);

	setup_imports();
	setup_exports();
	setup_services();

	if (stat_addr) {
		for(std::vector<std::string>::iterator it = subscribe_to->begin();
				it != subscribe_to->end(); ++it) {
			active_topics.insert(*it);
		}
	}
}

void client::run()
{
	int res;
	do {
		res = labcomm_decoder_decode_one(dec);

		if (res == -2) /* Handle LabComm's weird use of ENOENT. */
			ROS_WARN("Decode failed: Unknown type received.");
		else if (res < 0) /* Try to translate other errors. */
			ROS_WARN("Decode failed: %s", strerror(-res));

	} while (res > 0);

	ROS_INFO("Connection closed. Client exiting.");
}

/* Called when the bridge receives a subscribe request. */
void client::handle_subscribe(proto_subscribe *sub)
{
	ROS_INFO("Got subscribe request for topic: %s", sub->topic);
	active_topics.insert(sub->topic);
}

/* Called when the bridge receives a publish request (currently unused). */
void client::handle_publish(proto_publish *pub)
{
	ROS_INFO("Got publish request for topic: %s", pub->topic);
}

/* Include generated code. */
#include "conv.cpp"

