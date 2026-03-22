#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/vars.sh"

# recreate image
rm -f "$IMG"
qemu-img create "$IMG" "$SIZE"

# format filesystem
mkfs.ext4 "$IMG"

${SCRIPT_DIR}/mount.sh

# install minimal Debian
sudo debootstrap --arch=amd64 "$RELEASE" "$DIR" "$MIRROR"

${SCRIPT_DIR}/umount.sh
