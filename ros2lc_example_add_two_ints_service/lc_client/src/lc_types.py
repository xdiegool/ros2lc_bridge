#!/usr/bin/python
# Auto generated lc_types

import labcomm
import StringIO

class S__add_two_ints_PAR(object):
    signature = labcomm.sample('S__add_two_ints_PAR', 
        labcomm.struct([
            ('a', labcomm.LONG()),
            ('b', labcomm.LONG())]))

class S__add_two_ints_RET(object):
    signature = labcomm.sample('S__add_two_ints_RET', 
        labcomm.struct([
            ('sum', labcomm.LONG())]))

class S__add_two_intsS__get_loggers_PAR(object):
    signature = labcomm.sample('S__add_two_intsS__get_loggers_PAR', 
        labcomm.struct([])
    )

class S__add_two_intsS__get_loggers_RET(object):
    signature = labcomm.sample('S__add_two_intsS__get_loggers_RET', 
        labcomm.struct([
            ('loggers', labcomm.array([0],
                labcomm.struct([
                    ('name', labcomm.STRING()),
                    ('level', labcomm.STRING())])))]))

sample = [
    ('S__add_two_ints_PAR', S__add_two_ints_PAR.signature),
    ('S__add_two_ints_RET', S__add_two_ints_RET.signature),
    ('S__add_two_intsS__get_loggers_PAR', S__add_two_intsS__get_loggers_PAR.signature),
    ('S__add_two_intsS__get_loggers_RET', S__add_two_intsS__get_loggers_RET.signature),
]
