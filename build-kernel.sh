#!/usr/bin/env bash
set -e

export PATH="$PWD/llvm-project/llvm/build/bin:$PATH"

# build the kernel
cd linux/
make -j$(nproc) PAHOLE=../dwarves/build/pahole

# build bpf selftests
cd tools/testing/selftests/bpf/
make -j$(nproc) PAHOLE=../../../../../dwarves/build/pahole
