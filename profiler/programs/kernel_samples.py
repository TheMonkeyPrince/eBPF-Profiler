import os
import sys
import subprocess

KERNEL_SOURCE_PATH = "/mnt/linux/"
if not os.path.isdir(KERNEL_SOURCE_PATH):
	KERNEL_SOURCE_PATH = "../linux/"


def get_kernel_samples():
	print("Getting kernel samples...")
	print(KERNEL_SOURCE_PATH)


def run_kernel_samples(sample_name: str) -> subprocess.Popen[str]:
	if sample_name.startswith("sample_"):
		sample_name = sample_name[len("sample_") :]

	process = subprocess.Popen(
		["./" + sample_name],
		cwd=f"{KERNEL_SOURCE_PATH}/samples/bpf",
		stdout=subprocess.PIPE,
		stderr=subprocess.PIPE,
		text=True,
	)
	return process


if __name__ == "__main__":
	if len(sys.argv) < 2:
		print("Usage: python kernel_samples.py <sample_name>")
		sys.exit(1)

	sample_name = sys.argv[1]
	process = run_kernel_samples(sample_name)
	stdout, stderr = process.communicate()
	if process.returncode == 0:
		print(stdout)
	else:
		print(stderr)
