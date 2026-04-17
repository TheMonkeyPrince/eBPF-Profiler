#!/usr/bin/env bash
set -e

LLVM_PATH="$PWD/build-tools/llvm/"
export PATH="$LLVM_PATH/bin:$PATH"
export LD_LIBRARY_PATH="$LLVM_PATH/lib:$LD_LIBRARY_PATH"
PAHOLE_PATH="$PWD/build-tools/dwarves/build/pahole"

# build all samples with llvm
cd linux/
make headers_install PAHOLE=$PAHOLE_PATH LLC=$LLVM_PATH/bin/llc CLANG=$LLVM_PATH/bin/clang
make -C samples/bpf clean 
make M=samples/bpf PAHOLE=$PAHOLE_PATH LLC=$LLVM_PATH/bin/llc CLANG=$LLVM_PATH/bin/clang