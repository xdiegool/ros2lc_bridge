#!/usr/bin/python
# Auto generated proto

import labcomm
import StringIO

class subscribe(object):
    signature = labcomm.sample('subscribe', 
        labcomm.struct([
            ('topic', labcomm.STRING())]))

class unsubscribe(object):
    signature = labcomm.sample('unsubscribe', 
        labcomm.struct([
            ('topic', labcomm.STRING())]))

class publish(object):
    signature = labcomm.sample('publish', 
        labcomm.struct([
            ('topic', labcomm.STRING())]))

class unpublish(object):
    signature = labcomm.sample('unpublish', 
        labcomm.struct([
            ('topic', labcomm.STRING())]))

sample = [
    ('subscribe', subscribe.signature),
    ('unsubscribe', unsubscribe.signature),
    ('publish', publish.signature),
    ('unpublish', unpublish.signature),
]
