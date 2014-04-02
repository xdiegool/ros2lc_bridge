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
	std::cout << "before cpp callback" << std::endl;
	((client *) ctx)->handle_subscribe(v);
	std::cout << "in labcomm callback" << std::endl;
}

static void publish_callback(proto_publish *v, void *ctx)
{
	std::cout << "before cpp callback" << std::endl;
	((client *) ctx)->handle_publish(v);
	std::cout << "in labcomm callback" << std::endl;
}

static void ping_callback(lc_types_S__ping *v, void *ctx)
{
	std::cout << "got ping" << std::endl;
}


client::client(int client_sock) : sock(client_sock)
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
	labcomm_decoder_register_lc_types_S__ping(dec, ping_callback, this);
}

void client::run()
{
	int res;
	do {
		res = labcomm_decoder_decode_one(dec);
	} while (res > 0);
	std::cout << "labcomm decode failed with result: " << res << std::endl;
}

void client::handle_subscribe(proto_subscribe *sub)
{
	std::cout << "Got subscribe message for topic: " << sub->topic << std::endl;
}

void client::handle_publish(proto_publish *pub)
{
	std::cout << "Got subscribe message for topic: " << pub->topic << std::endl;
}

