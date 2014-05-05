import os
from tempfile import mkstemp
import shutil
from config_file import *
from collections import OrderedDict

from utils import *


CONVERSION_FILENAME = 'conv.cpp'
CLIENT_FILENAME     = 'client.h'
CONFIG_FILENAME     = 'conf.h'
GENBRIDGE__FILENAME = 'gen_bridge.cpp'


## Boilerplate content to output.
#################################

cmake_add_exec_begin = '''
set(CMAKE_C_FLAGS "${CMAKE_C_FLAGS} -DLABCOMM_CONSTRUCTOR= ")
rosbuild_add_executable(main
    src/hack.c
    src/lc_types.c
    src/proto.c'''

cmake_custom_conv = '''
    src/{f}'''

cmake_add_exec_end = '''
    src/client.cpp
    src/bridge.cpp
)
target_link_libraries(main {lc_lib} {trans_lib} {ff_lib})
include_directories({lc_inc} {ff_inc})
'''

conf_content = '''
#ifndef {pkg_name}_CONF_C
#define {pkg_name}_CONF_C

#include "proto.h"
#include "lc_types.h"

#define PKG_NAME "{pkg_name}"
#define PORT     ({port})
#define SLASHSUB "{slash_substitute}"

void init_signatures(void)
{{
	init_proto__signatures();
	init_lc_types__signatures();
}}
#endif
'''

client_file_begin = '''
#ifndef {pkg_name}_CLIENT_C
#define {pkg_name}_CLIENT_C

#include "ros/ros.h"

#include <boost/thread.hpp>
#include <boost/thread/mutex.hpp>
#include <boost/thread/locks.hpp>
#include <set>
#include <string>
#include <vector>

extern "C" {{

#include <labcomm.h>
#include <labcomm_default_memory.h>

/* Firefly includes */
#include <protocol/firefly_protocol.h>
#include <transport/firefly_transport_udp_posix.h>
#include <utils/firefly_event_queue.h>
#include <utils/firefly_event_queue_posix.h>

#include "proto.h"
#include "lc_types.h"

void alloc_array(void **, size_t, size_t);
}}

'''

client_class_include = '''
#include "{topic_type}.h"
'''

client_lc_callback_def = '''
void {topic_name}_lc_callback({lc_ns}_{type_name} *sample, void *ctx);
'''

client_service_callback_def = '''
static void handle_srv_{lc_name}(lc_types_{lc_par_type} *s, void* v);
'''


client_class_begin = '''
class client {
	ros::NodeHandle *n;
	struct labcomm_decoder *dec;
	struct labcomm_encoder *enc;
	boost::mutex enc_lock;
	std::set<std::string> active_topics;

public:
	bool close;
	std::vector<boost::shared_ptr<boost::thread> > service_threads;
'''

client_conv_member = '''
	{type_name} {name};'''

client_conv_cache = '''
	std::set<std::string> conv_{i}_cached;'''

client_ros_subscriber_members = '''
	ros::Subscriber {topic_name}Sub;
	void {topic_name}_ros_callback(const {topic_type}::ConstPtr& msg);
'''

client_ros_service_members = '''
	void call_srv_{srv_name}({cpp_type} *msg);
'''

client_ros_publisher_member = '''
	ros::Publisher {topic_name}Pub;
'''

client_functions = '''
	client(ros::NodeHandle *n);
	~client();

	void set_encoder(struct labcomm_encoder *enc);
	void set_decoder(struct labcomm_decoder *dec);
	void run();
	void handle_subscribe(proto_subscribe *subs);
	void handle_publish(proto_publish *pub);

	void setup_exports(struct firefly_channel_types *types) {
'''

client_subscribe_reg = '''
		{topic_name}Sub = n->subscribe("{ros_topic_name}", 1, &client::{topic_name}_ros_callback, this);
'''
client_enc_reg = '''
		firefly_channel_types_add_encoder_type(types,
			labcomm_encoder_register_{lc_ns}_{name});
'''

client_stat_begin = '''
	void setup_static() {
'''

setup_imports_pub_begin = '''
	void setup_imports(struct firefly_channel_types *types) {
'''

setup_imports_pub = '''
		{topic_name}Pub = n->advertise<{topic_type}>("{topic}", 1);
'''

setup_imports_dec_reg = '''
		firefly_channel_types_add_decoder_type(types,
				(labcomm_decoder_register_function)labcomm_decoder_register_{lc_ns}_{lc_name},
				(void (*)(void *, void *)) {name}_lc_callback, this);
'''

subscriber_cb_fn_begin = '''
void client::{topic_name}_ros_callback(const {topic_type}::ConstPtr& msg)
{{
'''

custom_dst_var_def = '''
	{typ} *{name} = NULL;
	bool should_send_{name} = true;
'''

custom_examine_cache = '''
	should_send_{name} = should_send_{name}
			&& conv_{i}_cached.find("{ros_topic}") != conv_{i}_cached.end();
'''

custom_examine_cache_custom = '''
	should_send_{name} = '''

custom_set_add = '''
	conv_{i}_cached.insert("{topic}");
'''

custom_replace = '''
	{name}_val.reset();
	{name}_val = msg;
'''

custom_replace_lc = '''
	labcomm_copy_free_{lc_ns}_{name}(labcomm_default_memory, &c->{varname}_val);
	labcomm_copy_{lc_ns}_{name}(labcomm_default_memory, &c->{varname}_val, sample);
'''

custom_call_begin = '''
	{conv_fn}('''

custom_should_send = '''
	if (active_topics.find("{ros_name}") != active_topics.end()
		&& {name} && should_send_{name}) {{
'''
custom_should_send_topic = '''
	if ({name} && should_send_{name}) {{
'''


