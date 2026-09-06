# Board profiles

A profile describes one board so the tooling knows what to talk to and what to
expect. Copy `nazare-unity.mk` and edit it for your setup.

Use one with any make target:

    make davega-debug PROFILE=profiles/nazare-unity.mk

Profiles are deliberately small - they hold connection details and the CAN id of
the second motor. They do NOT hold motor tuning: current limits and gearing are
specific to your motors, wheels and battery, and copying someone else's is a bad
idea. Run the detection wizard instead.
