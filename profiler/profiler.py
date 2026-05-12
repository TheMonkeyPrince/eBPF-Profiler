from profiler_types import ProfilingResult, Record
from analyser import TraceAnalyser
from programs.launcher import launch_bpf_program
from recorder import BPFRecorder
from storage import read_profile_file, result_bin_paths, save_analysis, save_result


class BPFProfiler:
    def __init__(self, verbose=False):
        self.verbose = verbose
        self.recorder = None

    def profile_program(self, program_name: str, save: bool = True) -> list[ProfilingResult]:
        if not self.recorder:
            self.recorder = BPFRecorder(verbose=self.verbose)
        self.recorder.start_recording()
        proc = launch_bpf_program(program_name)
        results = self.recorder.wait_for_completion(program_name)
        proc.terminate()
        proc.wait()
        if save and results:
            for r in results:
                save_result(r)
        return results

    def analyse_trace(
        self,
        program_name: str,
        trace: list[Record],
        save: bool = True,
        bpf_insn_count: int | None = None,
    ) -> TraceAnalyser:
        a = TraceAnalyser(program_name, trace, bpf_insn_count=bpf_insn_count)
        a.analyse()
        if save:
            save_analysis(program_name, a)
        return a

    def analyse_trace_from_file(self, program_name: str, save: bool = True) -> list[TraceAnalyser]:
        paths = result_bin_paths(program_name)
        if not paths:
            raise FileNotFoundError(f"No saved profile for {program_name!r}")
        out: list[TraceAnalyser] = []
        for p in paths:
            r = read_profile_file(p, p.stem)
            insn_n = len(r.program) if r.program else None
            out.append(self.analyse_trace(r.program_name, r.trace, save, insn_n))
        return out
