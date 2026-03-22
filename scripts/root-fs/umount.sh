#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/vars.sh"

sleep 2 # ensure all writes are flushed

# unmount
sudo umount -l "$DIR"
rm -rf "$DIR"