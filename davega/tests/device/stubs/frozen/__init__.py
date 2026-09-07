"""Stand-in for the DAVEGA's frozen firmware package.

Real modules on the path rather than objects pushed into `sys.modules`:
MicroPython will not let you construct a module, and importing the same way
the firmware does is closer to the thing being tested anyway.
"""
