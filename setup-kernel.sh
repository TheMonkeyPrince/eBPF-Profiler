#!/usr/bin/env bash
set -e

KERNEL_VERSION=v7.0-rc5

mkdir -p build-tools
cd build-tools

INSTALL_PREFIX="$PWD/llvm/"
rm -rf llvm
mkdir -p llvm
echo $INSTALL_PREFIX

# clone & build llvm
# git clone https://github.com/llvm/llvm-project.git
rm -rf llvm-project/llvm/build
mkdir -p llvm-project/llvm/build
cd llvm-project/llvm/build
cmake -G Ninja .. \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_INSTALL_PREFIX=$INSTALL_PREFIX \
  -DLLVM_ENABLE_PROJECTS="clang;lld" \
  -DLLVM_TARGETS_TO_BUILD="X86"
ninja
ninja install
cd ../../../
export PATH=$INSTALL_PREFIX/bin:$PATH
export LD_LIBRARY_PATH=$INSTALL_PREFIX/lib:$LD_LIBRARY_PATH

# clone & build pahole
git clone https://github.com/acmel/dwarves.git
mkdir dwarves/build
cd dwarves/build
cmake ..
make -j
cd ../../

cd ..

# clone linux kernel
git clone https://github.com/torvalds/linux.git
cd linux
git checkout $KERNEL_VERSION

# setup .config
cp ../.kernel-config .config

