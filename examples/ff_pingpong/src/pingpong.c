#include <stdlib.h>
#include <stdio.h>
#include <err.h>
#include <unistd.h>
#include <signal.h>
#include <string.h>

#include <protocol/firefly_protocol.h>
#include <transport/firefly_transport_udp_posix.h>
#include <utils/firefly_event_queue.h>
#include <utils/firefly_event_queue_posix.h>
#include "proto.h"
#include "lc_types.h"


#define ADDR "127.0.0.1"
#define PORT 7357
#define LOCAL_PORT 7358


static struct firefly_connection *connection;
static struct firefly_channel *channel;
static pthread_mutex_t lock = PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t sig = PTHREAD_COND_INITIALIZER;
static volatile sig_atomic_t stop;


static void handle_pong(lc_types_S__pong *pong, void *context)
{
    printf("Got pong %s\n", pong->s);
}

static void connection_opened(struct firefly_connection *c)
{
    struct firefly_channel_types types = FIREFLY_CHANNEL_TYPES_INITIALIZER;
    firefly_channel_types_add_decoder_type(&types,
        (labcomm_decoder_register_function)labcomm_decoder_register_lc_types_S__pong,
        (void (*)(void *, void *))handle_pong, NULL);
    pthread_mutex_lock(&lock);
    {
        connection = c;
        firefly_channel_open_auto_restrict(connection, types);
        pthread_cond_broadcast(&sig);
    }
    pthread_mutex_unlock(&lock);
}

/* Response to sent restr. req. */
static void chan_restr_info(struct firefly_channel *chan,
              enum restriction_transition restr)
{
    switch (restr) {
    case UNRESTRICTED:
        printf("unrestricted\n");
        break;
    case RESTRICTED:
        printf("restricted\n");
        break;
    case RESTRICTION_DENIED:
        printf("restr req denied\n");
        break;
    }
}

/* Incoming restr. req. */
bool chan_restr(struct firefly_channel *chan)
{
    return true;
}

static void chan_opened(struct firefly_channel *c)
{
    struct labcomm_encoder *enc;
    struct labcomm_decoder *dec;

    dec = firefly_protocol_get_input_stream(c);
    enc = firefly_protocol_get_output_stream(c);

    pthread_mutex_lock(&lock);
    {
        channel = c;
        pthread_cond_broadcast(&sig);
    }
    pthread_mutex_unlock(&lock);
}

static void chan_closed(struct firefly_channel *chan)
{
#if 0
    firefly_connection_close(firefly_channel_get_connection(chan));
    pthread_mutex_lock(&ping_done_lock);
    ping_done = true;
    pthread_cond_signal(&ping_done_signal);
    pthread_mutex_unlock(&ping_done_lock);
#endif
}

static void channel_error(struct firefly_channel *chan,
        enum firefly_error reason, const char *msg)
{
    if (reason == FIREFLY_ERROR_CHAN_REFUSED)
        printf("Channel was rejected.");
    err(1, "Channel error\n");
}

static struct firefly_connection_actions ping_actions = {
    .channel_opened        = chan_opened,
    .channel_closed        = chan_closed,
    .channel_recv          = NULL,    /* No channels are received. */
    .channel_error         = channel_error,
    .channel_restrict      = chan_restr,
    .channel_restrict_info = chan_restr_info,
    .connection_opened     = connection_opened
};

static void signal_handler(int signal)
{
    if (signal == SIGINT) {
        printf("Got signal, shutting down...\n");
        stop = 1;
        pthread_cond_broadcast(&sig);
    }
}

static short parse_port(char *s)
{
    char *tmp;
    short port;

    port = strtol(s, &tmp, 10);
    if (tmp == s || *tmp != '\0')
        err(1, "Give a *proper* port number as argument.\n");
    return port;
}

int main(int argc, char **argv)
{
    static struct firefly_event_queue *event_queue;
    struct firefly_transport_llp *llp;
    struct firefly_transport_connection *conn;
    struct labcomm_encoder *enc;
    struct labcomm_decoder *dec;
    const char *ip = ADDR;
    short port = PORT;
    short local_port = LOCAL_PORT;
    int res;

    for (int i = 1; i < argc-1; i += 2) {
        char *f = argv[i];
        char *v = argv[i+1];

        if (!strcmp(f, "-a"))
            ip = v;
        if (!strcmp(f, "-p"))
            port = parse_port(v);
        if (!strcmp(f, "-l"))
            local_port = parse_port(v);
    }
    printf("Remote LLP addr: %s:%d\n", ip, port);
    printf("Local  LLP port: %d\n", local_port);

    signal(SIGINT, signal_handler);

    event_queue = firefly_event_queue_posix_new(20);
    res = firefly_event_queue_posix_run(event_queue, NULL);
    if (res) err(1, "ERROR: starting event thread.");
    llp = firefly_transport_llp_udp_posix_new(local_port, NULL, event_queue);
    if (!llp) err(1, "ERROR: creating llp");
    res = firefly_transport_udp_posix_run(llp);
    if (res) err(1, "ERROR: starting reader/resend thread.\n");
    conn = firefly_transport_connection_udp_posix_new(
                    llp, ip, port,
                    FIREFLY_TRANSPORT_UDP_POSIX_DEFAULT_TIMEOUT);
    res = firefly_connection_open(&ping_actions, NULL, event_queue, conn);
    if (res < 0) fprintf(stderr, "PING ERROR: Open connection: %d.\n", res);

    pthread_mutex_lock(&lock);
    {
        puts("waiting for channel");
        while (!channel && !stop)
            pthread_cond_wait(&sig, &lock);
        if (stop) goto shutdown_connection;
        puts("channel open");
        dec = firefly_protocol_get_input_stream(channel);
        enc = firefly_protocol_get_output_stream(channel);
    }
    pthread_mutex_unlock(&lock);

    labcomm_encoder_register_proto_subscribe(enc);
    labcomm_encoder_register_proto_publish(enc);
    labcomm_encoder_register_lc_types_S__ping(enc);

    sleep(1);

    /* Publish on ping. */
    proto_publish pub;
    pub.topic = "S__ping";
    labcomm_encode_proto_publish(enc, &pub);

    /* Subscribe to pong. */
    proto_subscribe sub;
    sub.topic = "S__pong";
    labcomm_encode_proto_subscribe(enc, &sub);

    unsigned int cnt = 0;
    while (!stop) {
        lc_types_S__ping ping;
        char buf[32];

        snprintf(buf, sizeof(buf), "%d", cnt);
        ping.s = buf;
        cnt++;
        labcomm_encode_lc_types_S__ping(enc, &ping);
        sleep(1);
    }

    firefly_channel_close(channel);
shutdown_connection:
    firefly_transport_udp_posix_stop(llp);
    firefly_transport_llp_udp_posix_free(llp);
    firefly_event_queue_posix_free(&event_queue);
}
