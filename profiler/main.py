import time
import argparse
from profiler import BPFProfiler
from selftests import list_working_selftests


if __name__ == "__main__":
	parser = argparse.ArgumentParser()
	parser.add_argument(
		"--test",
		help="Run a specific test (e.g. selftest_xyz)"
	)
	args = parser.parse_args()

	if args.test:
		selftests = [args.test]
	else:
		selftests = list_working_selftests()
		# selftests = ["selftest_bpf_gotox"]
		# selftests = ["selftest_arg_parsing/test_parse_test_list"]
		# selftests = ["selftest_bpftool_metadata"]

		# selftests = ["selftest_access_variable_array"]

	runned_tests = []
	try:
		with BPFProfiler() as profiler:

			for selftest in selftests:
				print(f"Running selftest: {selftest}")
				trace = profiler.profile_program(selftest)
				if len(trace) > 0:
					runned_tests.append(selftest)

			for selftest in runned_tests:
				print(f"Analysing selftest: {selftest}")
				profiler.analyse_trace_from_file(selftest)
	except KeyboardInterrupt:
		print("Stopped")


	# trace = profiler.profile_program("selftest_arena_spin_lock")
	# trace = profiler.profile_program("selftest_arg_parsing")


	# trace = profiler.profile_program("dns_matching")
	# profiler.analyse_trace("dns_matching", trace)
	# profiler.analyse_trace_from_file("dns_matching")