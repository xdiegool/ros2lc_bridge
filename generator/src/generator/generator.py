#! /usr/bin/env python

from utils import PROJ_NAME
import roslib; roslib.load_manifest(PROJ_NAME)
import sys
from optparse import OptionParser
import xml.etree.ElementTree as ET

from tcol import *
from config_file import ConfigException
from utils import GeneratorException, sh
from backends import python,cpp


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
    op.add_option('-n', '--no-build', action="store_false", dest="build",
                  default=True, help="Prevents the generator from running"
                  " 'rosbuild' in the newly created package.")
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
            raise GeneratorException('Choose a language (use -h for help).')

        print(green("Bridge package created in %s" % d))
        if opt.build:
            sh('cd %s && rosmake' % d, nopipe=True)
    except (GeneratorException, ConfigException, IOError) as e:
        sys.stderr.write(red(e) + '\n')
        sys.exit(1)
    except ET.ParseError as e:
        sys.stderr.write(red("Parse error in config file '%s': %s\n" %
                             (opt.conf, e)))
        sys.exit(1)
