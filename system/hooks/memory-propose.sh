#!/bin/bash
# Forwarder: canonical implementation lives in tools/memory-propose.sh.
# Either path works; do not edit logic here — edit tools/memory-propose.sh.
HERE="$(cd "$(dirname "$0")" && pwd)"
exec "$HERE/../../tools/memory-propose.sh" "$@"
