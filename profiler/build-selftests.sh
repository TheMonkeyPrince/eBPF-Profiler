#!/usr/bin/env bash
set -e

# RUN THIS SCRIPT FROM QEMU

export PATH="/mnt/build-tools/llvm-project/llvm/build/bin:$PATH"
PAHOLE_PATH="/mnt/build-tools/dwarves/build/pahole"

# build all selftests with llvm
cd /mnt/linux/tools/testing/selftests/bpf/
make -j$(nproc) PAHOLE=/mnt/build-tools/dwarves/build/pahole