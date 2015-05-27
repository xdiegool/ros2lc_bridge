#!/usr/bin/env python

import sys
from optparse import OptionParser
import socket
import labcomm
import lc_types                 # The .lc generated by the generator.
import time
import pprint
import numpy


class AddTwoIntsCilent(object):
    def __init__(self, port):
        # Setup socket connection to bridge.
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.connect((socket.gethostname(), port))
        # Setup LabComm.
        f = sock.makefile()
        self.e = labcomm.Encoder(labcomm.StreamWriter(f))
        self.d = labcomm.Decoder(labcomm.StreamReader(f))
        self.e.add_decl(lc_types.S__add_two_ints_PAR.signature)
        self.e.add_decl(lc_types.S__add_two_intsS__get_loggers_PAR.signature)

    def call_service(self, iterations, a, b):
        '''Calls the add_two_ints service {iteration} number of times and
        prints out the average response time.
        '''
        times = []

        # Build request.
        req = lc_types.S__add_two_ints_PAR()
        req.a = a
        req.b = b

        # Run and time requests.
        for i in range(0, iterations):
            start = time.time()*1000
            self.e.encode(req, req.signature)

            value, decl = self.d.decode()
            while not value:
                value, decl = self.d.decode()

            end = time.time()*1000
            times.append(end-start)

        variance = numpy.std(times)
        mean = numpy.mean(times)
        maxi = max(times)
        mini = min(times)
        out = u'Got %d results in %.3fms (\u00B1 %.6f, min %f, max %f).'
        print out % (iterations,mean, variance, mini, maxi)

    def call_get_loggers(self):
        '''Calls the add_two_ints/get_loggers service to test more elaborate
        type conversions.'''
        par = lc_types.S__add_two_intsS__get_loggers_PAR()
        par.__dummy__ = 1
        self.e.encode(par, par.signature)

        value, decl = self.d.decode()
        while not value:
            value, decl = self.d.decode()
        pprint.pprint(value)


if __name__ == '__main__':
    op = OptionParser()
    op.add_option('-p', '--port', dest='port', default=7357, type='int',
                  help='The port to connect to.')
    op.add_option('-i', '--iterations', dest='iterations', default=100, type='int',
                  help='How many iterations to run.')
    (opt, args) = op.parse_args(sys.argv)
    if not len(args) == 3:
        print 'Specify two numbers to add as parameters.'
    a = int(args[1])
    b = int(args[2])

    s = AddTwoIntsCilent(opt.port)
    s.call_service(opt.iterations, a, b)
    s.call_get_loggers()
