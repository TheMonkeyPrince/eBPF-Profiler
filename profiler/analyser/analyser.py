import json

from event import Event
from collections import defaultdict
from time import time
from .utils import find_block_end

from config import KERNEL_SOURCE_PATH

class TraceAnalyser:
    def __init__(self, program_name: str, trace: list[Event]):
        self.program_name = program_name
        self.trace = trace

    def analyse(self, verbose=True):
        self.execution_times: dict[tuple[str, int, int], list[int]] = {}

        start_time = time()

        trace_start_time = None
        trace_end_time = None
        for ev in self.trace:
            match ev.get_event_type():
                case Event.EVENT_TYPE.VERIFIER_START:
                    trace_start_time = ev.timestamp
                case Event.EVENT_TYPE.VERIFIER_END:
                    trace_end_time = ev.timestamp
                case Event.EVENT_TYPE.BLOCK_TIMER_RESULT:
                    start_line = ev.line
                    end_line = find_block_end(KERNEL_SOURCE_PATH + ev.file.decode(), start_line)

                    key = (ev.file.decode(), start_line, end_line)

                    if ev.has_insn_idx():
                        if self.execution_times.get(key) is None:
                            self.execution_times[key] = {}
                        if self.execution_times[key].get(ev.insn_idx) is None:
                            self.execution_times[key][ev.insn_idx] = []
                        self.execution_times[key][ev.insn_idx].append(ev.duration)
                    else:
                        if self.execution_times.get(key) is None:
                            self.execution_times[key] = []
                        self.execution_times[key].append(ev.duration)
                case Event.EVENT_TYPE.FUNC_TIMER_RESULT:
                    start_line = ev.line
                    end_line = ev.line
                    key = (ev.file.decode(), start_line, end_line)
                    if self.execution_times.get(key) is None:
                        self.execution_times[key] = []
                    self.execution_times[key].append(ev.duration)

        self.total_duration = trace_end_time - trace_start_time
        if verbose:
            print(f"Total verification time: {self.total_duration} ns")

        print(f"Analysis completed in {time() - start_time:.2f} seconds")

    def to_json(self):
        # Convert tuple keys to string for JSON
        serializable_exec_times = {
            f"{filename}:{start}-{end}": durations
            for (filename, start, end), durations in self.execution_times.items()
        }
        data = {
            "program_name": self.program_name,
            "total_duration": self.total_duration,
            "execution_times": serializable_exec_times,
        }
        return json.dumps(data, indent=2)
