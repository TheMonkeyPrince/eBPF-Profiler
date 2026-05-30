import argparse
from time import time

from profiler import profile_program, analyse_trace
from profiler_types import BPFProgramInfo
from selftest import SelftestInfo, list_selftests

from storage import read_saved_program_list

from global_analyser import GlobalAnalyser

def profile_and_analyse(test: BPFProgramInfo, min_insns_to_save: int, min_duration_to_save: int, record_time: int, verbose=False, show_progress=True):
	results = profile_program(test, min_insns_to_save=min_insns_to_save, min_duration_to_save=min_duration_to_save, record_time=record_time, verbose=verbose)
	for r in results:
		analyse_trace(r, save=True, verbose=verbose)

def recording(tests: list[BPFProgramInfo], min_insns_to_save: int, min_duration_to_save: int, record_time: int, verbose=False, show_progress=True):
	for i, test in enumerate(tests):
		print(f"Running and analysing test: {test} ({i+1}/{len(tests)})")
		profile_and_analyse(test, min_insns_to_save=min_insns_to_save, min_duration_to_save=min_duration_to_save, record_time=record_time, verbose=verbose, show_progress=show_progress)

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
		default=8,
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
		"--global-analysis",
		help="Perform global analysis on existing analysis files",
		action="store_true",
	)
	parser.add_argument(
		"--recording",
		help="Perform recording",
		action="store_true",
	)
	parser.add_argument(
		"--save-program-list",
		help="Save the list of analysed programs to a file",
		action="store_true",
	)
	parser.add_argument(
		"--resolve-subtests",
		help="Resolve subtests for a given selftest",
		action="store_true",
	)

	args = parser.parse_args()

	if args.recording:
		
		if args.test:
			if args.test == "selftests":
				tests = list_selftests()
			else:
				tests = [BPFProgramInfo.from_string(args.test)]
		else:
			tests = read_saved_program_list()

		if args.resolve_subtests:
			print("Resolving subtests...")
			resolved_subtests = []
			for test in tests:
				if isinstance(test, SelftestInfo):
					subtests = test.list_subtests()	
					resolved_subtests.extend(subtests)
				else:
					resolved_subtests.append(test)
			tests = resolved_subtests
			print("Done resolving subtests")

		start_time = time()
		try:
			recording(tests, min_insns_to_save=args.min_insns, min_duration_to_save=args.min_duration, record_time=args.record_time, verbose=args.verbose, show_progress=args.progress)
			print("Recording and analysis completed")
		except KeyboardInterrupt:
			print("Stopped")
		end_time = time()
		total_time = end_time - start_time
		print(f"Done in: {int(total_time/60)} minutes and {int(total_time%60)} seconds")

	if args.global_analysis:
		global_analyser = GlobalAnalyser(verbose=args.verbose)
		global_analyser.global_analysis(save_programs=args.save_program_list)