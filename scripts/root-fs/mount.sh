#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/vars.sh"

# unmount
sudo umount "$DIR" || true
rm -rf "$DIR"

# mount
mkdir -p "$DIR"
sudo mount -o loop "$IMG" "$DIR"
