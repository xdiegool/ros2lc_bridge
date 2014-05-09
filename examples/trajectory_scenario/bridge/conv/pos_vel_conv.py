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
    if (kwarg['/velX'] and
        kwarg['/velY'] and
        kwarg['/velZ'] and
        kwarg['/velT']
       ):
        vr = velRef()
        vr.dx = kwarg['/velX'].data
        vr.dy = kwarg['/velY'].data
        vr.dz = kwarg['/velZ'].data
        vr.dt = kwarg['/velT'].data
        return {'/pt_velRef': vr}
    else:
        return None

# Decide whether to trigger send or not
def do_trigger(**kwarg):
    vr = velRef()
    if kwarg['/velX'] is not None:
        return True
    return False


