from bcc import BPF

def load_profiler():
	# Load BPF program
	profiler_module = BPF(src_file="bpf_profiler.c")

	profiler_module.attach_kprobe(event="bpf_check", fn_name="bpf_check_start")
	profiler_module.attach_kretprobe(event="bpf_check", fn_name="bpf_check_end")
	# b.attach_kfunc(event="bpf_profiler_capture_point", fn_name="capture_point")

	def print_event(cpu, data, size):
		event = profiler_module["events"].event(data)
		print(f"name={event.name.decode(errors='replace')}, timestamp={event.timestamp}")

	profiler_module["events"].open_perf_buffer(print_event)

	return profiler_module

def listen_for_events(profiler_module):
	print("Listening for kernel events...")
	while True:
		profiler_module.perf_buffer_poll()

# b.trace_print()