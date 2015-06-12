#!/usr/bin/env python
# TODO: Rewrite as services when impl.

import sys
import socket
import labcomm2014
import proto
import ft

def run(topic):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.connect((socket.gethostname(), 7357))
    f = s.makefile()
    e = labcomm2014.Encoder(labcomm2014.StreamWriter(f))
    d = labcomm2014.Decoder(labcomm2014.StreamReader(f))

    e.add_decl(proto.subscribe.signature)
    sub = proto.subscribe()
    sub.topic = topic
    e.encode(sub, sub.signature)

    while True:
        val, decl = d.decode()
        if val:
            print(val)
        else:
            print("Br. reg. type: %s" % decl)


if __name__ == '__main__':
    run('%s' % sys.argv[1])
