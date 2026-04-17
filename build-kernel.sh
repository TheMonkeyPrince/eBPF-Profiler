#!/usr/bin/env bash
set -e

export PATH="$PWD/build-tools/llvm-project/llvm/build/bin:$PATH"
PAHOLE_PATH="$PWD/build-tools/dwarves/build/pahole"

if [[ "$1" == "clean" ]]; then
    echo "Cleaning kernel and BPF selftests..."
    cd linux/
    make clean
    exit 0
fi

# build the kernel
cd linux/
git stash
git clean -fd
cp -r ../kernel_patch/* kernel/
make -j$(nproc) PAHOLE=$PAHOLE_PATH