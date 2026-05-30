from profiler_types import BPFProgramInfo, ProfilingResult, ProfileStats, Record
from recorder import BPFRecorder
from storage import save_analysis

from trace_analyser import TraceAnalyser, TraceAnalyserResult


def profile_program(
    program: BPFProgramInfo,
    min_insns_to_save: int = 50,
    min_duration_to_save: int = 0, # in milliseconds
    record_time: int = 1, # in seconds
    verbose: bool = False,
) -> list[ProfilingResult]:
    recorder = BPFRecorder(verbose=verbose)
    recorder.start_recording(record_time=record_time)
    proc = program.launch()
    results = recorder.get_results(program)
    proc.terminate()
    proc.wait()

    min_duration_to_save_ns = min_duration_to_save * 1_000_000
    filtered_results = [r for r in results if len(r.program) > min_insns_to_save and r.duration() > min_duration_to_save_ns]
    return filtered_results

def analyse_trace(
    profiling_result: ProfilingResult,
    save: bool = True,
    verbose: bool = False,
) -> TraceAnalyserResult | None:
    analyser = TraceAnalyser(profiling_result)
    result = analyser.analyse(verbose=verbose)
    if result and save:
        save_analysis(profiling_result.program_info, result, profiling_result.trace_index)
    return result