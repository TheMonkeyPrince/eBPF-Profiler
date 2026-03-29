#!/usr/bin/env bash
set -e

KERNEL_VERSION=v7.0-rc5

# clone & build llvm
git clone https://github.com/llvm/llvm-project.git
mkdir -p llvm-project/llvm/build
cd llvm-project/llvm/build
cmake .. -G "Ninja" -DLLVM_TARGETS_TO_BUILD="BPF;X86" \
           -DLLVM_ENABLE_PROJECTS="clang;lld"    \
           -DCMAKE_BUILD_TYPE=Release        \
           -DLLVM_BUILD_RUNTIME=OFF
ninja
cd ../../../
export PATH="$PWD/llvm-project/llvm/build/bin:$PATH"

# clone & build pahole
git clone https://github.com/acmel/dwarves.git
mkdir dwarves/build
cd dwarves/build
cmake ..
make -j
cd ../../

# clone linux kernel
git clone https://github.com/torvalds/linux.git
cd linux
git checkout $KERNEL_VERSION

# setup .config
cp ../.kernel-config .config

