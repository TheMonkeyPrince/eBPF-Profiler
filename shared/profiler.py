from bcc import BPF
import os

from event import Event


class BPFProfiler:
	def __init__(self, bpf_source="bpf_profiler.c", verbose=True):
		self.verbose = verbose
		self.bpf = BPF(src_file=bpf_source)

		# Attach kprobes to the kernel function "bpf_check"
		self.bpf.attach_kprobe(event="bpf_check", fn_name="verifier_start")
		self.bpf.attach_kretprobe(event="bpf_check", fn_name="verifier_end")

		self.bpf.attach_kprobe(event="bpf_profiler_func_start", fn_name="func_start")
		self.bpf.attach_kretprobe(event="bpf_profiler_func_end", fn_name="func_end")

		self.bpf.attach_kprobe(event="bpf_profiler_trace_point", fn_name="trace_point")

		self.bpf["events"].open_perf_buffer(self.handle_event)

	def handle_event(self, cpu, data, size):
		e = Event.from_data(data)

		if self.verbose:
			print(f"Received event: {e}")
		
		if not self.current_trace:
			print("No active trace, ignoring event")
			return

		match e.get_event_type():
			case Event.EVENT_TYPE.VERIFIER_START:
				self.current_trace.start(e)
			case Event.EVENT_TYPE.VERIFIER_END:
				self.current_trace.end(e)
			case _:
				self.current_trace.trace_event(e)


	def listen_for_events(self, program_name: str):
		print("Listening for kernel events...")
		self.current_trace = BPFTrace(program_name)
		while not self.current_trace.finished:
			self.bpf.perf_buffer_poll()

class BPFTrace:
	def __init__(self, name: str):
		self.name = name
		self.started = False
		self.finished = False
	
	def start(self, start_event: Event):
		self.started = True
		if start_event.get_event_type() != Event.EVENT_TYPE.VERIFIER_START:
			raise ValueError("First event must be a VERIFIER_START event")
		
		self.events = [start_event]

	def end(self, end_event: Event):
		if not self.started:
			raise ValueError("Trace must be started before it can be finalized")
		if end_event.get_event_type() != Event.EVENT_TYPE.VERIFIER_END:
			raise ValueError("Last event must be a VERIFIER_END event")
		self.finished = True
		self.events.append(end_event)

		os.makedirs("traces", exist_ok=True)
		with open(f"traces/{self.name}.bin", "wb") as f:
			for ev in self.events:
				f.write(bytes(ev))

	def trace_event(self, event: Event):
		if not self.started:
			raise ValueError("Trace must be started before it can receive events")
		
		self.events.append(event)
