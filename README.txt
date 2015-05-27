!!! OUTDATED (will be updated shortly) !!!


QUICK NOTE ABOUT PYTHON
	In order to run the Python examples, you need to set your
	$PYTHONPATH to include LabComm.





                           ROS2LS_BRIDGE GENERATOR

					 Erik Jansson <erikjansson90@gmail.com>
				  Tommy Olofsson <tommy.olofsson.90@gmail.com>

NOTES
    As for now, the C++ and Python generators are separate so depending on
    which one you want, you should run either generator_c for C++ or generator
    for Python. This document assumes you will be running the C++ one.

    It is also worth noting that due to naming issues, an external program won't
    subscribe to or publish on the topic names directly (e.g. /ping or /pong)
    but will use normalized names in which the forward-slash is replaces with
    'S__'. This is sub-optimal and will be changed in the future so be aware
    of that.

INTRODUCTION
    This is a bridge that enables exporting and importing topics to/from a ROS
    system. The bridge sits inside the ROS system. Thus, traffic going towards
    other nodes in the ROS system is referred to traffic on the "inside" of
    the bridge, while traffic going towards other nodes outside the ROS system
    is referred to as traffic on the "outside" of the bridge.


                       +----------------------+
                       |         ROS          |
                       |                   +--------+
                       |               <== |        | <====
                       |               IN  | BRIDGE |  OUT
                       |               ==> |        | =====>
                       |                   +--------+
                       |                      |
                       +----------------------+

    Traffic on the outside is sent via a networking library called Firefly
    (see the DEPENDENCIES below on how to get this). This enables using
    different transport protocols (e.g. Ethernet, UDP and TCP). Communication
    on the inside (when communicating with ROS nodes) is performed with
    ROSComm over TCP.

