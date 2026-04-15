import threading

from programs.some_test import some_test
from programs.dns_matching.dns_matching import run_dns_matching

def launch_bpf_program(program_path) -> threading.Thread:
	# thread = threading.Thread(target=some_test)
	thread = threading.Thread(target=run_dns_matching)
	thread.start()
	return thread
