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

import subprocess

from config import KERNEL_SOURCE_PATH

def list_selftests():
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

def run_selftest(test_name) -> subprocess.Popen[str]:
	if test_name.startswith("selftest_"):
		test_name = test_name[len("selftest_"):]

	process = subprocess.Popen(
		["./test_progs", "-t", test_name],
		cwd=f"{KERNEL_SOURCE_PATH}/tools/testing/selftests/bpf",
		stdout=subprocess.PIPE,
		stderr=subprocess.PIPE,
		text=True
	)
	return process

if __name__ == "__main__":
	print("Available selftests:")
	for test in list_selftests():
		print(test)