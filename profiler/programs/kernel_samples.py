import os
import sys
import subprocess
from pathlib import Path

KERNEL_SOURCE_PATH = "/mnt/linux/"
if not os.path.isdir(KERNEL_SOURCE_PATH):
	KERNEL_SOURCE_PATH = "../linux/"

SAMPLES_PATH = f"{KERNEL_SOURCE_PATH}/samples/bpf"

def get_kernel_samples():
	directory = Path(SAMPLES_PATH)

	executables = [
		"sample_" + f.name for f in directory.iterdir()
		if f.is_file() and os.access(f, os.X_OK) and f.suffix == ""
	]

	for exe in executables:
		print(exe)


def run_kernel_samples(sample_name: str) -> subprocess.Popen[str]:
	if sample_name.startswith("sample_"):
		sample_name = sample_name[len("sample_") :]

	process = subprocess.Popen(
		["./" + sample_name],
		cwd=SAMPLES_PATH,
		stdout=subprocess.PIPE,
		stderr=subprocess.PIPE,
		text=True,
	)
	return process


if __name__ == "__main__":
	if len(sys.argv) < 2:
		print("Usage: python kernel_samples.py <sample_name>")
		sys.exit(1)

	if sys.argv[1] == "list":
		get_kernel_samples()
		sys.exit(0)

	sample_name = sys.argv[1]
	process = run_kernel_samples(sample_name)
	stdout, stderr = process.communicate()
	if process.returncode == 0:
		print(stdout)
	else:
		print(stderr)
