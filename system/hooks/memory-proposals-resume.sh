#!/bin/bash
# Forwarder: canonical implementation lives in tools/memory-proposals-resume.sh.
# Either path works; do not edit logic here — edit tools/memory-proposals-resume.sh.
HERE="$(cd "$(dirname "$0")" && pwd)"
exec "$HERE/../../tools/memory-proposals-resume.sh" "$@"
