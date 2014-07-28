#!/usr/bin/env python

import conf                     # The generated configuration.
import roslib; roslib.load_manifest(conf.PKG_NAME)
import rospy
import socket
import labcomm
import threading
import lc_types

def msg2id(msg_name):
    return msg_name.replace('/', conf.SLASHSUB)


def id2msg(msg_name):
    return msg_name.replace(conf.SLASHSUB, '/')


# rospy.init_node(conf.PKG_NAME)

topic_types_py = {}
topics_to_import = conf.EXPORTS + conf.IMPORTS
for conv in conf.CONV:
    topics_to_import += conv[4]
    topics_to_import += conv[6]
for topic in topics_to_import:
    pkg, typ = conf.TOPIC_TYPES[topic].split('/')
    tmp = __import__('%s.msg' % pkg, globals(), locals(), [typ], 0)
    cls = getattr(tmp, typ)
    globals()[typ] = cls
    topic_types_py[topic] = cls


ttmap = {}         # Topic -> LabComm class
for topic in conf.IMPORTS + conf.EXPORTS:
    type_str = msg2id(topic)
    type_class = getattr(lc_types, type_str)
    ttmap[topic] = type_class


service_types_py = {} # Topic -> Python class
services = {} # Topic -> ROS ServiceProxy
slmap = {} # Topic -> LabComm class
for name,srv in conf.SERVICES.iteritems():
    name = msg2id(name)
    # Save service type (Python)
    pkg = subtyp = ''
    tmp = srv['type'].split('/')
    if len(tmp) > 1:
        pkg = tmp[0]
        subtyp = tmp[1]
    else:
        pkg = conf.PKG_NAME
        subtyp = tmp[0]

    tmp = __import__('%s.srv' % pkg, globals(), locals(), [subtyp], 0)
    cls = getattr(tmp, subtyp)
    globals()[subtyp] = cls
    service_types_py[name] = cls

    # Save the service proxy object
    if srv['direction'] == 'export':
        services[name] = rospy.ServiceProxy(srv['name'],
                                            service_types_py[name])
    else:
        services[name] = None

    # Save the service parameter and return type (LabComm)
    labcomm_par = getattr(lc_types, msg2id(srv['name']) + '_PAR')
    labcomm_ret = getattr(lc_types, msg2id(srv['name']) + '_RET')
    slmap[name] = (labcomm_par, labcomm_ret)


def get_from_module(mod, thing):
    tmp = __import__(mod, globals(), locals(), [thing], 0)
    return getattr(tmp, thing)


class Conversion(object):
    """A manual conversion lets a user do more advanced type conversion and fan
    out the content of a message to multiple samples, or vice versa.
    """
    def __init__(self, ct):
        # Unpack
        module = ct[0]          # Name module with user spec. conv. func.
        func = ct[1]            # Name of user spec. conv. func.
        lc = ct[2]              # Name of user spec. lc file.
        self.samples_in = ct[3] # Usage: (sample, pseudotopic)
        self.topics_in = ct[4]  # List of source topics.
        self.samples_out = ct[5] # Usage: (sample, pseudotopic)
        self.topics_out = ct[6]  # List of destination topics.
        self.convert_fn = get_from_module(module, func) # Callable conv. func.
        self.cache = {t: None for t in (self.topics_in +
                                        [x[1] for x in self.samples_in])}
        self.subs = {}          # Usage. {topic -> rospy.Subscriber}
        for t in self.topics_in:
            def cb(data, meta):
                insn, topic = meta
                insn.put_data(topic, data)
            self.subs[topic] = rospy.Subscriber(t, topic_types_py[t],
                                                cb, (self, t))
        self.pubs = {t: rospy.Publisher(t, topic_types_py[t])
                     for t in self.topics_out}
        self.pseudotopic_subs = {}
        self.pseudotopic_types = {pt: get_from_module(lc, s)
                                  for s, pt in self.samples_out}
        # Figure out trigger policy stuff.
        self.trigger_policy = ct[7] # Dict with trig policy.
        if self.trigger_policy['type'] == 'custom':
            self.trig_policy_fn = get_from_module(self.trigger_policy['path'],
                                                  self.trigger_policy['func'])

    def examine_cache(self, timer_event=None):    # TODO: Or notify conv/send thread?
        trig_type = self.trigger_policy['type']
        if trig_type == 'full':
            if None not in self.cache.values():
                res = self.convert_fn(**self.cache)
                self._send(res)
                for key in self.cache:
                    self.cache[key] = None
        elif trig_type == 'single':
            res = self.convert_fn(**self.cache)
            self._send(res)
        elif trig_type == 'custom':
            should_send = self.trig_policy_fn(**self.cache)
            res = self.convert_fn(**self.cache)
            if should_send:
                self._send(res)
        else:
            res = self.convert_fn(**self.cache)
            self._send(res)

        # else:
        #     for k,v in self.cache.iteritems():
        #         if v is None:
        #             print "%s is None" % k

    def put_data(self, topic, data):
        self.cache[topic] = data
        if self.trigger_policy['type'] != 'periodic':
            self.examine_cache()

    def put_sample(self, name, data):
        # TODO: Fix uglyness. (ch. to dict?)
        topic = None
        for s, pt in self.samples_in:
            if s == name:
                topic = pt
                break
        else:
            rospy.logerror("Sample %s sent to conversion not using it.", name)
            return
        self.cache[topic] = data
        if self.trigger_policy['type'] != 'periodic':
            self.examine_cache()

    def _send(self, vals):
        if vals is None:
            return

        for t in self.topics_out:
            self.pubs[t].publish(vals[t])
        for s, pt in self.samples_out:
            print "proc. %s" % pt
            for sub in self.pseudotopic_subs.get(pt, ()):
                sub.send_sample(vals[pt], vals[pt].signature)
                print "has sub"

    def register_sample_subscriber(self, pt, insn):
        if pt not in self.pseudotopic_subs:
            self.pseudotopic_subs[pt] = []
        self.pseudotopic_subs[pt].append(insn)
        return self.pseudotopic_types[pt]

    def unregister_sample_subscriber(self, pt, insn):
        self.pseudotopic_subs[pt].remove(insn)


