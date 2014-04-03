#include "client.h"

extern "C" {
#include <labcomm_default_error_handler.h>
#include <labcomm_fd_reader.h>
#include <labcomm_fd_writer.h>
#include <labcomm_default_memory.h>
#include <labcomm_default_scheduler.h>
}
#include <stdexcept>
#include <iostream>

static void subscribe_callback(proto_subscribe *v, void *ctx)
{
	((client *) ctx)->handle_subscribe(v);
}

static void publish_callback(proto_publish *v, void *ctx)
{
	((client *) ctx)->handle_publish(v);
}

client::client(int client_sock, ros::NodeHandle &n)
	: sock(client_sock), n(n)
{
	struct labcomm_reader *r;
	struct labcomm_writer *w;

	// TODO: Other reader/writer?
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
}

void client::run()
{
	int res;
	do {
		res = labcomm_decoder_decode_one(dec);
		if (res == -2) // Handle LabComm's weird use of ENOENT.
			std::cout << "Decode failed: Unknown type received." << std::endl;
		else if (res < 0)
			std::cout << "Decode failed: " << strerror(-res) << std::endl;
	} while (res > 0);
	std::cout << "Connection closed. Client exiting." << std::endl;
}

void client::handle_subscribe(proto_subscribe *sub)
{
	std::cout << "Got subscribe request for topic: " << sub->topic << std::endl;
}

void client::handle_publish(proto_publish *pub)
{
	std::cout << "Got publish request for topic: " << pub->topic << std::endl;
}

// Include generated code
#include "conv.cpp"

