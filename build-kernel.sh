#!/usr/bin/env bash
cd linux

# echo "Building kernel headers..."
# make headers_install INSTALL_HDR_PATH=headers

echo "Building kernel..."
make -j$(nproc)

# echo "Building bpftool..."
# cd tools/bpf/bpftool
# make LDFLAGS="-static"