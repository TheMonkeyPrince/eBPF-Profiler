import os
import threading
from time import time, sleep
import struct

from profiler_types import ProfilingResult, Record, BPFInsn

RECORD_FILE_PATH = "/tmp/bpf_profile_records"


class BPFRecorder:
	def __init__(self, verbose=False):
		self.verbose = verbose
		self.record_thread = None

	def start_recording(self):
		
		os.remove(RECORD_FILE_PATH) if os.path.exists(RECORD_FILE_PATH) else None

		def recording_loop():
			duration = 2  # seconds
			sleep(duration)

		self.record_thread = threading.Thread(target=recording_loop, daemon=True)
		self.record_thread.start()

	def wait_for_completion(self, program_name: str) -> list[ProfilingResult]:
		self.record_thread.join()
		results = self.read_profile_file(program_name)
		seen = set()
		filtered_results = []
		
		for result in results:
			key = tuple(result.program)
			if key not in seen:
				seen.add(key)
				result.program_name = program_name + "_" + str(len(seen))
				filtered_results.append(result)

		for result in filtered_results:
			if self.verbose:
				print(result)

		return filtered_results if results else []
		# return list(sorted(trace, key=lambda e: e.timestamp))

	def read_profile_file(self, program_name: str) -> list[ProfilingResult]:
		results = []
		with open("/tmp/bpf_profile_records", "rb") as f:
			i = 0
			while True:
				pos = f.tell()
				if not f.read(1):
					break
				f.seek(pos)
				program = self.read_bpf_program(f)
				trace = self.read_trace_(f)
				results.append(ProfilingResult(f"{program_name}_{i}", program, trace))
				i += 1

		return results

	def read_bpf_program(self, file) -> list[BPFInsn]:
		len_bytes = file.read(4)
		if len(len_bytes) != 4:
			raise ValueError("Corrupted file: partial count")

		(program_len,) = struct.unpack("<I", len_bytes)
		insn_size = BPFInsn.size()
		raw = file.read(program_len * insn_size)
		if len(raw) != program_len * insn_size:
			raise ValueError("Corrupted file: truncated BPF program block")

		program = []
		for i in range(program_len):
			chunk = raw[i * insn_size : (i + 1) * insn_size]
			program.append(BPFInsn.from_bytes(chunk))

		return program

	def read_trace_(self, file) -> list[Record]:
		len_bytes = file.read(4)
		if len(len_bytes) != 4:
			raise ValueError("Corrupted file: partial count")

		(record_count,) = struct.unpack("<I", len_bytes)
		record_size = Record.size()
		raw = file.read(record_count * record_size)
		if len(raw) != record_count * record_size:
			raise ValueError("Corrupted file: truncated record block")

		records = []
		for i in range(record_count):
			chunk = raw[i * record_size : (i + 1) * record_size]
			records.append(Record.from_bytes(chunk))

		return records
