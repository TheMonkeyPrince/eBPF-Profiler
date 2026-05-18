# import threading

# from programs.some_test import some_test
# from programs.dns_matching.dns_matching import run_dns_matching

# def launch_bpf_program(program_path) -> threading.Thread:
# 	# thread = threading.Thread(target=some_test)
# 	thread = threading.Thread(target=run_dns_matching)
# 	thread.start()
# 	return thread

import sys
import subprocess

try:
	from .kernel_selftests import run_kernel_selftest
	from .kernel_samples import run_kernel_samples
except ImportError:
	from kernel_selftests import run_kernel_selftest
	from kernel_samples import run_kernel_samples

def launch_bpf_program(program_name: str) -> subprocess.Popen[str]:

	if program_name.startswith("selftest_"):
		process = run_kernel_selftest(program_name)
		if process:
			return process

	elif program_name.startswith("sample_"):
		process = run_kernel_samples(program_name)
		if process:
			return process
	
	elif program_name == "some_test":
		return subprocess.Popen(
			["python3", "/root/programs/some_test.py"],
			stdout=subprocess.PIPE,
			stderr=subprocess.PIPE,
			text=True,
		)

	raise ValueError(f"Unknown program name: {program_name}")

if __name__ == "__main__":
	if len(sys.argv) < 2:
		print("Usage: python launcher.py <program_name>")
		sys.exit(1)

	program_name = sys.argv[1]
	process = launch_bpf_program(program_name)
	stdout, stderr = process.communicate()
	if process.returncode == 0:
		print(stdout)
	else:
		print(stderr)
