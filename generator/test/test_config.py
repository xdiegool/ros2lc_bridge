#!/usr/bin/env python

# TODO: Create proper tests.

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src', 'generator'))
from config_file import ConfigFile

if __name__ == '__main__':
    cf = ConfigFile(os.path.join(os.path.dirname(__file__), 'conf.xml'))
    assert cf.export_all
    assert cf.exports == []
    assert cf.imports == ['/rosout', '/ping']

    # Assertions for static config stuff
    addr1 = '192.168.1.101:1337'
    addr2 = '127.0.0.1:8080'
    assert addr1 in cf.static
    assert addr2 in cf.static
    assert cf.static[addr1] == {'publish': ['/ping'],
                                'subscribe': ['/pong', '/rosout']}
    assert cf.static[addr2] == {'publish': [], 'subscribe': ['/rosout']}
