import os
import threading
from time import time
import struct

from record import Record

RECORD_FILE_PATH = "/tmp/bpf_profile_records"

class BPFRecorder:
	def __init__(self, verbose=False):
		self.started = False
		self.finished = False
		self.verbose = verbose
		self.record_thread = None
		self.trace = []
		self.program_name = None
		

	def start_recording(self, program_name: str):
		self.started = False
		self.finished = False
		self.program_name = program_name
		self.trace = []

		start_time = time()
		timeout_on = True
		timeout_duration = 5

		os.remove(RECORD_FILE_PATH) if os.path.exists(RECORD_FILE_PATH) else None

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

		self.record_thread = threading.Thread(target=recording_loop, daemon=True)
		self.record_thread.start()


	def wait_for_completion(self) -> list[Record]:
		self.record_thread.join()

		print(f"Recording thread finished. Total events recorded: {len(self.trace)}")

		records = self.read_profile_file()
		print(f"Read {len(records)} records from profile file.")

		return records
		# return list(sorted(self.trace, key=lambda e: e.timestamp))

	def read_profile_file(self) -> list[Record]:
		records = []
		record_size = Record.size()

		with open("/tmp/bpf_profile_records", "rb") as f:
			# while True:
			count_bytes = f.read(4)
			# if not count_bytes:
			# 	break  # EOF

			if len(count_bytes) != 4:
				raise ValueError("Corrupted file: partial count")

			(count,) = struct.unpack("<I", count_bytes)

			raw = f.read(count * record_size)
			if len(raw) != count * record_size:
				raise ValueError("Corrupted file: truncated record block")

			for i in range(count):
				chunk = raw[i * record_size:(i + 1) * record_size]
				records.append(Record.from_bytes(chunk))

		return records