custom_send_clear_set = '''
	conv_{i}_cached.clear();
'''

custom_reset = '''
	{name}_val.reset();
'''

subscriber_type_def = '''
	// Convert received ROS data.
	if (active_topics.find("{ros_name}") != active_topics.end()) {{
		lc_types_{topic_name} conv;
'''


subscriber_cb_fn_end = '''
}
'''

lc2ros_cb_fn_begin = '''
void {topic_name}_lc_callback({lc_ns}_{type_name} *sample, void *ctx)
{{
	client *c = (client *) ctx;
'''

lc2ros_cb_def = '''
	{cpp_topic_type} msg;
'''

lc2ros_cb_fn_end = '''
	c->{topic_name}Pub.publish(msg);
}}'''

service_call_func = '''
static void handle_srv_{lc_name}(lc_types_{lc_par_type} *s, void* v)
{{
	client *c = (client *) v;
	{cpp_type} *msg = new {cpp_type}();
'''

service_call_start_thread = '''
	boost::shared_ptr<boost::thread> t(new boost::thread(&client::call_srv_{lc_name}, c, msg));
	c->service_threads.push_back(t);
}}
'''

service_call_callback_begin = '''
void client::call_srv_{lc_name}({cpp_type} *msg)
{{
	ros::ServiceClient client;
	client = n->serviceClient<{cpp_type}>("{srv_name}");
	if (client.call(*msg)) {{
		// TODO: convert back to LC.
		lc_types_{lc_ret_type} res;
'''

service_call_callback_end = '''
		boost::lock_guard<boost::mutex> enc_guard(enc_lock);
		labcomm_encode_lc_types_{lc_ret_type}(enc, &res);
	}} else {{
		//TODO: Fail
	}}

	delete msg;
}}
'''

end_fn = '}'

class_end = '''
};

#endif
'''

def create_pkg(ws, name, deps, force, lc_file, conf_file, conv_file,
               client_file, static_conns_file, mlc, mpy, conversions):
    """Create ROS package in the first dicectory in $ROS_PACKAGE_PATH, or /tmp/, unless explicitly specified."""
    if not ws:
        pkg_path = os.environ.get('ROS_PACKAGE_PATH')
        for path in pkg_path.split(':'):
            if 'home' in path.split(os.sep):
                ws = path
                break
    if not ws:
        ws = '/tmp'
        print(orange("Defaulting to /tmp as workspace."))

    d = os.path.join(ws, name)
    if force and os.path.exists(d):
        shutil.rmtree(d)

    depstr = ' '.join(['roslib', 'roscpp'] + list(deps))
    sh('cd %s && roscreate-pkg %s %s' % (ws, name, depstr))
    try:
        lcdir = os.path.join(d, 'lc')
        srcdir = os.path.join(d, 'src')
        skeldir = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'skel')
        skelcodedir = os.path.join(skeldir, 'cpp')
        skeltypesdir = os.path.join(skeldir, 'lc')

        # Move created type definitions to generated package.
        os.mkdir(lcdir)
        os.rename(lc_file, os.path.join(lcdir, 'lc_types.lc'))
        # Copy skeleton code to package.
        for f in os.listdir(skelcodedir):
            shutil.copy2(os.path.join(skelcodedir, f), srcdir);
        # Copy types for bridge commands to package.
        for f in os.listdir(os.path.join(skeldir, 'lc')):
            shutil.copy2(os.path.join(skeltypesdir, f), lcdir);
        # Move generated configuration code to package.
        os.rename(conf_file, os.path.join(srcdir, CONFIG_FILENAME))
        # Move generated conversion code to package.
        os.rename(conv_file, os.path.join(srcdir, CONVERSION_FILENAME))
        # Move generated client definition to package.
        os.rename(client_file, os.path.join(srcdir, CLIENT_FILENAME))
        # Move generated client definition to package.
        os.rename(static_conns_file, os.path.join(srcdir, GENBRIDGE__FILENAME))

        # Make sure LabComm and Firefly env exists.
        lcpath = os.environ.get('LABCOMM')
        if not lcpath:
            raise GeneratorException('Env. $LABCOMM not set, won\'t be able to'
                                     ' compile node. (Should be set to LabComm'
                                     ' repository path.)')
        ffpath = os.environ.get('FIREFLY')
        if not ffpath:
            raise GeneratorException('Env. $FIREFLY not set, won\'t be able to'
                                     ' compile node. (Should be set to Firefly'
                                     ' repository path.)')

        for lc in mlc:
            shutil.copy(lc, lcdir)
        # Compile LabComm files.
        for f in os.listdir(lcdir):
            name = os.path.splitext(f)[0]
            sh('java -jar {jar} -C --c={dest}.c --h={dest}.h {src}.lc'.format(
                    jar=lcpath + '/compiler/labComm.jar',
                    dest=os.path.join(srcdir, name),
                    src=os.path.join(lcdir, name)))

        # Copy user stuff for manual conversion.
        for py in mpy:
            shutil.copy(py, srcdir)

        with open('%s/CMakeLists.txt' % d, 'a') as bf:
            bf.write(cmake_add_exec_begin)

            for c in conversions:
                f = os.path.basename(c.lc_path).replace('.lc', '.c')
                bf.write(cmake_custom_conv.format(f=f))

            bf.write(cmake_add_exec_end.format(lc_lib=lcpath+'/lib/c/liblabcomm.a',
                                               lc_inc=lcpath+'/lib/c',
                                               ff_lib=ffpath+'/build/libfirefly-werr.a',
                                               trans_lib=ffpath+'/build/libtransport-udp-posix.a',
                                               ff_inc=ffpath+'/include'))

    except Exception as e:
        raise e
    return d

