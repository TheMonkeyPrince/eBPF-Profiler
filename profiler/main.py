import time
import argparse
from profiler import BPFProfiler
from selftests import list_selftests


if __name__ == "__main__":
	parser = argparse.ArgumentParser()
	parser.add_argument(
		"--test",
		help="Run a specific test (e.g. selftest_xyz)"
	)
	args = parser.parse_args()

	blacklist = [
		"selftest_arg_parsing",
		"selftest_assign_reuse",
		"selftest_btf_dedup_split"
	]

	if args.test:
		selftests = [args.test]
	else:
		# selftests = list_selftests()
		# selftests = ["selftest_bpf_gotox"]
		selftests = ["selftest_bpftool_metadata"]

		# selftests = ["selftest_access_variable_array"]

	try:
		with BPFProfiler() as profiler:

			for selftest in selftests:
				if selftest in blacklist:
					print(f"Skipping selftest: {selftest}")
					continue

				print(f"Running selftest: {selftest}")
				trace = profiler.profile_program(selftest)
				time.sleep(0.5)

			for selftest in selftests:
				if selftest in blacklist:
					continue

				print(f"Analysing selftest: {selftest}")
				profiler.analyse_trace_from_file(selftest)
	except KeyboardInterrupt:
		print("Stopped")


	# trace = profiler.profile_program("selftest_arena_spin_lock")
	# trace = profiler.profile_program("selftest_arg_parsing")


	# trace = profiler.profile_program("dns_matching")
	# profiler.analyse_trace("dns_matching", trace)
	# profiler.analyse_trace_from_file("dns_matching")