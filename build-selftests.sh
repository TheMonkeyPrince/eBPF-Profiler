#!/usr/bin/env bash
set -e

LLVM_PATH="$PWD/build-tools/llvm/"
PAHOLE_PATH="$PWD/build-tools/dwarves/build/"
export PATH="$PAHOLE_PATH:$LLVM_PATH/bin:$PATH"
export LD_LIBRARY_PATH="$LLVM_PATH/lib:$LD_LIBRARY_PATH"

# build all selftests with llvm
cd linux/tools/testing/selftests/bpf/
make clean
make -j$(nproc) PAHOLE=$PAHOLE_PATH/pahole LLC=$LLVM_PATH/bin/llc CLANG=$LLVM_PATH/bin/clang