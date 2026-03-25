import os
from bcc import BPF

from event import Event


class BPFRecorder:
    def __init__(self, verbose=True):
        self.started = False
        self.finished = False

        self.verbose = verbose
        self.bpf = BPF(src_file=f"{os.path.dirname(__file__)}/bpf_recorder.c")

        # Attach kprobes to the kernel function "bpf_check"
        self.bpf.attach_kprobe(event="bpf_check", fn_name="verifier_start")
        self.bpf.attach_kretprobe(event="bpf_check", fn_name="verifier_end")

        self.bpf.attach_kprobe(
            event="bpf_profiler_func_timer_result", fn_name="func_timer_result"
        )
        self.bpf.attach_kprobe(
            event="bpf_profiler_block_timer_result", fn_name="block_timer_result"
        )

        def handle_event(cpu, data, size):
            e = Event.cast_from_pointer(data)
            if self.verbose and e.get_event_type():
                print(f"Received event: {e.get_event_type().name}")

            if (
                not self.started
                and e.get_event_type() == Event.EVENT_TYPE.VERIFIER_START
            ):
                self.started = True
                self.trace.append(e)
                print(f"Trace started for program: {self.program_name}")
                return

            self.trace.append(e)

            match e.get_event_type():
                case Event.EVENT_TYPE.VERIFIER_START:
                    raise ValueError(
                        "Received VERIFIER_START event while a trace is already in progress"
                    )
                case Event.EVENT_TYPE.VERIFIER_END:
                    if self.started and not self.finished:
                        self.finished = True
                        print(f"Trace finished for program: {self.program_name}")

        self.bpf["events"].open_perf_buffer(handle_event)

    def record_events(self, program_name: str) -> list[Event]:
        self.started = False
        self.finished = False
        self.program_name = program_name
        self.trace = []

        print("Listening for kernel events...")
        while not self.finished:
            self.bpf.perf_buffer_poll()
        return list(self.trace)