def write_conf(f, bname, port):
    '''Writes the conf.h header file.

    :param f: the file to write the defines to.
    :param bname: the name of the created package.
    :param port: the port the bridge should run on.
    '''
    f.write(conf_content.format(pkg_name=bname, port=port,
                                slash_substitute=SLASHSUB))

def in_custom(topic, conversions):
    '''When converting to or from a topic, check if there is a custom
    conversion specified.
    '''
    for i,c in enumerate(conversions):
        # When converting to a topic from LabComm sample(s).
        if topic in c.topic_dsts:
            return i, c
        # When converting from a topic to LabComm sample(s).
        if topic in c.topic_srcs:
            return i,c
    return -1,None


def write_conv(clientf, convf, pkg_name, imports, exports,
               topics_types, services, service_defs, conversions, stat_conns):
    '''Writes the definition of the client class as well as conversion code.

    The client class handles subscribing to and publishing on topics as well as
    converting received messages/samples and sending them out the opposite way
    (i.e.  ROS->LC or LC->ROS).

    :param clientf: the file to write the client definition to.
    :param convf: the file to write converision code to.
    :param pkg_name: string with the name of the package.
    :param imports: a list topics imported into the ROS system.
    :param exports: a list topics exported from the ROS system.
    :param topics_types: a dict of topic names => topic types.
    :param services: a list of services that should be exported.
    :param service_defs: a dict of a service=>type mappings
    :param conversions: a list of conversions specified by the user (obsolete in C++)
    '''

    def write_once(f, fmt, key, items):
        '''Helper function to write duplicated items only once. It can only
        handle 1 param in the format string.

        :param f: the file to write to.
        :param fmt: the format string to use.
        :param key: the key to replace in the format string.
        :param items: the list of items to write.
        '''
        written = set()
        tmp = {}
        for i in items:
            if i not in written:
                written.add(i)
                tmp[key] = i
                f.write(fmt.format(**tmp))

    def extract_lc_ns(lc, suf):
        return basename(lc).replace('.lc', suf)

    # Write define stuff
    clientf.write(client_file_begin.format(pkg_name=pkg_name))

    # Write one include per custom conversion type.
    tmp = [extract_lc_ns(c.lc_path, '.h') for c in conversions]
    write_once(clientf, 'extern "C" {{\n#include "{f}"\n}}\n', 'f', tmp)

    # Write one include per msg type needed.
    tmp = [topics_types[t] for t in exports + imports]
    write_once(clientf, client_class_include, 'topic_type', tmp)

    # Write one include per service type needed.
    tmp = [get_srv_type(s) for s in services]
    write_once(clientf, '#include "{name}.h"\n', 'name', tmp)

    # Include custom conversion code.
    tmp = [basename(c.py_path) for c in conversions]
    write_once(convf, '#include "{f}"\n', 'f', tmp)

    # Write one function declaration (LC callback) per publisher
    decl_written = set()
    for topic in imports:
        i, custom = in_custom(topic, conversions)
        if not custom: # Auto conversion
            topic_name = msg2id(topic)
            clientf.write(client_lc_callback_def.format(topic_name=topic_name,
                                                        lc_ns='lc_types',
                                                        type_name=topic_name))
        else: # Custom conversion
            lc_ns = extract_lc_ns(custom.lc_path, '')
            for t in custom.sample_srcs:
                # t[0] is sample type, t[1] is pseudo-topic
                if t[1] in decl_written:
                    continue
                decl_written.add(t[1])
                clientf.write(client_lc_callback_def
                              .format(topic_name=msg2id(t[1]),
                                      lc_ns=lc_ns,type_name=t[0]))
    del decl_written

    # Write one function declaration (LC callback) per service.
    for service in services:
        lc_name = msg2id(service)
        lc_par_type = lc_name + SRV_PAR_SUFFIX
        clientf.write(client_service_callback_def.format(lc_name=lc_name,
                                                         lc_par_type=lc_par_type))

    # Write class definition and some members.
    clientf.write(client_class_begin)

    for i,c in enumerate(conversions):
        clientf.write('\n\t// Conv number {i}'.format(i=i))
        if len(c.topic_srcs + c.sample_srcs) > 1:
            clientf.write(client_conv_cache.format(i=i))
            # for s in c.sample_dsts:
            #     clientf.write(client_conv_cache.format(name=msg2id(s[1])))

            # for t in c.topic_dsts:
            #     clientf.write(client_conv_cache.format(name=msg2id(t)))

        for t in c.topic_srcs:
            topic_type = topics_types[t].replace('/', '::') + '::ConstPtr'
            clientf.write(client_conv_member.format(type_name=topic_type,
                                                    name=msg2id(t) + '_val'))
        # TODO: Do some magic with LabComm samples as well? Currently we can't
        # since we only get a pointer in the LabComm callback and the data is
        # freed once the callback returns. (And LabComm types can contain
        # pointers to arrays so we basically have to add a deep-copy function
        # to the LabComm compiler to get this to work.)
        for s in c.sample_srcs:
            lc_ns = extract_lc_ns(c.lc_path, '')
            ptopic = msg2id(s[1])
            clientf.write(client_conv_member.format(type_name=lc_ns+'_'+s[0],
                                                    name=ptopic+'_val'))

    # Write class members (ROS callback) for each subscriber.
    for topic in exports:
        topic_name = msg2id(topic)
        topic_type_cpp = topics_types[topic].replace('/', '::')
        clientf.write(client_ros_subscriber_members.format(topic_name=topic_name,
                                                           topic_type=topic_type_cpp))

    for topic in imports:
        topic_name = msg2id(topic)
        topic_type = topics_types[topic].replace('/', '::')
        clientf.write(client_ros_publisher_member.format(topic_name=topic_name,
                                                         topic_type=topic_type))
    for service in services:
        lc_name = msg2id(service)
        lc_ret_type = lc_name + SRV_RET_SUFFIX
        cpp_type = get_srv_type(service).replace('/', '::')
        clientf.write(client_ros_service_members.format(srv_name=lc_name,
                                                        cpp_type=cpp_type))

    # Write constructor and other function declarations in the client class.
    clientf.write(client_functions)

    # Write ROS subscriptions and LabComm registrations (i.e. ROS->LC stuff).
    reg_written = set()
    for topic in exports:
        if topic in reg_written:
            continue
        i, custom = in_custom(topic, conversions)
        if custom:
            lc_ns = extract_lc_ns(custom.lc_path, '')
            for t in custom.topic_srcs:
                reg_written.add(t)
                clientf.write(client_subscribe_reg.format(topic_name=msg2id(t),
                                                          ros_topic_name=t))
            for s in custom.sample_dsts:
                clientf.write(client_enc_reg.format(lc_ns=lc_ns, name=s[0]))
        else:
            lc_topic = msg2id(topic)
            clientf.write(client_subscribe_reg.format(topic_name=lc_topic,
                                                      ros_topic_name=topic))
            clientf.write(client_enc_reg.format(lc_ns='lc_types',
                                                name=lc_topic))

    clientf.write('\t' + end_fn)

    clientf.write(setup_imports_pub_begin)
    reg_written = set()
    for topic in imports:
        if topic in reg_written:
            continue
        i, custom = in_custom(topic, conversions)
        if custom:
            lc_ns = extract_lc_ns(custom.lc_path, '')
            for t in custom.topic_dsts:
                reg_written.add(t)
                topic_type = topics_types[t].replace('/', '::')
                clientf.write(setup_imports_pub.format(topic_name=msg2id(t),
                                                       topic_type=topic_type,
                                                       topic=t))
            for s in custom.sample_srcs:
                clientf.write(setup_imports_dec_reg.format(lc_ns=lc_ns,
                                                           lc_name=msg2id(s[0]),
                                                           name=msg2id(s[1])))
        else:
            name = msg2id(topic)
            # Get corresponding C++ type.
            topic_type = topics_types[topic].replace('/', '::')
            clientf.write(setup_imports_pub.format(topic_name=name,
                                                   topic_type=topic_type,
                                                   topic=topic))
            clientf.write(setup_imports_dec_reg.format(name=name,
                                                       lc_name=name,
                                                       lc_ns='lc_types'))
    clientf.write('\t' + end_fn)

    clientf.write('\n\tvoid setup_services() {\n')
    for service in services:
        name = msg2id(service)
        clientf.write('\t\tlabcomm_encoder_register_lc_types_{name}_RET(enc);\n'
                      .format(name=name))
        clientf.write('\t\tlabcomm_decoder_register_lc_types_{name}_PAR(dec, handle_srv_{name}, this);\n'
                      .format(name=name))
    clientf.write('\t' + end_fn)

    # Write setup for static connections.
    clientf.write(client_stat_begin)

    static_conns_setup = '''
		active_topics.insert("{name}");
		std::cout << "{name}" << std::endl;
'''

    for conn in stat_conns:
        subs = stat_conns[conn]['subscribe']
        pubs = stat_conns[conn]['publish']

        # Populate subscriber list.
        for pubsub in subs + pubs:
            clientf.write(static_conns_setup.format(name=pubsub))

    clientf.write(end_fn);

    # Write end-of-class.
    clientf.write(class_end)

    # Write LC callbacks for services.
    for service in services:
        lc_name = msg2id(service)
        lc_par_type = lc_name + SRV_PAR_SUFFIX
        lc_ret_type = lc_name + SRV_RET_SUFFIX
        cpp_type = get_srv_type(service).replace('/', '::')
        clientf.write(service_call_func.format(lc_name=lc_name,
                                               lc_par_type=lc_par_type,
                                               lc_ret_type=lc_ret_type,
                                               cpp_type=cpp_type,
                                               ros_name=service))
        definition = service_defs[get_srv_type(service)]
        convert_type(clientf, definition[0], 'to_ros', lc_ptr=False,
                     ros_ptr=False, ros_varname='msg->request', lc_varname='s')
        clientf.write(service_call_start_thread.format(lc_name=lc_name))
        # clientf.write('}\n')

    for conv in conversions:
        print 'lc path:       ', conv.lc_path
        print 'py path:       ', conv.py_path
        print 'conv func:     ', conv.py_func
        print 'trig policy:   ', conv.trig_policy
        print 'source samples:', conv.sample_srcs
        print 'source topics: ', conv.topic_srcs
        print 'dest samples:  ', conv.sample_dsts
        print 'dest topics:   ', conv.topic_dsts
        print ''

    def write_custom_out(f, topicsample, is_topic, num, custom):
        lc_ns = extract_lc_ns(custom.lc_path, '')
        tmp = ''
        if is_topic:
            tmp = topicsample
        else:
            tmp = topicsample[1]
        if len(custom.sample_srcs + custom.topic_srcs) > 1:
            # Add the incomming topic/sample to the set of cached values.
            f.write(custom_set_add.format(i=num, topic=tmp))

        # Call custom conversion code.
        def write_fn_call(custom, fn, src=True, dst=True):
            f.write(custom_call_begin.format(conv_fn=fn))
            var = '&{var}, '
            if not is_topic:
                var = '&c->{var}, '
            if len(custom.topic_dsts + custom.sample_dsts) > 0:
                if src:
                    to = len(custom.topic_srcs)
                    if len(custom.sample_srcs) == 0 and not dst:
                        to = -1
                    [f.write('{var}.get(), '.format(var=msg2id(t) + '_val'))
                            for t in custom.topic_srcs[:to]]
                    if to == -1:
                        var = msg2id(custom.topic_srcs[-1])
                        f.write('{var}.get());'.format(var=var + '_val'))
                    [f.write(var.format(var=msg2id(s[1]) + '_val'))
                            for s in custom.sample_srcs]
                    if (not to == -1 and
                        len(custom.topic_dsts) == 0 and
                        len(custom.sample_dsts) == 0):
                        var = msg2id(custom.sample_srcs[-1][1])
                        f.write('&{var});'.format(var=var + '_val'))
                if dst:
                    to = len(custom.topic_dsts)
                    if len(custom.sample_dsts) == 0:
                        to = -1
                    [f.write('&{var}, '.format(var=msg2id(t)))
                            for t in custom.topic_dsts[:to]]
                    if to == -1:
                        var = msg2id(custom.topic_dsts[-1])
                        f.write('&{var});'.format(var=var))
                    [f.write('&{var}, '.format(var=msg2id(s[1])))
                            for s in custom.sample_dsts[:-1]]
                    if not to == -1:
                        var = msg2id(custom.sample_dsts[-1][1])
                        f.write('&{var});'.format(var=var))

        def write_defs(custom, items, is_topic):
            '''Helper to write dst definitions for both samples and topics.'''
            for tmp in items:
                typ = ''
                name = ''
                if is_topic:
                    typ = topics_types[tmp].replace('/', '::')
                    name = msg2id(tmp)
                else:
                    typ = lc_ns + '_' + tmp[0]
                    name = msg2id(tmp[1])
                f.write(custom_dst_var_def.format(typ=typ,name=name))
                size = len(custom.topic_srcs + custom.sample_srcs)
                if custom.trig_policy['type'] == 'full' and size > 1:
                    for t in custom.topic_srcs:
                        f.write(custom_examine_cache.format(name=name,
                                                            ros_topic=t,
                                                            i=num))
                    for s in custom.sample_srcs:
                        f.write(custom_examine_cache.format(name=name,
                                                            ros_topic=s[1],
                                                            i=num))
                elif custom.trig_policy['type'] == 'custom':
                    func = custom.trig_policy['func']
                    f.write(custom_examine_cache_custom.format(name=name,
                                                               func=func))
                    write_fn_call(custom, func, dst=False)


        # Write definitions for destinations.
        write_defs(custom, custom.sample_dsts, False)
        write_defs(custom, custom.topic_dsts, True)

        # Reset the old value pointer and assign the new one.
        if is_topic:
            f.write('\n\t// Reset shared ptr with new value.')
            f.write(custom_replace.format(name=msg2id(topicsample)))
        else:
            f.write('\n\t// Reset member with new value.')
            name = msg2id(topicsample[0])
            varname = msg2id(topicsample[1])
            f.write(custom_replace_lc.format(lc_ns=lc_ns,name=name,
                                             varname=varname))
        write_fn_call(custom, custom.py_func)

        # Write send code.
        def write_send_ts(f, custom, items, is_topic):
            for tmp in items:
                typ = ''
                name = ''
                if is_topic:
                    name = msg2id(tmp)
                    # TODO: Write send code for topics.
                    f.write(custom_should_send_topic.format(name=name))
                    f.write('\t\tc->{name}Pub.publish(*{name});\n'
                            .format(name=name))
                else:
                    typ = tmp[0]
                    name = msg2id(tmp[1])
                    f.write(custom_should_send.format(ros_name=tmp[1],name=name))
                    write_send(convf, typ, name, lc_prefix=lc_ns, indent=2)
                # Clear variables if we are in full trigger mode.
                f.write('\t}\n')
        write_send_ts(convf, custom, custom.sample_dsts, False)
        write_send_ts(convf, custom, custom.topic_dsts, True)
        size = len(custom.sample_srcs + custom.topic_srcs)
        if custom.trig_policy['type'] == 'full' and size > 1:
            for t in custom.topic_dsts:
                name = msg2id(t)
                convf.write(custom_should_send_topic.format(name=name))
                convf.write(custom_send_clear_set.format(i=num))
                convf.write('\t}\n')
            for s in custom.sample_dsts:
                name = msg2id(s[1])
                convf.write(custom_should_send.format(ros_name=s[1],name=name))
                convf.write(custom_send_clear_set.format(i=num))
                convf.write('\t}\n')

        # Write call to free function.
        write_fn_call(custom, custom.py_func + '_free', src=False)
        # f.write('\t{free_fn}('.format(free_fn=custom.py_func + '_free'))
        # if len(custom.sample_dsts + custom.topic_dsts) > 0:
        #     for s in custom.sample_dsts[:-1]: # All but last var
        #         f.write('&{var}, '.format(var=msg2id(s[1])))
        #     var = msg2id(custom.sample_dsts[-1][1])
        #     f.write('&{var});'.format(var=var))
        f.write('\n}\n')


    # Write subscriber callbacks that converts to LabComm samples.
    for topic in exports:
        topic_name = msg2id(topic)
        topic_type = topics_types[topic]
        topic_type_cpp = topic_type.replace('/', '::')
        convf.write(subscriber_cb_fn_begin.format(topic_name=topic_name,
                                                  topic_type=topic_type_cpp))
        # Write conversion from ROS to LabComm.
        free_list = []
        i, custom = in_custom(topic, conversions)
        if custom:
            write_custom_out(convf, topic, True, i, custom)
        else:
            convf.write(subscriber_type_def.format(ros_name=topic,topic_name=topic_name))
            free_list = convert_type(convf, get_def(topic_type), 'to_lc',
                                     lc_ptr=False, ros_ptr=True, ros_varname='msg',
                                     lc_varname='conv')
            write_send(convf, topic, name='&conv')
            write_free(convf, free_list)
            convf.write('\t}\n')
            convf.write(subscriber_cb_fn_end)

    # Write LabComm callbacks that converts to ROS msgs.
    custom_topics_done = set()
    for topic in imports:
        if topic in custom_topics_done:
            return
        i, custom = in_custom(topic, conversions)
        if custom:
            [custom_topics_done.add(t) for t in custom.topic_dsts]
            convf.write('// ' + msg2id(topic) + '\n')
            # f.write(lc2ros_cb_fn_begin.format(topic_name=msg2id(s[1]),
            #                                   type_name=s[0], lc_ns=lc_ns))
            for s in custom.sample_srcs:
                convf.write(lc2ros_cb_fn_begin.format(topic_name=msg2id(s[1]),
                                                      type_name=s[0],
                                                      lc_ns=lc_ns))
                write_custom_out(convf, s, False, i, custom)
        else:
            definition = get_def(topics_types[topic])
            cpp_type = topics_types[topic].replace('/', '::')
            name = msg2id(topic)
            convf.write(lc2ros_cb_fn_begin.format(lc_ns='lc_types',
                                                  topic_name=name,
                                                  type_name=name))
            convf.write(lc2ros_cb_def.format(cpp_topic_type=cpp_type))
            convert_type(convf, definition, 'to_ros', lc_ptr=True, ros_ptr=False,
                         ros_varname='msg', lc_varname='sample')
            convf.write(lc2ros_cb_fn_end.format(topic_name=name))

    # Write LabComm callbacks that converts to ROS msgs.
    for service in services:
        ros_type = get_srv_type(service)
        definition = service_defs[ros_type]
        lc_name = msg2id(service)
        lc_par_type = lc_name + SRV_PAR_SUFFIX
        lc_ret_type = lc_name + SRV_RET_SUFFIX
        cpp_type = ros_type.replace('/', '::')
        convf.write(service_call_callback_begin.format(lc_name=lc_name,
                                                       srv_name=service,
                                                       lc_par_type=lc_par_type,
                                                       lc_ret_type=lc_ret_type,
                                                       cpp_type=cpp_type))
        convert_type(convf, definition[1], 'to_lc', lc_ptr=False,
                ros_ptr=False, ros_varname='msg->response', lc_varname='res')
        convf.write(service_call_callback_end.format(lc_name=lc_name,
                                                     lc_ret_type=lc_ret_type))



