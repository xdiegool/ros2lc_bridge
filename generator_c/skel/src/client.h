#ifndef CLIENT_H
#define CLIENT_H

extern "C" {
#include <labcomm.h>

#include "proto.h"
#include "lc_types.h"
}

class client {
	int sock;
	struct labcomm_decoder *dec;
	struct labcomm_encoder *enc;
	struct labcomm_reader *r;
	struct labcomm_writer *w;
	
public:
	client(int sock);
	~client()
	{
		labcomm_decoder_free(dec);
		labcomm_encoder_free(enc);
	}

	void run();

	void handle_subscribe(proto_subscribe *subs);
	void handle_publish(proto_publish *pub);
};

#endif
