import os
import threading
from time import time, sleep
import struct

from profiler.types import Record, BPFInsn

RECORD_FILE_PATH = "/tmp/bpf_profile_records"

class BPFRecorder:
	def __init__(self, verbose=False):
		self.started = False
		self.finished = False
		self.verbose = verbose
		self.record_thread = None
		self.program_name = None
		

	def start_recording(self, program_name: str):
		self.started = False
		self.finished = False
		self.program_name = program_name

		start_time = time()
		timeout_on = True
		timeout_duration = 5

		os.remove(RECORD_FILE_PATH) if os.path.exists(RECORD_FILE_PATH) else None

		def recording_loop():
			print(f"Recording thread started for program '{program_name}'")
			sleep(self.timeout_duration)
			print(f"Recording thread finished waiting for {self.timeout_duration} seconds")

		self.record_thread = threading.Thread(target=recording_loop, daemon=True)
		self.record_thread.start()


	def wait_for_completion(self) -> list[Record]:
		self.record_thread.join()

		results = self.read_profile_file()
		print(f"Read {len(results)} programs and traces from profile file.")

		if results:
			print(f"First program has {len(results[0][0])} instructions and {len(results[0][1])} records.")
		
		return results[0][1] if results else []
		# return list(sorted(trace, key=lambda e: e.timestamp))

	def read_profile_file(self) -> list[tuple[list[BPFInsn], Record]]:
		results = []
		with open("/tmp/bpf_profile_records", "rb") as f:
			while True:
				try:
					program = self.read_bpf_program(f)
					trace = self.read_trace_(f)
					results.append((program, trace))
				except ValueError as e:
					print(f"Finished reading profile file: {e}")
					break
				break # only read one program + trace for now

		return results
	
	def read_bpf_program(self, file) -> list[BPFInsn]:
		len_bytes = file.read(4)
		if len(len_bytes) != 4:
			raise ValueError("Corrupted file: partial count")
		
		(program_len, ) = struct.unpack("<I", len_bytes)
		insn_size = BPFInsn.size()
		raw = file.read(program_len * insn_size)
		if len(raw) != program_len * insn_size:
			raise ValueError("Corrupted file: truncated BPF program block")
		
		program = []
		for i in range(program_len):
			chunk = raw[i * insn_size:(i + 1) * insn_size]
			program.append(BPFInsn.from_bytes(chunk))

		return program

	def read_trace_(self, file) -> list[Record]:
		len_bytes = file.read(4)
		if len(len_bytes) != 4:
			raise ValueError("Corrupted file: partial count")
		
		(record_count, ) = struct.unpack("<I", len_bytes)
		record_size = Record.size()
		raw = file.read(record_count * record_size)
		if len(raw) != record_count * record_size:
			raise ValueError("Corrupted file: truncated record block")
		
		records = []
		for i in range(record_count):
			chunk = raw[i * record_size:(i + 1) * record_size]
			records.append(Record.from_bytes(chunk))

		return records