conversions = {
    'to_ros': {
        '': ('', False),
        'default': ('\t{ros}.{name} = {lc}->{name};\n', False),
        'ddefault': ('\t{ros}.{rosname} = {lc}->{lcname};\n', False),
        'array': {
            'default': ('\t{ros}.{name}[i] = {lc}->{name}.a[i];\n', False),
            'string': ('\t\t{ros}.{name}.push_back({lc}->{name}.a[i]);\n', False),
            'time': (('\t\t{ros}.{name}[i].sec = {lc}->{name}.a[i].secs;\n'
                      '\t\t{ros}.{name}[i].nsec = {lc}->{name}.a[i].nsecs;\n'),
                      False),
            'alloc': (('\t{ros}.{name}.clear();\n'
                       '\tfor (int i = 0; i < {lc}->{name}.n_0; i++) {{\n'),
                       False),
            'end': ('\t}}', False)
        },
        'time': (('\t{ros}.{name}.sec = {lc}->{name}.secs;\n'
                  '\t{ros}.{name}.nsec = {lc}->{name}.nsecs;\n'), False),
        'ttime': (('\t{ros}.{rosname}.sec = {lc}->{lcname}.secs;\n'
                  '\t{ros}.{rosname}.nsec = {lc}->{lcname}.nsecs;\n'), False),
        'string': ('\t{ros}.{name} = {lc}->{name};\n', False),
        'sstring': ('\t{ros}.{rosname} = {lc}->{lcname};\n', False)
    },
    'to_lc': {
        '': ('', False),
        'default': ('\t{lc}.{name} = {ros}.{name};\n', False),
        'ddefault': ('\t{lc}.{lcname} = {ros}.{rosname};\n', False),
        'array': {
            'default': ('\t{lc}.{name}.a[i] = {ros}.{name}[i];\n', False),
            'string': ('\t\t{lc}.{name}.a[i] = strdup({ros}.{name}[i].c_str());\n', True),
            'time': (('\t\t{lc}.{name}.a[i].secs = {ros}.{name}[i].sec;\n'
                      '\t\t{lc}.{name}.a[i].nsecs = {ros}.{name}[i].nsec;\n'),
                      False),
            'alloc': (('\t{lc}.{name}.n_0 = {ros}.{name}.size();\n'
                       '\talloc_array((void **)&{lc}.{name}.a, {lc}.{name}.n_0,\n'
                       '\t            sizeof({ros}.{name}[0]));\n'
                       '\tfor (size_t i = 0; i < {ros}.{name}.size(); i++) {{\n'),
                       True),
            'end': ('\t}}\n', False)
        },
        'time': (('\t{lc}.{name}.secs = {ros}.{name}.sec;\n'
                  '\t{lc}.{name}.nsecs = {ros}.{name}.nsec;\n'), False),
        'ttime': (('\t{lc}.{lcname}.secs = {ros}.{rosname}.sec;\n'
                  '\t{lc}.{lcname}.nsecs = {ros}.{rosname}.nsec;\n'), False),
        'string': ('\t{lc}.{name} = strdup({ros}.{name}.c_str());\n', True),
        'sstring': ('\t{lc}.{lcname} = strdup({ros}.{rosname}.c_str());\n', True)
    }
}