convs = []                      # All manual conversions.
topic_in_hooks = {}             # {Topic -> [All conversions using it as input]}
sample_in_hooks = {}            # {Samples -> [All conversions using it as input]}
pseudotopic_sources = {}        # {PT -> [Providers (convs) of PT]}
pseudotopic_sinks = {}          # {PT -> [Users (convs) of PT]} TODO: Not use?
pseudotopic_types = {}

for ct in conf.CONV:
    c = Conversion(ct)
    convs.append(c)
    for t in c.topics_in:
        if t not in topic_in_hooks:
            topic_in_hooks[t] = []
        topic_in_hooks[t].append(c)
    for s, pt in c.samples_in:
        if s not in sample_in_hooks:
            sample_in_hooks[s] = []
        sample_in_hooks[s].append(c)
        if pt not in pseudotopic_sinks:
            pseudotopic_sinks[pt] = []
        pseudotopic_sinks[pt].append(c)
        # TODO: Out
    for t in c.topics_out:
        pass
    for s, pt in c.samples_out:
        print "got source for", pt
        if pt not in pseudotopic_sources:
            pseudotopic_sources[pt] = []
        pseudotopic_sources[pt].append(c)
        # pseudotopic_types[pt] = None # TODO: ?


class LabCommBridge(object):
    def __init__(self):
        rospy.init_node(conf.PKG_NAME)
        # Need to create rospy.Timer *after* rospy.init_node()
        for conv in convs:
            if conv.trigger_policy['type'] == 'periodic':
                period = conv.trigger_policy['period']
                rospy.Timer(rospy.Duration(period), conv.examine_cache)

    def serve(self):
        ssock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        ssock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        ssock.settimeout(None)
        ssock.bind(('', conf.PORT))
        ssock.listen(5)

        for str_addr,pubsub_dict in conf.STATIC_CONNS.iteritems():
            addr = str_addr.split(':')
            addr[1] = int(addr[1])
            csock = socket.create_connection(tuple(addr))
            ClientThread(csock, addr, pubsub_dict).start()

        while not rospy.is_shutdown():
            rospy.loginfo("Bridge waiting...")
            try:
                csock, caddr = ssock.accept()
                ClientThread(csock, caddr).start()
            except socket.error:
                rospy.loginfo('Shutting down bridge.')


class ServiceWorker(threading.Thread):
    """A worker thread that handles calling services."""

    def __init__(self, srv, params, sign, callback, callback_data):
        super(ServiceWorker, self).__init__()
        self.srv = srv
        self.params = params
        self.sign = sign
        self.callback = callback
        self.callback_data = callback_data

    def run(self):
        args = []
        for name, typ in self.sign.decl.field:
            args.append(getattr(self.params, name))
        rospy.wait_for_service(self.srv['name'])

        res = services[msg2id(self.srv['name'])](*args)
        self.callback(res, self.callback_data)


