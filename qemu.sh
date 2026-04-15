# qemu boot
echo "Booting kernel with QEMU..."
sudo qemu-system-x86_64 \
  -enable-kvm \
  -cpu host \
  -m 4G \
  -smp 4 \
  -kernel linux/arch/x86/boot/bzImage \
  -append "console=ttyS0 root=/dev/sda rw ip=dhcp" \
  -drive file=rootfs.img,format=raw \
  -netdev user,id=net0 \
  -device e1000,netdev=net0 \
  -virtfs local,path=profiler,mount_tag=profiler,security_model=none \
  -virtfs local,path=linux,mount_tag=linux,security_model=none \
  -virtfs local,path=build-tools,mount_tag=build-tools,security_model=none \
  -nographic

# to exit qemu, press Ctrl+A followed by X