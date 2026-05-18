# # build once
# make
# # list available top-level tests
# ./test_progs -l
# # run one test by name match
# sudo ./test_progs -t xdp_bonding
# # run one test by numeric id (from -l output order)
# sudo ./test_progs -n 123
# For a specific subtest inside a test:


# # format: test_name/subtest_name
# sudo ./test_progs -t "test_tc_tunnel/ipv4_geneve"
# # or numeric test/subtest
# sudo ./test_progs -n 45/2

import sys
import os
import sys
import subprocess

KERNEL_SOURCE_PATH = "/mnt/linux/"
if not os.path.isdir(KERNEL_SOURCE_PATH):
    KERNEL_SOURCE_PATH = "../linux/"

def list_kernel_selftests():
	result = subprocess.run(
		["./test_progs", "-l"],
		cwd=f"{KERNEL_SOURCE_PATH}/tools/testing/selftests/bpf",
		capture_output=True,
		text=True
	)
	if result.returncode != 0:
		print("Error listing selftests:", result.stderr)
		return []
	
	selftests = map(lambda test: "selftest_" + test, result.stdout.splitlines())
	return list(selftests)

def run_kernel_selftest(test_name) -> subprocess.Popen[str]:
	if test_name.startswith("selftest_"):
		test_name = test_name[len("selftest_"):]

	process = subprocess.Popen(
		["./test_progs", "-t", f"{test_name}"],
		cwd=f"{KERNEL_SOURCE_PATH}/tools/testing/selftests/bpf",
		stdout=subprocess.PIPE,
		stderr=subprocess.PIPE,
		text=True
	)
	return process	

if __name__ == "__main__":
	if len(sys.argv) < 2:
		print("Usage: python kernel_selftests.py <test_name/list>")
		sys.exit(1)

	if sys.argv[1] == "list":
		for sample in list_kernel_selftests():
			print(sample)
		sys.exit(0)

	selftest_name = sys.argv[1]
	process = run_kernel_selftest(selftest_name)
	stdout, stderr = process.communicate()
	if process.returncode == 0:
		print(stdout)
	else:
		print(stderr)