def get_code(direction, key, array = False, ros_ptr = False, lc_ptr = False):
    conv = ''
    if array:
        conv = conversions[direction]['array'][key]
    else:
        conv = conversions[direction][key]
    st = conv[0]
    if ros_ptr:
        st = st.replace('{ros}.', '{ros}->')
    if lc_ptr:
        st = st.replace('{lc}.', '{lc}->')

    return (st, conv[1])


splitter = re.compile(r'[ =]')
def convert_type(f, definition, direction, ros_varname = '', lc_varname = '', 
                 prefix = '', lc_ptr = False, ros_ptr = False, in_array = False):
    '''Writes the conversion code for types.

    :param f: the file to write to.
    :param definition: the ROS type definition to convert to/from.
    :param direction: the direction to convert to (e.g. 'to_ros' or 'to_lc').
    :param ros_varname: the ROS variable name to use in the generated code.
    :param lc_varname: the LabComm variable name to use in the generated code.
    :param prefix: a possible prefix to prepend to the name, mostly only used
                   internally when writing non-primitive types.
    :param lc_ptr: boolean whether the generated code uses pointers for the
                   LabComm variable.
    :param ros_ptr: boolean whether the generated code uses pointers for the
                    ROS variable.
    :param in_array: used internally to keep state when writing arrays.
    '''
    conv_map = conversions[direction]

    free_list = []

    def append_free(stmt, rosvar, lcvar, name):
        if stmt[1]:
            defined = stmt[0].split('=')[0].strip()
            if 'alloc_array' in stmt[0]:
                defined = '{lc}.{name}.a' #TODO: This should be extracted from stmt[0]
            free_list.append(defined.format(ros=rosvar,lc=lcvar,lcname=name,name=name))

    def recursive_array(f, direction, typ, rosvar, lcvar, name, in_array_local,
                        ros_ptr, lc_ptr):
        res = get_code(direction, typ, in_array_local, ros_ptr, lc_ptr)
        parts = name.split('.')
        lcname = parts[0] + '.a[i].' + parts[1]
        rosname = parts[0] + '[i].' + parts[1]
        append_free(res, rosvar, lcvar, lcname)
        f.write(res[0].format(ros=rosvar,lc=lcvar,lcname=lcname,rosname=rosname))

    def write_string(f, conv_map, rosvar, lcvar, name, in_array_local = False):
        '''Helper function for writing conversion code for strings.'''
        if in_array: # Not a nice hack... Should probably do better
            recursive_array(f, direction, 'sstring', rosvar, lcvar, name,
                            in_array_local, ros_ptr, lc_ptr)
        else:
            res = get_code(direction, 'string', in_array_local, ros_ptr, lc_ptr)
            append_free(res, rosvar, lcvar, name)
            f.write(res[0].format(ros=rosvar,lc=lcvar,name=name))

    def write_time_duration(f, conv_map, rosvar, lcvar, name, in_array_local = False):
        '''Helper function for writing conversion code for Time or Duration
        (which are primitive types in ROS msgs).
        '''
        if in_array: # Not a nice hack... Should probably do better
            recursive_array(f, direction, 'ttime', rosvar, lcvar, name,
                            in_array_local, ros_ptr, lc_ptr)
        else:
            res = get_code(direction, 'time', in_array_local, ros_ptr, lc_ptr)
            append_free(res, rosvar, lcvar, name)
            f.write(res[0].format(ros=rosvar,lc=lcvar,name=name))

    def write_array(f, conv_map, rosvar, lcvar, name, typ):
        '''Helper function for writing conversion code for arrays.'''
        res = get_code(direction, 'alloc', True, ros_ptr, lc_ptr)
        append_free(res, rosvar, lcvar, name)
        f.write(res[0].format(ros=rosvar,lc=lcvar,name=name))
        res = ('',False)
        if typ == 'string':
            write_string(f, conv_map, rosvar, lcvar, name, True)
        elif typ == 'time' or typ == 'duraiton':
            write_time_duration(f, conv_map, rosvar, lcvar, name, True)
        elif len(get_nested(typ)) > 0:
            convert_type(f, get_def(clean_type), direction, ros_varname=rosvar,
                         lc_varname=lcvar, prefix=name, lc_ptr=lc_ptr,
                         ros_ptr=ros_ptr, in_array=True)
        else:
            res = get_code(direction, 'default', True, ros_ptr, lc_ptr)
        append_free(res, rosvar, lcvar, name)
        f.write(res[0].format(ros=rosvar,lc=lcvar,name=name))
        res = conv_map['end']
        append_free(res, rosvar, lcvar, name)
        f.write(res[0].format(ros=rosvar,lc=lcvar,name=name))

    for d in definition.split('\n'):
        # Extract type info from definition.
        (typ, tail) = (lambda x: (x[0], x[1:]))(splitter.split(d))
        clean_type = typ.replace('[]', '')
        name = ''
        if len(tail) > 0:
            name = tail[0]
            if len(tail) > 1: # Skip enums
                continue
        if prefix:
            name = prefix + '.' + name
        if len(get_nested(typ)) > 0 and '[]' not in typ: # non-primitive type, recurse
            free_list += convert_type(f, get_def(clean_type), direction,
                                      ros_varname=ros_varname,
                                      lc_varname=lc_varname,
                                      lc_ptr=lc_ptr, ros_ptr=ros_ptr,
                                      prefix=name)
        else: # primitive type
            if '[]' in typ:
                # array_type = typ.replace('[]', '')
                write_array(f, conv_map['array'], ros_varname, lc_varname,
                            name, clean_type)
            elif typ == 'string':
                write_string(f, conv_map, ros_varname, lc_varname, name)
            elif typ == 'time' or typ == 'duration':
                write_time_duration(f, conv_map, ros_varname, lc_varname, name)
            elif typ == '':
                res = get_code(direction, '', False, ros_ptr, lc_ptr)
                f.write(res[0].format(ros=ros_varname,lc=lc_varname,name=name))
            else: # primitive types, just copy
                if in_array: # Not a nice hack... Should probably do better
                    recursive_array(f, direction, 'ddefault', ros_varname,
                            lc_varname, name, False, ros_ptr, lc_ptr)
                else:
                    res = get_code(direction, 'default', False, ros_ptr, lc_ptr)
                    append_free(res, ros_varname, lc_varname, name)
                    f.write(res[0].format(ros=ros_varname,lc=lc_varname,name=name))

    return free_list

