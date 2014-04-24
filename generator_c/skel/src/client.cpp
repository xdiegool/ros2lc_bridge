#include "client.h"

/* Other */
#include <stdexcept>
#include <vector>
#include <string>

client::client(struct firefly_connection *conn,
		ros::NodeHandle *n,
		struct sockaddr_in *stat_addr,
		std::vector<std::string> *subscribe_to,
		std::vector<std::string> *publish_on)
	: n(n),
	  enc_lock(),
	  active_topics() { }

client::~client()
{
	/* Make sure we join on all service threads created. */
	std::vector<boost::shared_ptr<boost::thread> >::iterator it;
	for (it = service_threads.begin(); it != service_threads.end(); ++it) {
		(*it)->join();
	}
}

void client::set_encoder(struct labcomm_encoder *enc)
{
	this->enc = enc;
}

void client::set_decoder(struct labcomm_decoder *dec)
{
	this->dec = dec;
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