DEPENDENCIES
    Naturally, the first dependency is ROS (information about installing ROS
    can be found on http://wiki.ros.org/). The rest of the dependencies are
    LabComm and Firefly which are described in the next few paragraphs.

    LabComm is a serialization library similar to Google's Protocol Buffers
    but, in addition, also has self-describing types. It can be found on
    http://git.cs.lth.se/robotlab/labcomm-core. LabComm consists of two parts,
    a compiler and libraries for different languages. To install LabComm,
    change to some directory where you have write permissions (I use ~/src)
    and clone the repository.

        $ cd ~/src
        $ git clone http://git.cs.lth.se/robotlab/labcomm-core.git labcomm
        $ cd labcomm

    Unfortunately, Labcomm doesn't have much documentation available in
    the repository. Here are some simple steps that should allow you to
    build the important parts. The compiler is written in Java so you need
    a working Java compiler (including ant). You also need make and a C
    comiler. On Ubuntu you could install these as:

        $ sudo apt-get install openjdk-6-jdk ant build-essential

    To build the compiler, simply run:

        $ make make-compiler

    When this is done, you should have a file called labComm.jar in the
    compiler directory. Next, the C library should be built:

        $ cd lib/c # from the repository root
        $ make

    This should produce a couple of files, among them liblabcomm.a and
    liblabcomm.so.1. It should be noted that in order for Firefly to find
    LabComm, its directory should be called labcomm and not labcomm-core.

    Next, Firefly should be built. It can be found at
    http://git.cs.lth.se/robotlab/firefly. The easiest way for Firefly to
    discover where the LabComm library is located is to keep the two
    repositories next to each other (i.e. LabComm in ~/src/labcomm and Firefly
    in ~/src/firefly). Unfortunately, the bridge depends on the vxworks branch
    in the Firefly repository as well.

        $ cd ~/src
        $ git clone http://git.cs.lth.se/robotlab/firefly.git
        $ cd firefly
        $ git checkout -b vxworks --track origin/vxworks

    Firefly needs cmake to build (which probably should be installed
    already on Ubuntu).  Cmake looks for the environment variable
    LABCOMM to find the LabComm root. Put the following in your
    ~/.bashrc and source it.

        $ export LABCOMM=~/src/labcomm

    Then the steps for building is fairly simple:

        $ mkdir build && cd build   # in the firefly repository root
        $ cmake ../src              # look for "Found LABCOMM" in the output!
        $ make

    The result of the build should be a
    couple of lib*.a files. The library is modularized so the core of the
    library is in libfirefly.a while the different transport layers are in
    libtransport-{1}-{2}.a where {1} is the transport protocol and {2} is the
    platform (e.g. libtransport-udp-posix.a).

    In order for the bridge generator to find LabComm and Firefly, it uses two
    environment variables (for now, might be improved in the future). LABCOMM
    should point to the LabComm repository's directory and FIREFLY should do
    the same for Firefly's directory. I.e., in this example we would have:

        $ export LABCOMM=~/src/labcomm
        $ export FIREFLY=~/src/firefly

    At this point, all dependencies should be satisfied.

INSTALLING
    There isn't much to install actually. The bridge generator can be found at
    http://git.cs.lth.se/robotlab/ros2lc_bridge and can be cloned from
    http://git.cs.lth.se/robotlab/ros2lc_bridge.git (which you probably
    already have done since you're reading this README).

        $ git clone http://git.cs.lth.se/robotlab/ros2lc_bridge.git
        $ cd ros2lc_bridge
        $ git checkout -b cpp --track origin/cpp

    The only requirement is that the path to generator directory must be put
    in the ROS_PACKAGE_PATH. E.g. in our example, we would prepend
    ~/src/ros2lc_bridge to our ROS_PACKAGE_PATH.

SIMPLE CONFIGURATION
    The generator is configured with a simple XML-file. In the examples
    directory of the repository, you will find some examples. A quick
    explanation of the basics follows:

        <bridge name="test_bridge" port="7357">
            <imports>
                <topic name="/ping" />
            </imports>

            <exports>
                <topic name="/pong" />
            </exports>
        </bridge>

    The root node has two required attributes, name and port which are fairly
    self-explanatory. Name is the name of the generated bridge and port is the
    port it should listen to. When generating a bridge, it will inspect the
    $ROS_PACKAGE_PATH and place the generated node in the first directory it
    can find which lies inside the user's home directory or /tmp if it can't
    find one. So if we have ~/src first in our $ROS_PACKAGE_PATH, the bridge
    would put the result of the abode configuration in ~/src/test_bridge.

    imports lists the topics one wishes to import to the ROS system and
    exports lists the topics one wishes to export from the ROS system. This
    example config is taken from the pingpong example in the repository in
    which an external program publishes on /ping and subscribes to /pong. A
    ROS node does the opposite (subscribes on /ping and publishes on /pong)
    and echoes everything it hears on /ping to /pong (which will be heard be
    the external program).

RUNNING BRIDGE

    The bridge can be run as:

        $ rosrun generator_c generator.py -c <path_to_config_file>

    It can also be run with the --help parameter to display info about other
    parameters. For example, the -f parameter can be used to force the
    generator to overwrite an existing bridge.

PINGPONG EXAMPLE
    First, one must start the ROS node (after the ROS master of course) in
    order for the type to be registered with the ROS master.  Assuming the
    examples directory is in $ROS_PACKAGE_PATH, you can start the ROS node
    with:

        $ cd examples/ros_pingpong && make
        $ rosrun ros_pingpong pingpong.py

    (If you don't have examples/ in your $ROS_PACKAGE_PATH, simply change to
    examples/ros_pingpong and run ./src/ros_pingpong/pingpong.py instead.)

    Next, the bridge should be generated:

        $ rosrun generator_c generator.py -c examples/pingpong_conf.xml

    And then built and started:

        $ cd <your-ros-ws-in-home>/test_bridge # ~/src/test_bridge for me
        $ make
        $ rosrun test_bridge main

    Lastly, we should build and run the ff_pingpong client:

        $ cd examples/ff_pingpong && make
        $ ./pingpong

FIREFLY DESCRIPTION
    Describing the entirety of Firefly is unfortunately a bit out of scope for
    this document but a brief explanation is given here. The idea of Firefly
    is to provide a framework for easily building networked applications that
    need to communicate typed data. I also makes it easy to change which
    transport protocol is used. Implementations for a variety of protocols are
    provided in the Firefly repository (e.g. UDP/TCP/Ethernet for POSIX and
    UDP for lwIP).

    A good example of using Firefly is the pingpong example client in
    examples/ff_pingpong. It uses signaling from callbacks a bit heavily so a
    stripped down version of only the necessary pieces are presented here.

    A callback function is registered for each type one wishes to receive. In
    this case, we only want to receive the response from /pong:

        static void handle_pong(lc_types_S__pong *pong, void *context)
        {
            printf("Got pong %s\n", pong->s);
        }

    Firefly has the concept of connections and channels. Each connection can
    contain multiple channels and each channel can have multiple LabComm types
    registered on it. When a connection is opened, a callback is received to
    allow the client to perform some setup. In this callback, the client
    should register all the types it would like to receive and send. This is
    done by adding them to the struct firefly_channel_types structure and
    passing that to the firefly_channel_open_auto_restrict() function.

        static void connection_opened(struct firefly_connection *c)
        {
            struct firefly_channel_types types = FIREFLY_CHANNEL_TYPES_INITIALIZER;
            firefly_channel_types_add_decoder_type(&types,
                (labcomm_decoder_register_function)labcomm_decoder_register_lc_types_S__pong,
                (void (*)(void *, void *))handle_pong, NULL);

            firefly_channel_types_add_encoder_type(&types,
                labcomm_encoder_register_proto_subscribe);
            firefly_channel_types_add_encoder_type(&types,
                labcomm_encoder_register_proto_publish);
            firefly_channel_types_add_encoder_type(&types,
                labcomm_encoder_register_lc_types_S__ping);

            pthread_mutex_lock(&lock);
            {
                connection = c;
                firefly_channel_open_auto_restrict(connection, types);
                pthread_cond_broadcast(&sig);
            }
            pthread_mutex_unlock(&lock);
        }

    In order to synchronize with the other end of the connection, Firefly uses
    a light-weight version of TCP's three-way handshake. When this is done,
    the client receives a callback with the newly opened channel:

        static void chan_opened(struct firefly_channel *c)
        {
            pthread_mutex_lock(&lock);
            {
                channel = c;
                pthread_cond_broadcast(&sig);
            }
            pthread_mutex_unlock(&lock);
        }

    Firefly supports a feature called restricted channels which prohibits any
    new type registrations. A restrict request can be initiated by either
    party and when one is received, a callback is called with the channel. If
    the client wishes to accept the restrict request, this callback should
    return true, otherwise it should return false.

        bool chan_restr(struct firefly_channel *chan)
        {
            return true;
        }

    The client that initiated the restriction will receive a callback when the
    restricted state has been entered/exited or denied by the other side.

        static void chan_restr_info(struct firefly_channel *chan,
                      enum restriction_transition restr)
        {
            switch (restr) {
            case UNRESTRICTED:
                printf("unrestricted\n");
                break;
            case RESTRICTED:
                printf("restricted\n");
                go = 1;
                break;
            case RESTRICTION_DENIED:
                printf("restr req denied\n");
                break;
            }
        }

    Either side can close the channel when he/she wishes to which will lead to
    the other side receiving a callback informing it that this channel was
    closed. No pointer to the provided argument can be saved since the data it
    points to will be freed once the callback returns.

        static void chan_closed(struct firefly_channel *chan) { }

    If an error occurs at any point, the client will be informed of it via the
    channel error callback. A message and an enum with the reason (defined in
    include/utils/firefly_error.h) is provided to help debugging and error
    recovery.

        static void channel_error(struct firefly_channel *chan,
                enum firefly_error reason, const char *msg)
        {
            printf("Channel error: %s\n", msg);
        }

    The struct firefly_connection_actions contains pointers to all the
    callbacks. This must be provided when initializing Firefly.

        static struct firefly_connection_actions ping_actions = {
            .channel_opened        = chan_opened,
            .channel_closed        = chan_closed,
            .channel_recv          = NULL,    /* No channels are received. */
            .channel_error         = channel_error,
            .channel_restrict      = chan_restr,
            .channel_restrict_info = chan_restr_info,
            .connection_opened     = connection_opened
        };

    The main function is comment along the way which should explain the
    structure. Please not that no error checks are made here, see
    examples/ff_pingpong for that.

        int main(int argc, char **argv)
        {
            static struct firefly_event_queue *event_queue;
            struct firefly_transport_llp *llp;
            struct firefly_transport_connection *t_conn;
            struct labcomm_encoder *enc;
            struct labcomm_decoder *dec;

            /* Firefly uses an event queue to drive the library. */
            event_queue = firefly_event_queue_posix_new(20);
            /* The POSIX provides helper functions to run the event loop. */
            firefly_event_queue_posix_run(event_queue, NULL);

            /* LLP (Link Layer Port) is equivalent to an Ethernet port and
               connections live on the LLP. */
            llp = firefly_transport_llp_udp_posix_new(local_port, NULL,
                            event_queue);

            /* The POSIX layer also provides helper functions to run the
               read/resend loop which reads data from the network and resends
               lost data respectively. */
            firefly_transport_udp_posix_run(llp);

            /* Next we need to create some glue between the connection and
             * LLP. */
            t_conn = firefly_transport_connection_udp_posix_new(
                            llp, "127.0.0.1", 7357,
                            FIREFLY_TRANSPORT_UDP_POSIX_DEFAULT_TIMEOUT);

            /* Next we open a connection to the bridge. */
            firefly_connection_open(&ping_actions, NULL, event_queue, t_conn);

            /* Next we wait for the channel to be opened and restricted. The
               restricted part is important to wait for since there can be
               race conditions otherwise. */
            pthread_mutex_lock(&lock);
            {
                puts("waiting for channel");
                while (!go && !stop)
                    pthread_cond_wait(&sig, &lock);
                if (stop) goto shutdown_connection;
                puts("channel open");
                dec = firefly_protocol_get_input_stream(channel);
                enc = firefly_protocol_get_output_stream(channel);
            }
            pthread_mutex_unlock(&lock);

            /* We want to publish on /ping so we tell the bridge that by
               encoding a proto_publish type with the topic member set to the
               name of the topic. */
            proto_publish pub;
            pub.topic = "S__ping";
            labcomm_encode_proto_publish(enc, &pub);

            /* Likewise we want to subscribe to /pong. */
            proto_subscribe sub;
            sub.topic = "S__pong";
            labcomm_encode_proto_subscribe(enc, &sub);

            /* Now we have a channel and can start sending stuff. */
            unsigned int cnt = 0;
            while (!stop) {
                lc_types_S__ping ping;
                char buf[32];

                snprintf(buf, sizeof(buf), "%d", cnt++);
                ping.s = buf;
                labcomm_encode_lc_types_S__ping(enc, &ping);
                sleep(1);
            }

            /* Close and free channel and connection when we're done. */
            firefly_channel_close(channel);
        shutdown_connection:
            firefly_transport_udp_posix_stop(llp);
            firefly_transport_llp_udp_posix_free(llp);
            firefly_event_queue_posix_free(&event_queue);
        }

