#!/usr/bin/env bash
set -e

export PATH="$PWD/build-tools/llvm-project/llvm/build/bin:$PATH"
PAHOLE_PATH="$PWD/build-tools/dwarves/build/pahole"

# build all samples with llvm
cd linux/
# make headers_install
make M=samples/bpf