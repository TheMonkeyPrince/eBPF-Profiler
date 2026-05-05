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
	args = parser.parse_args()

	if args.test:
		tests = [args.test]
	else:
		tests = ["sample_tracex1"]

	runned_tests = []
	try:
		with BPFProfiler() as profiler:

			for test in tests:
				print(f"Running test: {test}")
				trace = profiler.profile_program(test)
				if len(trace) > 0:
					runned_tests.append(test)

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