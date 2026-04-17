#!/usr/bin/env bash
set -e

KERNEL_VERSION=v7.0-rc5

LLVM_PATH="$PWD/build-tools/llvm/"

mkdir -p build-tools
cd build-tools

# clone & build llvm
rm -rf llvm
mkdir -p llvm
git clone https://github.com/llvm/llvm-project.git
rm -rf llvm-project/llvm/build
mkdir -p llvm-project/llvm/build
cd llvm-project/llvm/build
cmake -G Ninja .. \
  -DCMAKE_BUILD_TYPE=Release \
  -LLVM_PATH=$LLVM_PATH \
  -DLLVM_ENABLE_PROJECTS="clang;lld" \
  -DLLVM_TARGETS_TO_BUILD="X86;BPF"
ninja
ninja install
cd ../../../
export PATH="$LLVM_PATH/bin:$PATH"
export LD_LIBRARY_PATH="$LLVM_PATH/lib:$LD_LIBRARY_PATH"

# clone & build pahole
git clone https://github.com/acmel/dwarves.git
rm -rf dwarves/build
mkdir -p dwarves/build
cd dwarves/build
cmake ..
make -j LLC=$LLVM_PATH/bin/llc CLANG=$LLVM_PATH/bin/clang
cd ../../

cd ..

# clone linux kernel
git clone https://github.com/torvalds/linux.git
cd linux
git checkout $KERNEL_VERSION

# setup .config
cp ../.kernel-config .config

