from storage import *

class GlobalAnalyser:
	def __init__(self, verbose=False, show_progress=True):
		self.verbose = verbose
		self.show_progress = show_progress
		self.programs: dict[str, list[dict]] = {}


	def global_analysis(self, save_programs=False):
		programs = list_analysed_programs()
		print(f"Found {len(programs)} analysed programs with a total of {len(list_analysis_files())} analysis files.")

		if save_programs:
			save_program_list(programs)
			print(f"Saved list of analysed programs")

		self.programs = {}
		analyis = []
		for program in programs:
			analysis_files = list_analysis_for_program(program)
			self.programs[program] = [read_analysis(f) for f in analysis_files]
			analyis.extend(self.programs[program])

		# sort analysis by descending order of total time
		analyis.sort(key=lambda a: a["stats"]["verification_time"], reverse=True)
		with open("out/time_analysis.txt", "w") as f:
			for a in analyis:
				f.write(f"{a['program_name']} ({a['stats']['program_length']} insns): {a['stats']['verification_time']/1000000:.2f} ms\n")

		