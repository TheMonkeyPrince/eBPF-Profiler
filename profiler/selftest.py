# list available top-level tests
# ./test_progs -l
# run one test by name match
# sudo ./test_progs -t xdp_bonding
# run one test by numeric id (from -l output order)
# sudo ./test_progs -n 123

# For a specific subtest inside a test:
# format: test_name/subtest_name
# sudo ./test_progs -t "test_tc_tunnel/ipv4_geneve"
# or numeric test/subtest
# sudo ./test_progs -n 45/2

import sys
import os
import sys
import subprocess
from dataclasses import dataclass

from profiler_types import BPFProgramInfo

KERNEL_SOURCE_PATH = "/mnt/linux/"
if not os.path.isdir(KERNEL_SOURCE_PATH):
    KERNEL_SOURCE_PATH = "../linux/"

@dataclass
class SelftestInfo(BPFProgramInfo):
	test_id: int = None
	subtest_id: int = None
	test_name: str = None
	subtest_name: str = None
	description: str = None	
	
	def id(self):
		if self.subtest_id is not None:
			return f"{self.test_id}/{self.subtest_id}"
		return str(self.test_id)

	def launch(self):
		process = subprocess.Popen(
			["./test_progs", "-n", self.id()],
			cwd=f"{KERNEL_SOURCE_PATH}/tools/testing/selftests/bpf",
			stdout=subprocess.PIPE,
			stderr=subprocess.PIPE,
			text=True
		)
		return process
	
	def to_analysis_file_name(self) -> str:
		file_name = f"selftest_{self.id()}"
		if self.test_name:
			file_name += f"___{self.test_name}"
			if self.subtest_name:
				file_name += f"/{self.subtest_name}"

		return file_name.replace("/", "-", 2)

	@staticmethod
	def from_analysis_file_name(file_name: str) -> 'SelftestInfo':
		fixed_name = file_name.replace("-", "/", 2).replace("___", "   ", 1)
		return SelftestInfo.from_string(fixed_name)

	@staticmethod
	def from_string(full_name: str) -> 'SelftestInfo':
		"""seltest name format:
		- [selftest_][#]id   [testname[/subtestname[: description]]]]
		- subtestname is optional, and is separated from testname by a dash
		- selftest_ prefix is optional, and is removed if present
		
		example: #598/2   verifier_map_ptr/bpf_map_ptr: read with negative offset rejected @unpriv
		"""

		parsed = full_name.strip().removeprefix("selftest_").split("   ", 1)

		def parse_selftest_numeric_id(id_str):
			"""Parse a numeric id from a selftest name."""
			id_str = id_str.removeprefix("#")
			parts = id_str.split("/", 1)
			try:
				test_id = int(parts[0])
				subtest_id = int(parts[1]) if len(parts) == 2 else None
			except ValueError:
				raise ValueError(f"Invalid selftest numeric id format: {id_str}")
			return test_id, subtest_id

		test_id, subtest_id = parse_selftest_numeric_id(parsed[0])
		selftest = SelftestInfo(test_id=test_id, subtest_id=subtest_id)

		if len(parsed) == 2:
			parsed = parsed[1].split("/", 1)
			selftest.test_name = parsed[0]
			if len(parsed) == 2:
				parsed = parsed[1].split(":", 1)
				selftest.subtest_name = parsed[0]
				if len(parsed) == 2:
					selftest.description = parsed[1].strip()

		return selftest
	
	def __str__(self):
		result = f"selftest_#{self.id()}"
		if self.subtest_id is not None:
			result += f"/{self.subtest_id}"
		if self.test_name is not None:
			result += f"   {self.test_name}"
		if self.subtest_name is not None:
			result += f"/{self.subtest_name}"
		if self.description is not None:
			result += f": {self.description}"
		return result
	
	def list_subtests(self) -> list['SelftestInfo']:
		process = self.launch()
		stdout, stderr = process.communicate()
		if process.returncode != 0:
			raise RuntimeError(f"Error running selftest {selftest}: {stderr}")
		
		subtests = []
		for line in stdout.splitlines():
			if line.startswith("#"):
				line = line.strip().rsplit(":", 1)
				if len(line) == 2:
					selftest = SelftestInfo.from_string(line[0])
					if selftest.subtest_id is not None:
						subtests.append(selftest)

		if subtests:
			return subtests
		return [selftest]
	
	def __eq__(self, other):
		if not isinstance(other, SelftestInfo):
			return NotImplemented
		return str(self) == str(other)
	
	def __hash__(self):
		return hash(str(self))

def list_selftests() -> list[SelftestInfo]:
	result = subprocess.run(
		["./test_progs", "-l"],
		cwd=f"{KERNEL_SOURCE_PATH}/tools/testing/selftests/bpf",
		capture_output=True,
		text=True
	)
	if result.returncode != 0:
		raise RuntimeError(f"Error listing selftests: {result.stderr}")
	
	selftests: list[SelftestInfo] = []
	for test_id, test_name in enumerate(result.stdout.splitlines()):
		selftests.append(SelftestInfo(test_id=test_id + 1, test_name=test_name.strip()))
	
	return selftests

if __name__ == "__main__":
	args = sys.argv
	if len(args) < 2:
		print("Usage: python kernel_selftests.py [list/<test_name>]")
		sys.exit(1)

	if args[1] == "list":
		if len(args) == 2:
			selftests = list_selftests()
			for selftest in selftests:
				print(selftest)
		else:
			test_name = args[2]
			selftest = SelftestInfo.from_string(test_name)
			for subtest in selftest.list_subtests():
				print(subtest)
	else:
		process = SelftestInfo.from_string(args[1]).launch()
		stdout, stderr = process.communicate()
		if process.returncode != 0:
			print("Error running selftest:", stderr)
		else:
			print(stdout)

