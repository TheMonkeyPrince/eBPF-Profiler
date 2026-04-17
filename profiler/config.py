import os

KERNEL_SOURCE_PATH = "/mnt/linux/"
if not os.path.isdir(KERNEL_SOURCE_PATH):
    KERNEL_SOURCE_PATH = "../linux/"
