import argparse
from profiler import BPFProfiler
from programs.kernel_samples import list_kernel_samples
from programs.kernel_selftests import list_kernel_selftests


if __name__ == "__main__":
	parser = argparse.ArgumentParser()
	parser.add_argument(
		"--test",
		help="Run a specific test (e.g. selftest_xyz, sample_abc)",
		type=str,
	)
	parser.add_argument(
		"--min-insns-to-save",
		help="Only write out/results/*.bin when the BPF program has more than this many insns (default: 50)",
		type=int,
		default=200,
	)
	parser.add_argument(
		"--verbose",
		help="Print extra analysis messages",
		action="store_true",
	)
	parser.add_argument(
		"--progress",
		help="Show analysis progress bars",
		action="store_true",
	)
	args = parser.parse_args()

	if args.test:
		if args.test == "samples":
			tests = list_kernel_samples()
		elif args.test == "selftests":
			tests = list_kernel_selftests()
		else:
			tests = [args.test]
	else:
		tests = list_kernel_selftests() + list_kernel_samples()

	runned_tests = []
	try:
		profiler = BPFProfiler(verbose=args.verbose, show_progress=args.progress)
		for i, test in enumerate(tests):
			print(f"Running and analysing test: {test} ({i+1}/{len(tests)})")
			results = profiler.profile_program(test, min_insns_to_save=args.min_insns_to_save, save=False)
			for r in results:
				profiler.new_analyse_trace(r, save=True)
	except KeyboardInterrupt:
		print("Stopped")