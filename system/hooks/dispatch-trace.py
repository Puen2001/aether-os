#!/usr/bin/env python3
# Forwarder: canonical implementation lives in tools/dispatch-trace.py.
# Kept here so settings.json can wire hooks under system/hooks/ if preferred.
# Either path works; do not edit logic here — edit tools/dispatch-trace.py.
import os
import runpy

HERE = os.path.dirname(os.path.abspath(__file__))
TARGET = os.path.normpath(os.path.join(HERE, "..", "..", "tools", "dispatch-trace.py"))
runpy.run_path(TARGET, run_name="__main__")
