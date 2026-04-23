import os
import threading
import ctypes as ct
try:
	from bcc import BPF
	BCC_AVAILABLE = True
except ImportError:
	BPF = None
	BCC_AVAILABLE = False

from event import Event


class BPFRecorder:
	def __init__(self, verbose=False):
		self.started = False
		self.finished = False
		self.verbose = verbose
		self.record_thread = None
		self.trace = []
		self.program_name = None

		if not BCC_AVAILABLE:
			# Dummy mode
			self.bpf = None
			print("bcc not available: running in dummy mode")
			return
		
		# Normal mode
		self.bpf = BPF(src_file=f"{os.path.dirname(__file__)}/bpf_recorder.c")

		# Attach kprobes to the kernel function "bpf_check"
		self.bpf.attach_kprobe(event="bpf_check", fn_name="verifier_start")
		self.bpf.attach_kretprobe(event="bpf_check", fn_name="verifier_end")

		self.bpf.attach_kprobe(
			event="bpf_profiler_func_timer_result", fn_name="func_timer_result"
		)
		self.bpf.attach_kprobe(
			event="bpf_profiler_block_timer_result", fn_name="block_timer_result"
		)

		def handle_event(cpu, data, size):
			e = Event.from_bytes(ct.string_at(data, size))
			if self.verbose and e.get_event_type():
				# print(f"Received event: {e.get_event_type().name}")
				print(f"Received event: {e}")

			if self.finished:
				return

			if (
				not self.started
				and e.get_event_type() == Event.EVENT_TYPE.VERIFIER_START
			):
				self.started = True
				self.trace.append(e)
				print(f"Trace started for program: {self.program_name}")
				return

			self.trace.append(e)

			match e.get_event_type():
				case Event.EVENT_TYPE.VERIFIER_START:
					raise ValueError(
						"Received VERIFIER_START event while a trace is already in progress"
					)
				case Event.EVENT_TYPE.VERIFIER_END:
					if self.started and not self.finished:
						self.started = False
						self.finished = True
						print(f"Trace finished for program: {self.program_name}")

		self.bpf["events"].open_perf_buffer(handle_event)

	# def record_events(self, program_name: str) -> list[Event]:
	# 	self.started = False
	# 	self.finished = False
	# 	self.program_name = program_name
	# 	self.trace = []

	# 	print("Listening for kernel events...")
	# 	while not self.finished:
	# 		self.bpf.perf_buffer_poll()
	# 	return list(sorted(self.trace, key=lambda e: e.timestamp))


	def start_recording(self, program_name: str):
		self.started = False
		self.finished = False
		self.program_name = program_name
		self.trace = []

		def recording_loop():
			print("Listening for kernel events...")
			while not self.finished:
				self.bpf.perf_buffer_poll(timeout=100)

		self.record_thread = threading.Thread(target=recording_loop, daemon=True)
		self.record_thread.start()


	def wait_for_completion(self) -> list[Event]:
		self.record_thread.join()
		return list(sorted(self.trace, key=lambda e: e.timestamp))
	
	def unload(self):
		if self.record_thread and self.record_thread.is_alive():
			print("Stopping recording thread...")
			self.finished = True
			self.record_thread.join()
			print("Thread stopped.")
		if self.bpf:
			print("Cleaning up BPF resources...")
			self.bpf.cleanup()
			print("BPF resources cleaned up.")