#!/usr/bin/env python

import sys
from optparse import OptionParser
import socket
import labcomm
import time

import lc_types


def main(port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(('127.0.0.1', port))
    sock.listen(5)

    while True:
        print 'Listening for new connection on port:', port
        (csock, addr) = sock.accept()
        print 'Got connection from:', addr

        f = csock.makefile()
        e = labcomm.Encoder(labcomm.StreamWriter(f))
        d = labcomm.Decoder(labcomm.StreamReader(f))
        e.add_decl(lc_types.S__ext_service_RET.signature)

        while True:
            value,decl = d.decode()
            if value:
                print 'Got call:', value.controller_id
                res = lc_types.S__ext_service_RET()
                res.status = value.controller_id
                time.sleep(5)
                e.encode(res, res.signature)


if __name__ == '__main__':
    op = OptionParser()
    op.add_option('-p', '--port', dest='port', default=1337,
                  help='The port to listen on.')
    (opt, args) = op.parse_args(sys.argv)

    main(int(opt.port))

