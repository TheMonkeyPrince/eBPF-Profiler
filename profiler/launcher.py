import threading

from programs.some_test import some_test


def launch_bpf_program(program_path) -> threading.Thread:
	thread = threading.Thread(target=some_test)
	thread.start()
	return thread
