import argparse
from profiler import BPFProfiler
from programs.kernel_samples import list_kernel_samples
from programs.kernel_selftests import list_kernel_selftests
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
		"--trace-only",
		help="Only run the profiler and save the trace without analysing it",
		action="store_true",
	)
	parser.add_argument(
		"--analysis-only",
		help="Only analyse the trace without running the profiler",
		action="store_true",
	)
	parser.add_argument(
		"--verbose",
		help="Print extra analysis messages",
		action="store_true",
	)
	parser.add_argument(
		"--no-progress",
		help="Disable analysis progress bars",
		action="store_true",
	)
	parser.add_argument(
		"--direct",
		help="Run the profiler and analyse traces directly without saving them",
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
		# tests = ["sample_tracex1"]
		# tests = ["sample_hbm", "sample_ibumad", "sample_cpustat"]
		# tests = ["sample_ibumad"]
		# tests = ["selftest_access_variable_array"]

	runned_tests = []
	try:
		profiler = BPFProfiler(verbose=args.verbose, show_progress=not args.no_progress)
		if not args.direct:
			if not args.analysis_only:
				for i, test in enumerate(tests):
					print(f"Running test: {test} ({i+1}/{len(tests)})")
					results = profiler.profile_program(test, min_insns_to_save=args.min_insns_to_save)
					if len(results) > 0:
						runned_tests.append(test)
			else:
				runned_tests = tests

			if not args.trace_only:
				for i, test in enumerate(runned_tests):
					print(f"Analysing test: {test} ({i+1}/{len(runned_tests)})")
					if result_bin_paths(test):
						profiler.analyse_trace_from_file(test)
		else:
			for i, test in enumerate(tests):
				print(f"Running and analysing test: {test} ({i+1}/{len(tests)})")
				results = profiler.profile_program(test, min_insns_to_save=args.min_insns_to_save, save=False)
				if len(results) > 0:
					profiler.analyse_traces(results)
	except KeyboardInterrupt:
		print("Stopped")


	# trace = profiler.profile_program("selftest_arena_spin_lock")
	# trace = profiler.profile_program("selftest_arg_parsing")


	# trace = profiler.profile_program("dns_matching")
	# profiler.analyse_trace("dns_matching", trace)
	# profiler.analyse_trace_from_file("sample_tracex1")