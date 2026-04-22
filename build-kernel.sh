#!/usr/bin/env bash
set -e

LLVM_PATH="$PWD/build-tools/llvm/"
PAHOLE_PATH="$PWD/build-tools/dwarves/build/"
export PATH="$PAHOLE_PATH:$LLVM_PATH/bin:$PATH"
export LD_LIBRARY_PATH="$LLVM_PATH/lib:$LD_LIBRARY_PATH"

if [[ "$1" == "clean" ]]; then
    echo "Cleaning kernel and BPF selftests..."
    cd linux/
    make clean
    exit 0
fi

# build the kernel
cd linux/
git reset --hard
cp -r ../kernel_patch/* kernel/
make -j$(nproc) PAHOLE=$PAHOLE_PATH/pahole LLC=$LLVM_PATH/bin/llc CLANG=$LLVM_PATH/bin/clang