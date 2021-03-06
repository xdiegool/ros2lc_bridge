"""Classes and methods for parsing the configuration file."""

from os.path import abspath, dirname, join, basename, splitext
import xml.etree.ElementTree as ET


class ConfigException(Exception):
    """Thrown when an error with the configuration file is detected."""
    pass


def _bn(name):
    """Returns the base name of a file without the file extension."""
    return splitext(basename(name))[0]


class Conversion(object):
    """Represents a conversion in the configuration file."""
    # pylint: disable=R0902

    def __init__(self):
        self.lc_path = None
        self.py_path = None
        self.py_func = None
        self.trig_policy = {'type': 'full'}
        self.sample_srcs = []      # [(sample_name, pseudotopic)]
        self.topic_srcs = []
        self.sample_dsts = [] # [(sample_name, pseudotopic)]
        self.topic_dsts = []

    def tuple_repr(self):       # Easily printable...
        """Get a tuple representation of the conversion object."""
        # ('/tmp/fake.py', 'ft_split', [], ['force_torque'],
        #  [], [], { 'type': 'periodic', 'period': 1.0})

        return (_bn(self.py_path), self.py_func, _bn(self.lc_path),
                self.sample_srcs, self.topic_srcs,
                self.sample_dsts, self.topic_dsts,
                self.trig_policy)


class ConfigFile(object):
    """Represents a bridge configuration file."""
    # pylint: disable=R0902

    def __init__(self, fnam, rewrite=False):
        self.fnam = fnam
        # General
        self.name = None
        self.port = 0
        self.autopubsub = False
        # Topics
        self.export_all = False
        self.exports = []
        self.imports = []
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
        # pylint: disable=R0912,R0915,C0301
        tree = ET.parse(fnam)
        root = tree.getroot()
        self.name = root.attrib['name']
        self.port = root.attrib['port']
        if 'autopubsub' in root.attrib:
            self.autopubsub = bool(root.attrib['autopubsub'])
        for child in root:
            if child.tag == 'exports':
                for gchild in child:
                    if gchild.tag == 'all':
                        self.export_all = True
                    elif gchild.tag == 'topic':
                        self.exports.append(gchild.attrib['name'])
                    elif gchild.tag == 'service':
                        srv = {
                            'name': gchild.attrib['name'],
                            'direction': 'export'
                        }
                        self.services.append(srv)
            elif child.tag == 'imports':
                for gchild in child:
                    if gchild.tag == 'topic':
                        self.imports.append(gchild.attrib['name'])
                    elif gchild.tag == 'service':
                        conf_dir = dirname(self.fnam)
                        srv = {
                            'name': gchild.attrib['name'],
                            'file': abspath(join(conf_dir,gchild.attrib['file'])),
                            'direction': 'import'
                        }
                        self.services.append(srv)
            elif child.tag == 'services': # TODO: Deprecated, remove.
                for gchild in child:
                    if gchild.tag == 'all':
                        self.allow_all_services = True
                    elif gchild.tag == 'service':
                        srv = {
                            'name': gchild.attrib['name'],
                            'direction': 'export'
                        }
                        self.services.append(srv)
            elif child.tag == 'static-connections':
                for gchild in child:
                    if gchild.tag == 'target':
                        addr = gchild.attrib['addr']
                        self.static[addr] = {
                            'subscribe': [],
                            'publish': [],
                            'service': []
                        }
                        for ggchild in gchild:
                            if ggchild.tag == 'subscribe':
                                self.static[addr]['subscribe'].append(
                                    ggchild.attrib['name'])
                            elif ggchild.tag == 'publish':
                                self.static[addr]['publish'].append(
                                    ggchild.attrib['name'])
                            elif ggchild.tag == 'service':
                                self.static[addr]['service'].append(
                                    ggchild.attrib['name'])
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
                                        conv.topic_srcs.append(name)
                                    elif src.tag == 'sample':
                                        conv.sample_srcs.append((name, src.attrib['pseudotopic']))
                            elif ggchild.tag == 'destinations':
                                for dst in ggchild:
                                    name = dst.attrib['name']
                                    if dst.tag == 'topic':
                                        conv.topic_dsts.append(name)
                                    elif dst.tag == 'sample':
                                        conv.sample_dsts.append((name, dst.attrib['pseudotopic']))
                        self.conversions.append(conv)


    def lc_files(self):
        """Get absolute paths to all LC files in the config."""
        base = dirname(self.fnam)  # Paths are relative to config.
        return [abspath(join(base, c.lc_path)) for c in self.conversions]

    def py_files(self):
        """Get absolute paths to all Python files in the config."""
        base = dirname(self.fnam)  # Paths are relative to config.
        return [abspath(join(base, c.py_path)) for c in self.conversions]


def collect_referenced_files(conf_path):
    """Reads the content of all files referenced in the configuration file."""
    files = {}
    conf = ConfigFile(conf_path)
    base = dirname(conf_path)
    for conv in conf.conversions:
        for f in (conv.lc_path, conv.py_path):
            if f:
                files[f] = open(abspath(join(base, f))).read()
    return files
