#!/usr/bin/env bash
set -e

export PATH="$PWD/build-tools/llvm-project/llvm/build/bin:$PATH"
PAHOLE_PATH="$PWD/build-tools/dwarves/build/pahole"

# build all selftests with llvm
cd linux/tools/testing/selftests/bpf/
make -j$(nproc) PAHOLE=$PAHOLE_PATH