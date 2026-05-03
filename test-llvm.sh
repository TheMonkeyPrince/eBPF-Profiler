#!/usr/bin/env bash
set -e

LLVM_PATH="$PWD/build-tools/llvm/"
PAHOLE_PATH="$PWD/build-tools/dwarves/build/"
export PATH="$PAHOLE_PATH:$LLVM_PATH/bin:$PATH"
export LD_LIBRARY_PATH="$LLVM_PATH/lib:$LD_LIBRARY_PATH"

llvm-config --version
llvm-config --cflags --libs

"$LLVM_PATH/bin/llc" -march=bpf -mattr=help | grep dwarfris