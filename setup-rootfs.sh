#!/usr/bin/env bash
set -e

IMG=rootfs.img
SIZE=4G
DIR=rootfs
MIRROR=http://deb.debian.org/debian
RELEASE=stable

# recreate image
rm -f "$IMG"
qemu-img create "$IMG" "$SIZE"

# format filesystem
mkfs.ext4 "$IMG"

# unmount
sudo umount "$DIR" || true
rm -rf "$DIR"

# mount
mkdir -p "$DIR"
sudo mount -o loop "$IMG" "$DIR"

# install minimal Debian
sudo debootstrap --arch=amd64 "$RELEASE" "$DIR" "$MIRROR"

# unmount
sleep 2 # ensure all writes are flushed
sudo umount -l "$DIR"
rm -rf "$DIR"