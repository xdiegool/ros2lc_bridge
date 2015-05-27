#!/usr/bin/python
# Auto generated pos_vel

import labcomm
import StringIO

class posRef(object):
    signature = labcomm.sample('posRef', 
        labcomm.struct([
            ('x', labcomm.FLOAT()),
            ('y', labcomm.FLOAT()),
            ('z', labcomm.FLOAT())]))

class velRef(object):
    signature = labcomm.sample('velRef', 
        labcomm.struct([
            ('dx', labcomm.FLOAT()),
            ('dy', labcomm.FLOAT()),
            ('dz', labcomm.FLOAT()),
            ('dt', labcomm.FLOAT())]))

sample = [
    ('posRef', posRef.signature),
    ('velRef', velRef.signature),
]