def write_send(f, topic, name, lc_prefix='lc_types', indent=1):
    '''Writes the code to send the converted data.
    
    :param f: the file handle to write to.
    :param topic: the topic being converted.
    '''
    lc_topic = msg2id(topic)
    tabs = '\t'*indent
    f.write(tabs+'boost::lock_guard<boost::mutex> enc_guard(enc_lock);\n')
    f.write(tabs+'labcomm_encode_{lc_prefix}_{lc_topic}(enc, {name});\n'
            .format(lc_topic=lc_topic, lc_prefix=lc_prefix,name=name))


def write_free(f, free_list):
    '''Writes the code to free any allocated data structures from the
    conversion code.

    :param f: the file handle to write to.
    :param free_list: the list of names that should be freed.
    '''
    f.write('\t// Free the allocated stuff\n')
    free_list.reverse() # free in reverse order of alloc
    for name in free_list:
        if '[i]' in name: # Detect array.
            size = name.replace('a[i]', 'n_0')
            f.write(('\tfor (int i = 0; i < {size}; i++) {{\n'
                     '\t\tfree({name});\n'
                     '\t}}\n').format(name=name,size=size))
        else:
            f.write('\tfree({name});\n'.format(name=name))

static_conns_begin = '''
void LabCommBridge::setup_static()
{{
'''

