#!/bin/bash
# Forwarder: canonical implementation lives in tools/memory-sweep-due.sh.
# Either path works; do not edit logic here — edit tools/memory-sweep-due.sh.
HERE="$(cd "$(dirname "$0")" && pwd)"
exec "$HERE/../../tools/memory-sweep-due.sh" "$@"
