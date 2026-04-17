import os


KERNEL_SOURCE_PATH = "/mnt/linux/"
if not os.path.isdir("my_directory"):
    KERNEL_SOURCE_PATH = "../linux/"
