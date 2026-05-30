from storage import *

class GlobalAnalyser:
	def __init__(self, verbose=False):
		self.verbose = verbose
		self.programs: dict[str, list[dict]] = {}


	def global_analysis(self, save_programs=False):
		programs = list_analysed_programs()
		if not programs:
			print("No analysed programs found.")
			return
		else:
			print(f"Found {len(programs)} analysed programs with a total of {len(list_analysis_files())} analysis files.")

		if save_programs:
			save_program_list(list(programs.keys()))
			print(f"Saved list of analysed programs")

		analysis_list: list[TraceAnalyserResult] = [
			r
			for lists in programs.values()
			for r in lists
		]

		# sort analysis by descending order of total time
		analysis_list.sort(key=lambda a: a.stats["verification_time"], reverse=True)
		with open("out/time_analysis.txt", "w") as f:
			for a in analysis_list:
				f.write(f"{a.program_name} ({a.stats['program_length']} insns): {a.stats['verification_time']/1000000:.2f} ms\n")

		