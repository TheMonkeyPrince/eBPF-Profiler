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

make M=samples/bpf clean
make M=samples/bpf LLVM=1 \
  PAHOLE="$PAHOLE_PATH/pahole" \
  LLC="$LLVM_PATH/bin/llc" \
  CLANG="$LLVM_PATH/bin/clang" \
  BPF_EXTRA_CFLAGS="-g -Wno-microsoft-anon-tag -fms-extensions" \
  TPROGS_USER_CFLAGS="-Wno-microsoft-anon-tag -fms-extensions"