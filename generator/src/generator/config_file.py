#!/usr/bin/env python

from os.path import abspath, dirname, join, basename, splitext
import xml.etree.ElementTree as ET


class ConfigException(Exception):
    pass


def _bn(name):
    return splitext(basename(name))[0]



class Conversion(object):
    def __init__(self):
        self.lc_path = None
        self.py_path = None
        self.py_func = None
        self.trig_policy = {}
        self.sources_sample = []      # [(sample_name, pseudotopic)]
        self.sources_topic = []
        self.destinations_sample = [] # [(sample_name, pseudotopic)]
        self.destinations_topic = []

    def tuple_repr(self):       # Easily printable...
        # ('/tmp/fake.py', 'ft_split', [], ['force_torque'],
        #  [], [], { 'type': 'periodic', 'period': 1.0})

        return (_bn(self.py_path), self.py_func, _bn(self.lc_path),
                self.sources_sample, self.sources_topic,
                self.destinations_sample, self.destinations_topic,
                self.trig_policy)


class ConfigFile(object):
    """Represents a bridge configuration file."""

    def __init__(self, fnam, rewrite=False):
        self.fnam = fnam
        # General
        self.name = None
        self.port = 0
        # Topics
        self.allow_all_incoming_topics = False
        self.topics_in = []
        self.topics_out = []
        # Services
        self.allow_all_services = False
        self.services = []
        # Static connections
        self.static = {}
        # Explicit type converson
        self.conversions = []

        self.rewrite = rewrite
        if self.rewrite:
            self.lc_paths = {}  # Referenced lc files: basename -> path
        self._read(fnam)

    def _read(self, fnam):
        """Reads a config file according to 'test/conf.xml'."""
        tree = ET.parse(fnam)
        root = tree.getroot()
        self.name = root.attrib['name']
        self.port = root.attrib['port']
        for child in root:
            if child.tag == 'topics_in':
                for gchild in child:
                    if gchild.tag == 'all':
                        self.allow_all_incoming_topics = True
                    elif gchild.tag == 'topic':
                        self.topics_in.append(gchild.attrib['name'])
            elif child.tag == 'topics_out':
                for gchild in child:
                    if gchild.tag == 'topic':
                        self.topics_out.append(gchild.attrib['name'])
            elif child.tag == 'services':
                for gchild in child:
                    if gchild.tag == 'all':
                        self.allow_all_services = True
                    elif gchild.tag == 'service':
                        self.services.append(gchild.attrib['name'])
            elif child.tag == 'static-connections':
                for gchild in child:
                    addr = gchild.attrib['addr']
                    self.static[addr] = {
                            'subscribe': [],
                            'publish': []
                    }
                    for ggchild in gchild:
                        if ggchild.tag == 'subscribe':
                            self.static[addr]['subscribe'].append(ggchild.attrib['name'])
                        elif ggchild.tag == 'publish':
                            self.static[addr]['publish'].append(ggchild.attrib['name'])
            elif child.tag == 'conversions':
                for gchild in child:
                    if gchild.tag == 'conversion':
                        conv = Conversion()
                        for ggchild in gchild:
                            if ggchild.tag == 'lc':
                                conv.lc_path = ggchild.attrib['path']
                            elif ggchild.tag == 'py':
                                conv.py_path = ggchild.attrib['path']
                                conv.py_func = ggchild.attrib['function']
                            elif ggchild.tag == 'trig_policy':
                                policy_type = ggchild.attrib['type']
                                conv.trig_policy['type'] = policy_type
                                if policy_type == 'periodic':
                                    conv.trig_policy['period'] = float(ggchild.attrib['period'])
                                elif policy_type == 'custom':
                                    conv.trig_policy['path'] = _bn(ggchild.attrib['path'])
                                    conv.trig_policy['func'] = ggchild.attrib['function']
                            elif ggchild.tag == 'sources':
                                for src in ggchild:
                                    name = src.attrib['name']
                                    if src.tag == 'topic':
                                        conv.sources_topic.append(name)
                                    elif src.tag == 'sample':
                                        e = (name, src.attrib['pseudotopic'])
                                        conv.sources_sample.append(e)
                            elif ggchild.tag == 'destinations':
                                for dst in ggchild:
                                    name = dst.attrib['name']
                                    if dst.tag == 'topic':
                                        conv.destinations_topic.append(name)
                                    elif dst.tag == 'sample':
                                        e = (name, dst.attrib['pseudotopic'])
                                        conv.destinations_sample.append(e)
                        self.conversions.append(conv)


    def assert_defined(self, known_topics):
        sall  = set(known_topics)
        ukin  = set(self.topics_in)  - sall
        ukout = set(self.topics_out) - sall
        if ukin or ukout:
            raise ConfigException("Config contains unknown topics(s): %s" % ','.join(ukin | ukout))
        if self.allow_all_incoming_topics:
            tin = list(known_topics)
        else:
            tin = list(self.topics_in)
        tout = list(self.topics_out)
        return (tin, tout)

    def assert_defined_services(self, known_services):
        uk = set(self.services) - set(known_services)
        if uk:
            raise ConfigException("Config contains unknown service(s): %s" % ','.join(uk))
        if self.allow_all_services:
            return known_services
        else:
            return self.services

    def lc_files(self):
        b = dirname(self.fnam)  # Paths are relative to config.
        return [abspath(join(b, c.lc_path)) for c in self.conversions]

    def py_files(self):
        b = dirname(self.fnam)  # Paths are relative to config.
        return [abspath(join(b, c.py_path)) for c in self.conversions]


def collect_referenced_files(conf_path):
    files = {}
    conf = ConfigFile(conf_path)
    base = dirname(conf_path)
    for conv in conf.conversions:
        for f in (conv.lc_path, conv.py_path):
            if f:
                files[f] = open(abspath(join(base, f))).read()
    return files
