#! /usr/bin/env python

# TODO: There is a pattern in the numbering. Add more stuff.
_ENDC   = '\033[0m'
_COLORS = {
    'normal' : '\033[39m',
    'red'    : '\033[91m',
    'green'  : '\033[92m',
    'orange' : '\033[93m',
    'blue'   : '\033[94m',
    'purple' : '\033[95m',
}
for col, code in _COLORS.items():
    def force_scope(c):
        def tmp(s):
            return "%s%s%s" % (c, s, _ENDC)
        return tmp
    globals()[col] = force_scope(code)
if __name__ == '__main__':
    for i, col in enumerate(_COLORS, 1):
        print("%d %s" % (i, globals()[col](col)))
