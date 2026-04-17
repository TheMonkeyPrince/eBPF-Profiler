#!/usr/bin/env bash
set -e

export PATH=$PWD/build-tools/llvm/bin:$PATH
export LD_LIBRARY_PATH=$PWD/build-tools/llvm/lib:$LD_LIBRARY_PATH

llvm-config --version
llvm-config --cflags --libs