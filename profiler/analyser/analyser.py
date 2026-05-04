import os
import json

from event import Event
from time import time
from .utils import find_block_start, find_block_end

KERNEL_SOURCE_PATH = "/mnt/linux/"
if not os.path.isdir(KERNEL_SOURCE_PATH):
    KERNEL_SOURCE_PATH = "../linux/"


class TraceAnalyser:
    def __init__(self, program_name: str, trace: list[Event]):
        self.program_name = program_name
        self.trace = trace

    def analyse(self, verbose=True, kernel_compiler="clang"):
        self.execution_times: dict[tuple[str, int, int] | tuple[str, int, int, str], list[int]] = {}

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
                    if kernel_compiler == "clang":
                        end_line = ev.line
                        start_line = find_block_start(
                            KERNEL_SOURCE_PATH + ev.file.decode(), end_line
                        )
                    elif kernel_compiler == "gcc":
                        start_line = ev.line
                        end_line = find_block_end(
                            KERNEL_SOURCE_PATH + ev.file.decode(), start_line
                        )
                    else:
                        raise ValueError("Unsupported kernel compiler: " + kernel_compiler)

                    key = (ev.file.decode(), start_line, end_line)

                    if ev.has_arg():
                        if self.execution_times.get(key) is None:
                            self.execution_times[key] = {}
                        if self.execution_times[key].get(ev.arg) is None:
                            self.execution_times[key][ev.arg] = []
                        self.execution_times[key][ev.arg].append(ev.duration())
                    else:
                        if self.execution_times.get(key) is None:
                            self.execution_times[key] = []
                        self.execution_times[key].append(ev.duration())
                case Event.EVENT_TYPE.FUNC_TIMER_RESULT:
                    line = ev.line
                    key = (ev.file.decode(), line, line, ev.func_name.decode())
                    if self.execution_times.get(key) is None:
                        self.execution_times[key] = []
                    self.execution_times[key].append(ev.duration())

        self.total_duration = trace_end_time - trace_start_time
        if verbose:
            print(f"Total verification time: {self.total_duration / 1000000:.2f} ms")

        print(f"Analysis completed in {time() - start_time:.2f} seconds")

    def to_json(self):
        # Convert tuple keys to string for JSON
        serializable_exec_times = {}

        for key, durations in self.execution_times.items():
            filename, start, end, *rest = key
            name = rest[0] if rest else None

            dict_key = f"{filename}:{start}-{end}"
            if name is not None:
                dict_key += f":{name}"

            serializable_exec_times[dict_key] = durations


        data = {
            "program_name": self.program_name,
            "total_duration": self.total_duration,
            "execution_times": serializable_exec_times,
        }
        return json.dumps(data, indent=2)
