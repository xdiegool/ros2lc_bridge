#!/usr/bin/env python

from pos_vel import posRef, velRef
from std_msgs.msg import Float32


# Convert incoming position data:
def convert_pos_in(**kwarg):
    pos = kwarg['/pt_posRef']
    return {'/posX': Float32(pos.x),
            '/posY': Float32(pos.y),
            '/posZ': Float32(pos.z)}


# Convert outgoing velocity data:
def convert_vel_out(**kwarg):
    vr = velRef()
    vr.dx = kwarg['/velX'].data
    vr.dy = kwarg['/velY'].data
    vr.dz = kwarg['/velZ'].data
    vr.dt = kwarg['/velT'].data

    return {'/pt_velRef': vr}

# Decide whether to trigger send or not
def do_trigger(**kwarg):
    vr = velRef()
    vr.dx = kwarg['/velX'].data
    if vr.dx != None:
        return True
    return False


