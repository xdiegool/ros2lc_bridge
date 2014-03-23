#!/usr/bin/env python

from ft import force, torque

def convert_ft(**kwarg):
    ft = kwarg['/force_torque']
    f = force()
    t = torque()

    # Conv. force:
    f.x = ft.force.x
    f.y = ft.force.y
    f.z = ft.force.z

    # Conv. torque:
    t.x = ft.torque.x
    t.y = ft.torque.y
    t.z = ft.torque.z

    return {'/force_pt': f, '/torque_pt': t}
