#!/usr/bin/env bash
set -e

IMG=rootfs.img
DIR=rootfs

# unmount
sudo umount "$DIR" || true
rm -rf "$DIR"

# mount
mkdir -p "$DIR"
sudo mount -o loop "$IMG" "$DIR"

# copy kernel headers to rootfs
# sudo mkdir -p "$DIR/lib/modules/headers"
# sudo cp -r linux/headers/include "$DIR/lib/modules/headers"

# DNS inside chroot, so apt works
sudo cp "$DIR/etc/resolv.conf" "$DIR/etc/resolv.conf.bak"
sudo cp /etc/resolv.conf "$DIR/etc/resolv.conf"

# install necessary packages inside chroot
sudo chroot "$DIR" apt-get update
# sudo chroot "$DIR" apt-get install -y clang llvm dwarves libelf-dev libssl-dev libbpf-dev python3 python3-pip isc-dhcp-client curl openssh-server bpftool bpfcc-tools python3-bpfcc
sudo chroot "$DIR" apt-get install -y python3 python3-pip isc-dhcp-client curl bpftool bpfcc-tools python3-bpfcc

# enable root autologin on ttyS0
sudo mkdir -p "$DIR/etc/systemd/system/serial-getty@ttyS0.service.d"
sudo tee "$DIR/etc/systemd/system/serial-getty@ttyS0.service.d/autologin.conf" >/dev/null <<EOF
[Service]
ExecStart=
ExecStart=-/sbin/agetty --autologin root --noclear %I \$TERM
EOF

# minimal configuration
echo "/dev/sda / ext4 defaults 0 1" | sudo tee "$DIR/etc/fstab" >/dev/null
echo "ttyS0" | sudo tee -a "$DIR/etc/securetty" >/dev/null

# set root password to empty for easy login
sudo chroot "$DIR" passwd -d root
# sudo sed -i 's/^#\?PermitEmptyPasswords .*/PermitEmptyPasswords yes/' "$DIR/etc/ssh/sshd_config"
# sudo sed -i 's/^#\?PermitRootLogin .*/PermitRootLogin yes/' "$DIR/etc/ssh/sshd_config"

# set hostname
echo "bpfvm" | sudo tee "$DIR/etc/hostname" >/dev/null

# configure network interfaces for DHCP
cat <<EOF | sudo tee "$DIR/etc/network/interfaces"
auto lo
iface lo inet loopback

auto eth0
iface eth0 inet dhcp
EOF

# sudo cp "$DIR/etc/resolv.conf.bak" "$DIR/etc/resolv.conf"
echo "nameserver 8.8.8.8" | sudo tee $DIR/etc/resolv.conf >/dev/null

sudo chroot "$DIR" mkdir -p /mnt/profiler
echo "profiler /mnt/profiler 9p trans=virtio,version=9p2000.L,msize=8192,uid=0,gid=0,_netdev 0 0" | sudo tee -a "$DIR/etc/fstab"

sudo chroot "$DIR" mkdir -p /mnt/linux
echo "linux /mnt/linux 9p trans=virtio,version=9p2000.L,msize=8192,uid=0,gid=0,_netdev 0 0" | sudo tee -a "$DIR/etc/fstab"


# cleanup to reduce size
sudo chroot "$DIR" apt-get clean
sudo rm -rf "$DIR/usr/share/doc/"*
sudo rm -rf "$DIR/usr/share/man/"*

# unmount
sleep 2 # ensure all writes are flushed
sudo umount -l "$DIR"
rm -rf "$DIR"