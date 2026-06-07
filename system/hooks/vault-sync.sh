#!/bin/bash
# Forwarder: canonical implementation lives in tools/vault-sync.
# Either path works; do not edit logic here — edit tools/vault-sync.
HERE="$(cd "$(dirname "$0")" && pwd)"
exec "$HERE/../../tools/vault-sync" "$@"
