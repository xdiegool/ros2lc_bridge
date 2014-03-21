#!/usr/local/bin env

from socket import socket as sock

sock.write = sock.send
sock.read  = sock.recv
sock.flush = lambda x: None
