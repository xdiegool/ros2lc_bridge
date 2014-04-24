                           ROS2LS_BRIDGE GENERATOR

					 Erik Jansson <erikjansson90@gmail.com>
				  Tommy Olofsson <tommy.olofsson.90@gmail.com>

NOTE
    As for now, the C++ and Python generators are separate so depending on
    which one you want, you should run either generator_c for C++ or generator
    for Python. This document assumes you will be running the C++ one.

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
    and clone the repository. You also have to checkout the vx branch in the
    LabComm repository since it depends on some new features there.

        $ cd ~/src
        $ git clone http://git.cs.lth.se/robotlab/labcomm-core.git labcomm
        $ cd labcomm
        $ git checkout -b vx --track origin/vx     # or just `git checkout vx`

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

    Firefly needs cmake to build (which probably should be installed already
    on Ubuntu). The steps for building is fairly simple:

        $ mkdir build && cd build   # in the firefly repository root
        $ cmake ../src              # look for "Found LABCOMM" in the output!
        $ make

    If LabComm wasn't found, go back and check that you put both repositories
    next to each other in a directory. The result of the build should be a
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
            <topics_in>
                <topic name="/ping" />
            </topics_in>

            <topics_out>
                <topic name="/pong" />
            </topics_out>
        </bridge>

    The root node has two required attributes, name and port which are fairly
    self-explanatory. Name is the name of the generated bridge and port is the
    port it should listen to. When generating a bridge, it will inspect the
    $ROS_PACKAGE_PATH and place the generated node in the first directory it
    can find which lies inside the user's home directory or /tmp if it can't
    find one. So if we have ~/src first in our $ROS_PACKAGE_PATH, the bridge
    would put the result of the abode configuration in ~/src/test_bridge.

    topics_in and topics_out are unfortunately a bit confusingly names (plans
    exists to switch them to better suited ones). topics_in lists the topics
    one wishes to import to the ROS system and topics_out lists the topics one
    wishes to export from the ROS system. This example config is taken from
    the pingpong example in the repository in which an external program
    publishes on /ping and subscribes to /pong. A ROS node does the opposite
    (subscribes on /ping and publishes on /pong) and echoes everything it
    hears on /ping to /pong (which will be heard be the external program).

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


