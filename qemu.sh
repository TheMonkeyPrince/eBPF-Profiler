# qemu boot
echo "Booting kernel with QEMU..."
qemu-system-x86_64 \
  -enable-kvm \
  -cpu host \
  -m 1G \
  -smp 2 \
  -kernel linux/arch/x86/boot/bzImage \
  -append "console=ttyS0 root=/dev/sda rw ip=dhcp" \
  -drive file=rootfs.img,format=raw \
  -netdev user,id=net0,hostfwd=tcp::2222-:22 \
  -device e1000,netdev=net0 \
  -virtfs local,path=shared,mount_tag=shared,security_model=mapped-xattr \
  -nographic

# to exit qemu, press Ctrl+A followed by X