class ServiceCallback(object):
    """A callable class which should be passed as the callback function when
    creating a new Service object. It is used to keep some state for the
    function called as a service request comes in. It forwards the request via
    LabComm and waits for the response. When the response is decoded, the
    set_result function should be called which makes the blocked call return.
    """

    def __init__(self, srv, client):
        self.srv = srv
        self.client = client
        self.signal = threading.Event()
        self.lock = threading.Lock()
        with self.client.enc_lock:
            self.client.enc.add_decl(slmap[msg2id(self.srv)][0].signature)
        self.res = None

    def set_result(self, res, sig):
        args = []
        for name, typ in sig.decl.field:
            args.append(getattr(res, name))

        self.res = service_types_py[msg2id(self.srv)]._response_class(*args)
        self.signal.set()

    def __call__(self, data):
        with self.lock: # For now, only allow one caller at the time.
            # Find LC type
            typ = slmap[msg2id(self.srv)][0]

            try:
                self.client.send_sample(data, typ.signature)
                self.signal.wait()
                self.signal.clear()
                return self.res
            except socket.error:
                # TODO: Shut down Service object.
                return None


service_publishers = {}
class ClientThread(threading.Thread):
    """Client thread class.

    This class contains all logic for communicating with a client connecting to
    this bridge.

    """

    def __init__(self, client_sock, client_addr, static_dict = None):
        super(ClientThread, self).__init__()

        self.subs= {} # topic -> subscriber
        self.pubs = {} # topic -> subscriber
        self.client_addr = client_addr
        self.client_socket = client_sock
        client_sock.settimeout(None)
        f = client_sock.makefile('w', 0)
        self.enc = labcomm.Encoder(labcomm.StreamWriter(f))
        self.dec = labcomm.Decoder(labcomm.StreamReader(f))

        self.enc_lock = threading.Lock()
        self.subscribed_conversions = {} # pt -> conv
        self.published_conversions = {} # pt -> conv
        self.ongoing_service_calls = {} # srv name -> dict

        import_srvs = [srv for name,srv in conf.SERVICES.iteritems()
                           if srv['direction'] == 'import' and
                           name not in service_publishers]
        for srv in import_srvs:
            n = msg2id(srv['name'])
            cb = ServiceCallback(n, self)
            self.ongoing_service_calls[n] = cb
            service_publishers[n] = rospy.Service(srv['name'],
                                                  service_types_py[n], cb)

        if static_dict:
            for pubsub,topics in static_dict.iteritems():
                for t in topics:
                    if pubsub == 'publish' and t in conf.IMPORTS:
                        rospy.loginfo(('Setting up static publish for topic %s '
                                       'to client %s'), t, client_addr)
                        self.pubs[t] = rospy.Publisher(t, topic_types_py[t])
                    elif pubsub == 'subscribe' and t in conf.EXPORTS:
                        rospy.loginfo(('Setting up static subscribe for topic '
                                       '%s to client %s'), t, client_addr)
                        typ = ttmap[t]
                        self.enc.add_decl(typ.signature)
                        self.subs[t] = rospy.Subscriber(t, topic_types_py[t],
                                                        self._convert_and_send,
                                                        callback_args=t)

        if conf.AUTOPUBSUB:
            class Dummy(object):
                pass

            print pseudotopic_sources
            print pseudotopic_sinks
            dummy = Dummy()
            for topic in conf.EXPORTS:
                dummy.topic = topic
                self._handle_subscribe(dummy, None)
            for topic, _ in pseudotopic_sources.iteritems():
                dummy.topic = topic
                self._handle_subscribe(dummy, None)
            for topic in conf.IMPORTS:
                dummy.topic = topic
                self._handle_publish(dummy, None)
            for topic, _ in pseudotopic_sinks.iteritems():
                dummy.topic = topic
                self._handle_publish(dummy, None)

    def _convert_and_send(self, data, topic):
        """Converts incoming ROS msg to LC sample and encodes it."""
        typ = ttmap[topic]
        var = typ()
        for field in typ.signature.decl.field:
            name = field[0]
            setattr(var, name, getattr(data, name))
        try:
            self.send_sample(var, var.signature)
        except socket.error:
            self.subs[topic].unregister()

    def send_sample(self, var, sig):
        with self.enc_lock:
            self.enc.encode(var, sig)

    def _handle_subscribe(self, sub, sig):
        """Handles incoming subscribe request from the client."""
        topic = id2msg(sub.topic)

        if topic in conf.EXPORTS:
            rospy.loginfo('Accepted subscribe request for topic: %s', topic)

            typ = ttmap[topic]
            self.enc.add_decl(typ.signature)

            def cb(data, meta):
                instance, topic = meta
                instance._convert_and_send(data, topic)

            # TODO: Perhaps we shouldn't be subscribing twice to the same topic?
            self.subs[topic] = rospy.Subscriber(topic, topic_types_py[topic],
                                                cb, (self, topic))
        elif topic in pseudotopic_sources:
            for conv in pseudotopic_sources.get(topic, ()):
                cls = conv.register_sample_subscriber(topic, self)
                self.enc.add_decl(cls.signature)
                self.subscribed_conversions[topic] = conv
        else:
            rospy.logwarn('Rejected subscribe request for topic: %s', topic)

    def _handle_publish(self, pub, sig):
        """Handles incoming publish request from the client."""
        topic = id2msg(pub.topic)

        if topic in conf.IMPORTS:
            rospy.loginfo('Accepted publish for: %s', topic)
            self.pubs[topic] = rospy.Publisher(topic, topic_types_py[topic])
        elif topic in pseudotopic_sinks:
            rospy.loginfo('Publish notification on %s', topic)
        else:
            rospy.logwarn('Rejected publish request for topic %s', topic)

    def _handle_topic(self, val, sig):
        """Converts incoming LC sample to ROS msg and publishes it."""
        topic = id2msg(sig.name)
        msg = topic_types_py[topic]()
        for name, typ in sig.decl.field:
            setattr(msg, name, getattr(val, name))

        if topic in self.pubs:
            self.pubs[topic].publish(msg)
        else:
            rospy.logwarn('did not publish on topic %s', topic)

    def _handle_service(self, val, sig):
        """Handles incoming service call requests.

        Creates a worker thread that avoids locking the client thread while the
        worker performs the ROS service call.

        """
        srvname = id2msg(sig.name[:-4])
        rospy.loginfo('Got service call for: %s', srvname)

        if msg2id(srvname) in self.ongoing_service_calls:
            rospy.loginfo('Got response from non-ROS service: %s', srvname)

            cb = self.ongoing_service_calls[msg2id(srvname)]
            cb.set_result(val, sig)
        elif srvname in conf.SERVICES.keys():
            rospy.loginfo('Accepted service call for: %s', srvname)

            types = slmap[msg2id(srvname)]
            self.enc.add_decl(types[1].signature)

            def service_callback(data, meta):
                srvname, instance = meta
                # Get response type and create an instance
                typ = slmap[msg2id(srvname)][1] # 0 is req. type, 1 is resp. type
                var = typ()
                # Copy over each field
                for field in typ.signature.decl.field:
                    name = field[0]
                    setattr(var, name, getattr(data, name))

                # Send data back to client.
                with instance.enc_lock:
                    instance.enc.encode(var, var.signature)

            ServiceWorker(conf.SERVICES[srvname], val, sig, service_callback,
                          (srvname, self)).start()
        else:
            rospy.logwarn('Got service call not in configuration file: %s',
                          srvname)

    def run(self):
        """The run loop of the thread which drives it all."""
        rospy.loginfo("Bridge accepted client: %s", self.client_addr)

        try:
            while True:
                val, sig = self.dec.decode()
                rosname = id2msg(sig.name)
                if val is not None: # Not as stupid as it looks.
                    if rosname == 'subscribe':
                        self._handle_subscribe(val, sig)
                    elif rosname == 'publish':
                        self._handle_publish(val, sig)
                    elif sig.name in sample_in_hooks: # TODO: Check reg.?
                        for conv in sample_in_hooks[sig.name]:
                            conv.put_sample(sig.name, val)
                    elif rosname in conf.IMPORTS: # TODO: out.
                        self._handle_topic(val, sig)
                    else:
                        self._handle_service(val, sig)
                else:
                    rospy.loginfo("Client registered: '%s'", sig.name)
        except EOFError:
            # Clean up socket and subscriptions on EOF.
            self.client_socket.close()
            for topic,sub in self.subs.iteritems():
                sub.unregister()
            # TODO: Clean conv.
            for pt, conv in self.subscribed_conversions.iteritems():
                conv.unregister_sample_subscriber(pt, self)
        except socket.error as e:
            rospy.logerr("Socket error %d: %s", e.errno, e.strerror)

        rospy.loginfo("Client disconnected")


if __name__ == '__main__':
    b = LabCommBridge()
    b.serve()
