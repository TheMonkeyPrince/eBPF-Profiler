#!/usr/bin/env bash
set -e

export PATH="$PWD/llvm-project/llvm/build/bin:$PATH"

# build the kernel
cd linux/
make -j PAHOLE=../dwarves/build/pahole