#!/usr/bin/env bash
set -e

LLVM_PATH="$PWD/build-tools/llvm/"
PAHOLE_PATH="$PWD/build-tools/dwarves/build/"
export PATH="$PAHOLE_PATH:$LLVM_PATH/bin:$PATH"
export LD_LIBRARY_PATH="$LLVM_PATH/lib:$LD_LIBRARY_PATH"

# build all samples with llvm
cd linux/

make -C tools clean
make -C samples/bpf clean

make headers_install

# make headers_install PAHOLE=$PAHOLE_PATH/pahole LLC=$LLVM_PATH/bin/llc CLANG=$LLVM_PATH/bin/clang

make M=samples/bpf PAHOLE=$PAHOLE_PATH/pahole LLC=$LLVM_PATH/bin/llc CLANG=$LLVM_PATH/bin/clang