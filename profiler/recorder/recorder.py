import os
import threading
import ctypes as ct
from time import time
try:
	from bcc import BPF
	BCC_AVAILABLE = True
except ImportError:
	BPF = None
	BCC_AVAILABLE = False

from record import Record


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
		self.bpf.attach_kretprobe(event="bpf_profiler_hook", fn_name="profiler_hook")


		def handle_event(cpu, data, size):
			# print(f"Handling event on CPU {cpu} with data size {size} bytes")
			# raw = ct.string_at(data, size)
			# print(raw)
			# return


			record = Record.from_bytes(ct.string_at(data, size))
			self.trace.append(record)
			return
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

		start_time = time()
		timeout_on = True
		timeout_duration = 5

		def recording_loop():
			nonlocal timeout_on
			print("Listening for kernel events...")
			while not self.finished:
				if timeout_on:
					if self.started:
						timeout_on = False
					else:
						elapsed_time = time() - start_time
						if elapsed_time > timeout_duration:
							print(f"Timeout reached after {elapsed_time:.2f} seconds. Stopping recording.")
							self.finished = True
							break

				self.bpf.perf_buffer_poll(timeout=100)

		self.record_thread = threading.Thread(target=recording_loop, daemon=True)
		self.record_thread.start()


	def wait_for_completion(self) -> list[Record]:
		self.record_thread.join()

		print(f"Recording thread finished. Total events recorded: {len(self.trace)}")

		l = []
		for elt in self.trace:
			if elt.start_time in l:
				print(f"Duplicate timestamp found: {elt.start_time}")
			l.append(elt.start_time)
		print(f"Unique timestamps: {len(set(l))}")

		import sys
		sys.exit(0)
		# return list(sorted(self.trace, key=lambda e: e.timestamp))
	
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