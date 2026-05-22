import os
import threading
from time import sleep

from profiler_types import ProfilingResult
from storage import read_profile

RECORD_FILE_PATH = "/tmp/bpf_profile_records"


class BPFRecorder:
	def __init__(self, verbose=False):
		self.verbose = verbose
		self.record_thread = None

	def start_recording(self, record_duration=1):
		
		os.remove(RECORD_FILE_PATH) if os.path.exists(RECORD_FILE_PATH) else None

		def recording_loop():
			duration = record_duration  # seconds
			sleep(duration)

		self.record_thread = threading.Thread(target=recording_loop, daemon=True)
		self.record_thread.start()

	def wait_for_completion(self, program_name: str) -> list[ProfilingResult]:
		self.record_thread.join()
		results = self.read_results(program_name)
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

	def read_results(self, program_name: str) -> list[ProfilingResult]:
		results = []
		try:
			with open("/tmp/bpf_profile_records", "rb") as f:
				i = 0
				while True:
					pos = f.tell()
					if not f.read(1):
						break
					f.seek(pos)
					results.append(read_profile(f, f"{program_name}_{i}"))
					i += 1
		except FileNotFoundError:
			print("No profiling data found.")
			return []
		except ValueError as e:
			print(f"Error reading profiling data: {e}")
			return []

		return results
