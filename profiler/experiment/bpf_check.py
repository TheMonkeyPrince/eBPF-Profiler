from bcc import BPF
import subprocess
import time
import threading
import ctypes as ct
import os

from trace_execve import trace_exceve


b = BPF(src_file="bpf_check.c")
b.attach_kprobe(event="bpf_check", fn_name="bpf_check")

print("Tracing bpf_check calls...\n")

def print_event(cpu, data, size):
    print("bpf_check called")


b["events"].open_perf_buffer(print_event)

def start_program():
    # Start a long-running program to trigger the bpf_check kprobe
    os.system("/mnt/linux/samples/bpf/tracex1")

# threading.Thread(target=trace_exceve).start()
threading.Thread(target=start_program).start()


while True:
    try:
        b.perf_buffer_poll()
    except KeyboardInterrupt:
        break
