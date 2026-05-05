from bcc import BPF
import subprocess
import time
import threading
import ctypes as ct


def trace_exceve(poll=False):
    b = BPF(src_file="trace_execve.c")
    b.attach_kprobe(event="do_execveat_common", fn_name="trace_execve")

    class Event(ct.Structure):
        _fields_ = [
            ("pid", ct.c_uint),
            ("read_ret", ct.c_int),
            ("comm", ct.c_char * 16),
            ("fname", ct.c_char * 256),
        ]

    def run_commands():
        time.sleep(1)
        subprocess.run(["/usr/bin/echo", "banana"])
        time.sleep(1)

    threading.Thread(target=run_commands).start()

    print("Tracing execve calls...\n")

    def print_event(cpu, data, size):
        event = ct.cast(data, ct.POINTER(Event)).contents
        comm = event.comm.decode("utf-8", errors="replace").rstrip("\x00")
        fname = event.fname.decode("utf-8", errors="replace").rstrip("\x00")
        print(f"execve pid={event.pid} comm={comm} read={event.read_ret} file={fname}")

    if poll:
        b["events"].open_perf_buffer(print_event)
        while True:
            try:
                b.perf_buffer_poll()
            except KeyboardInterrupt:
                break

if __name__ == "__main__":
    trace_exceve(poll=True)