import argparse
from profiler import BPFProfiler
from programs.kernel_samples import list_kernel_samples
from programs.kernel_selftests import list_working_selftests
from storage import result_bin_paths


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
		default=25,
	)
	parser.add_argument(
		"--no-analysis",
		help="Only run the profiler without analysing the trace",
		action="store_true",
	)
	args = parser.parse_args()

	if args.test:
		tests = [args.test]
	else:
		tests = list_kernel_samples()
		# tests = ["sample_hbm", "sample_ibumad", "sample_cpustat"]
		# tests = ["sample_tracex1"]
		# tests = ["sample_hbm", "sample_ibumad", "sample_cpustat"]
		# tests = ["sample_ibumad"]
		# tests = ["selftest_access_variable_array"]

	runned_tests = []
	try:
		profiler = BPFProfiler()
		for test in tests:
			print(f"Running test: {test}")
			results = profiler.profile_program(test, min_insns_to_save=args.min_insns_to_save)
			if len(results) > 0:
				runned_tests.append(test)

		if not args.no_analysis:
			for test in runned_tests:
				print(f"Analysing test: {test}")
				if result_bin_paths(test):
					profiler.analyse_trace_from_file(test)
	except KeyboardInterrupt:
		print("Stopped")


	# trace = profiler.profile_program("selftest_arena_spin_lock")
	# trace = profiler.profile_program("selftest_arg_parsing")


	# trace = profiler.profile_program("dns_matching")
	# profiler.analyse_trace("dns_matching", trace)
	# profiler.analyse_trace_from_file("sample_tracex1")