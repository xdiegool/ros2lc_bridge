#! /usr/bin/env python


from backends.utils import GeneratorException
from backends.utils import PROJ_NAME
import roslib; roslib.load_manifest(PROJ_NAME)
import sys
from optparse import OptionParser
from config_file import ConfigException
import xml.etree.ElementTree as ET
from tcol import *

# Import both python and C++ backends
from backends import python,cpp,utils


if __name__ == '__main__':
    op = OptionParser()
    op.add_option('-c', '--config-file', dest='conf', default=None,
                  help='The bridge configuration file.')
    op.add_option('-w', '--workspace-path', dest='ws', default=None,
                  help='The directory in which the package will be created.')
    op.add_option('-f', '--force', action="store_true", dest="force",
                  help='Replace any existing directory in case of a name collision')
    op.add_option('-l', '--lang', dest='lang', default='python',
                  help=('The language to generate. Supported options are'
                        '\'python\' or \'cpp\''))
    (opt, args) = op.parse_args(sys.argv)
    if not opt.conf:
        sys.stderr.write(red("Specify config file.\n"))
        sys.exit(1)

    try:
        if opt.lang == 'python':
            d = python.run(opt.conf, opt.ws, opt.force)
        elif opt.lang == 'cpp':
            d = cpp.run(opt.conf, opt.ws, opt.force)
        else:
            raise GeneratorException('Unsupported language specified.')

        print("Bridge package created in %s" % d)
    except (GeneratorException, ConfigException, IOError) as e:
        sys.stderr.write(red(e) + '\n')
    except ET.ParseError as e:
        sys.stderr.write(red("Parse error in config file '%s': %s\n" %
                             (opt.conf, e)))
