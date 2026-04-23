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

def list_working_selftests():
	try:
		with open("working_selftests.txt", "r") as file:
			return file.read().splitlines()
	except:
		working_selftests = find_working_selftests()
		with open("working_selftests.txt", "w") as file:
			file.write("\n".join(working_selftests))
		return working_selftests

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

def extract_working_subtests(test_name) -> list[str]:
	process = run_selftest(test_name)
	stdout, stderr = process.communicate()
	if process.returncode == 0:	
		print(stdout)	
		lines = stdout.splitlines()
		lines.pop()
		if len(lines) == 0:
			return []
		
		def extract_subtest_name(line):
			try:
				test_name, status = line.rsplit(":", 1)
				test_name = test_name.strip()
				if status.strip() == "OK":
					return "selftest_" + test_name.split()[1]
			except:
				return False
			return False

		if len(lines) == 1:
			test_name = extract_subtest_name(lines[0])
			if test_name:
				return [test_name]
			return []
		else:
			lines.pop()
			subtests = []
			for line in lines:
				subtest_name = extract_subtest_name(line)
				if subtest_name:
					subtests.append(subtest_name)
			return subtests
	return []

def find_working_selftests():
	selftests = list_selftests()
	working_subtests = []
	for test in selftests:
		subtests = extract_working_subtests(test)
		working_subtests.extend(subtests)
		from time import sleep

	return working_subtests



if __name__ == "__main__":
	print("Available selftests:")
	print(list_working_selftests())
