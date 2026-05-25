import argparse
from time import time
from profiler import BPFProfiler
from programs.kernel_samples import list_kernel_samples
from programs.kernel_selftests import list_kernel_selftests

from storage import read_saved_program_list

from global_analyser import GlobalAnalyser

if __name__ == "__main__":
	parser = argparse.ArgumentParser()
	parser.add_argument(
		"--test",
		help="Run a specific test (e.g. selftest_xyz, sample_abc)",
		type=str,
	)
	parser.add_argument(
		"--min-insns",
		help="Only save results for BPF program executions that have more than this many instructions (default: 200)",
		type=int,
		default=200,
	)
	parser.add_argument(
		"--min-duration",
		help="Only save results for BPF program executions that last longer than this many milliseconds (default: 10)",
		type=int,
		default=10,
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
	parser.add_argument(
		"--record-time",
		help="Duration to record the BPF program execution in seconds (default: 1)",
		type=int,
		default=1,
	)
	parser.add_argument(
		"--global-analysis-only",
		help="Only perform global analysis on existing analysis files, without running new profiles",
		action="store_true",
	)
	parser.add_argument(
		"--save-program-list",
		help="Save the list of analysed programs to a file",
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
		tests = read_saved_program_list()

	if not args.global_analysis_only:
		start_time = time()
		runned_tests = []
		try:
			profiler = BPFProfiler(verbose=args.verbose, show_progress=args.progress)
			for i, test in enumerate(tests):
				print(f"Running and analysing test: {test} ({i+1}/{len(tests)})")
				results = profiler.profile_program(test, min_insns_to_save=args.min_insns, min_duration_to_save=args.min_duration, save=False, record_time=args.record_time)
				for r in results:
					profiler.new_analyse_trace(r, save=True)
		except KeyboardInterrupt:
			print("Stopped")
		end_time = time()
		total_time = end_time - start_time
		print(f"Done in: {int(total_time/60)} minutes and {int(total_time%60)} seconds")

	global_analyser = GlobalAnalyser(verbose=args.verbose, show_progress=args.progress)
	global_analyser.global_analysis(save_programs=args.save_program_list)