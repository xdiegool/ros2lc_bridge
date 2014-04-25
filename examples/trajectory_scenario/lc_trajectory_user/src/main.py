#! /usr/bin/env python
import socket
import labcomm
from lc_gen import pos_vel, proto
from time import sleep
import threading
from pprint import pprint
import sys


def run():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.connect((socket.gethostname(), 7357))
    f = s.makefile()
    e = labcomm.Encoder(labcomm.StreamWriter(f))
    d = labcomm.Decoder(labcomm.StreamReader(f))

    e.add_decl(proto.subscribe.signature)
    e.add_decl(proto.publish.signature)
    e.add_decl(pos_vel.posRef.signature)

    pub = proto.publish()
    pub.topic = 'S__pt_posRef'
    e.encode(pub, pub.signature)

    sub = proto.subscribe()
    sub.topic = 'S__pt_velRef'
    e.encode(sub, sub.signature)

    dec_thread = threading.Thread(target=dec, args=(d,))
    dec_thread.start()

    i = 0;
    while True:
        print "send %d" % i
        pos = pos_vel.posRef()
        pos.x = 1.0 + i
        pos.y = 2.0 + i
        pos.z = 3.0 + i
        e.encode(pos, pos.signature)
        i += 1
        sleep(1.0)


def dec(d):
    print "Decoder running."
    while True:
        val, decl = d.decode()
        if val:
            sys.stdout.write("Got value: ")
            pprint(val)
        else:
            sys.stdout.write("Bridge registered: ")
            pprint(decl)


if __name__ == '__main__':
    run()
