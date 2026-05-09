import argparse
from profiler import BPFProfiler
from programs.kernel_selftests import list_working_selftests


if __name__ == "__main__":
	parser = argparse.ArgumentParser()
	parser.add_argument(
		"--test",
		help="Run a specific test (e.g. selftest_xyz, sample_abc)",
		type=str,
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
		tests = ["sample_tracex1"]
		tests = ["sample_hbm", "sample_ibumad", "sample_cpustat"]
		tests = ["sample_ibumad"]
		# tests = ["selftest_access_variable_array"]

	runned_tests = []
	try:
		profiler = BPFProfiler()
		for test in tests:
			print(f"Running test: {test}")
			trace = profiler.profile_program(test)
			if len(trace) > 0:
				runned_tests.append(test)

		if not args.no_analysis:
			for test in runned_tests:
				print(f"Analysing test: {test}")
				profiler.analyse_trace_from_file(test)
	except KeyboardInterrupt:
		print("Stopped")


	# trace = profiler.profile_program("selftest_arena_spin_lock")
	# trace = profiler.profile_program("selftest_arg_parsing")


	# trace = profiler.profile_program("dns_matching")
	# profiler.analyse_trace("dns_matching", trace)
	# profiler.analyse_trace_from_file("sample_tracex1")