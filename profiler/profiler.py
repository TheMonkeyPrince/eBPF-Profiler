from event import Event
from recorder.recorder import BPFRecorder
from analyser.analyser import TraceAnalyser
from launcher import launch_bpf_program
from storage import save_trace, load_trace, save_analysis, load_analysis


class BPFProfiler:
	def __init__(self, verbose=False):
		self.verbose = verbose
		self.recorder = None

	def profile_program(self, program_name: str, save: bool = True) -> list[Event]:
		if not self.recorder:
			self.recorder = BPFRecorder(verbose=self.verbose)


		self.recorder.start_recording(program_name)
		process = launch_bpf_program(program_name)
		trace = self.recorder.wait_for_completion()
		process.terminate()
		process.wait()

		if save:
			save_trace(program_name, trace)
		return trace

	def analyse_trace(
		self, program_name: str, trace: list[Event], save: bool = True
	) -> TraceAnalyser:
		analyser = TraceAnalyser(program_name, trace)
		analyser.analyse()
		if save:
			save_analysis(program_name, analyser)
		return analyser

	def analyse_trace_from_file(
		self, program_name: str, save: bool = True
	) -> TraceAnalyser:
		trace = load_trace(program_name)
		return self.analyse_trace(program_name, trace, save=save)

	def __enter__(self):
		return self
	
	def __exit__(self, exc_type, exc, tb):
		if self.recorder:
			self.recorder.unload()