static_conns_decl = '''
	struct firefly_transport_connection *conn;
	int res;
'''

static_conns_content = '''
	conn = firefly_transport_connection_udp_posix_new(llp, "{addr}", {port},
					FIREFLY_TRANSPORT_UDP_POSIX_DEFAULT_TIMEOUT);

	res = firefly_connection_open(&actions, NULL, eq, conn, (void *) 1);
	if (res < 0) {{
		throw new std::runtime_error("ERROR: Opening static connection.");
	}}
'''

def write_statics(f, pkg_name, static_connections):
    f.write(static_conns_begin.format(ln=len(static_connections)))

    if len(static_connections) > 0:
        # Write declarations.
        f.write(static_conns_decl)

        for conn in static_connections:
            addr = conn.split(':')[0]
            port = conn.split(':')[1]

            f.write(static_conns_content.format(addr=addr,port=port))

    f.write(end_fn)


srv_type_cache = {}
def get_srv_type(srv):
    if srv in srv_type_cache:
        return srv_type_cache[srv]
    typ = sh('rosservice type %s' % srv)
    if typ[0]:
        srv_type_cache[srv] = typ[1].strip()
        return srv_type_cache[srv]
    else:
        return None


def run(conf, ws, force):
    """Run the tool and put a generated package in ws."""
    cf = ConfigFile(conf)

    # topic, service with a common base class would be prettier.

    # Topics
    topics = get_types()        # name -> type
    defs = OrderedDict()        # type -> definition
    types = set(topics.itervalues())
    while types:
        t = types.pop()
        defn = get_def(t)
        defs[t] = defn
        types |= get_nested(defn) - set(defs.keys())

    # Services
    services = get_srv_types()
    service_defs = {}
    for t in services.itervalues():
        defn = get_srv_def(t)
        service_defs[t] = defn
        types |= get_nested(defn[0]) | get_nested(defn[1]) - set(defs.keys())
    # types -= set(defs.keys())
    while types:     # Services can include complex types. Resolve again.
        t = types.pop()
        defn = get_def(t)
        defs[t] = defn
        types |= get_nested(defn) - set(defs.keys())
    del types

    imports, exports = cf.assert_defined(list(topics))
    services_used = {s: services[s] for s in
                     cf.assert_defined_services(list(services))}
    topics_types = { t: topics[t] for t in imports + exports }

    # C++ configuration
    (cfd, cnam) = mkstemp('.h')
    cfil = os.fdopen(cfd, 'w')
    write_conf(cfil, cf.name, cf.port)
    cfil.close()

    # C++ conversions
    (clientfd, clientnam) = mkstemp('.h')
    (convfd, convnam) = mkstemp('.cpp')
    clientfil = os.fdopen(clientfd, 'w')
    convfil = os.fdopen(convfd, 'w')
    write_conv(clientfil, convfil, cf.name,
               imports, exports, topics_types,
               services_used, service_defs, cf.conversions, cf.static)
    convfil.close()

    # C++ static connections.
    (statfd, statnam) = mkstemp('.cpp')
    statfil = os.fdopen(statfd, 'w')
    write_statics(statfil, cf.name, cf.static)
    statfil.close()

    req_topics = {}
    for t in imports + exports:
        req_topics[t] = topics[t]

    req_services = {}
    for s in services_used:
        req_services[s] = services[s]

    (tfd, tnam) = mkstemp('.lc')
    tfil = os.fdopen(tfd, 'w')
    write_lc(req_topics, defs, req_services, service_defs, tfil)
    tfil.close()

    union = dict(req_topics.items() + req_services.items())
    deps = set()
    for dep in union.itervalues():
        deps.add(dep[:dep.index('/')])

    return create_pkg(ws, cf.name, deps, force, tnam, cnam, convnam, clientnam,
                      statnam, cf.lc_files(), cf.py_files(), cf.conversions)

