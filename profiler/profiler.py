from profiler_types import BPFProgramInfo, ProfilingResult, ProfileStats, Record
from trace_analyser import TraceAnalyser
from recorder import BPFRecorder
from storage import save_analysis

from trace_analyser import TraceAnalyser

class BPFProfiler:
    def __init__(self, verbose=False, show_progress=True):
        self.verbose = verbose
        self.show_progress = show_progress
        self.recorder = None

    def profile_program(
        self,
        program: BPFProgramInfo,
        min_insns_to_save: int = 50,
        min_duration_to_save: int = 0, # in milliseconds
        record_time: int = 1, # in seconds
    ) -> list[ProfilingResult]:
        if not self.recorder:
            self.recorder = BPFRecorder(verbose=self.verbose)
        self.recorder.start_recording(record_time=record_time)
        proc = program.launch()
        results = self.recorder.wait_for_completion(program)
        proc.terminate()
        proc.wait()

        min_duration_to_save_ns = min_duration_to_save * 1_000_000
        filtered_results = [r for r in results if len(r.program) > min_insns_to_save and r.duration() > min_duration_to_save_ns]
        return filtered_results

    def analyse_trace(
        self,
        profiling_result: ProfilingResult,
        save: bool = True,
    ) -> TraceAnalyser:
        analyser = TraceAnalyser(profiling_result)
        result = analyser.analyse(verbose=self.verbose)
        if result and save:
            save_analysis(profiling_result.program_info, result, profiling_result.trace_index)
        return analyser
    
    # def analyse_trace_from_file(self, program_name: str, save: bool = True) -> list[TraceAnalyser]:
    #     paths = result_bin_paths(program_name)
    #     if not paths:
    #         raise FileNotFoundError(f"No saved profile for {program_name!r}")
    #     out: list[TraceAnalyser] = []
    #     for p in paths:
    #         r = read_profile_file(p, p.stem)
    #         out.append(
    #             self.analyse_trace(
    #                 r.program_name, r.trace, save, program=r.program, stats=r.stats
    #             )
    #         )
    #     return out
