import os
import json

from event import Event
from analyser.analyser import TraceAnalyser


def load_trace(program_name: str) -> list[Event]:
    trace = []
    event_size = Event.size()
    with open(f"out/traces/{program_name}.bin", "rb") as f:
        while chunk := f.read(event_size):
            if len(chunk) != event_size:
                raise ValueError(f"Incomplete event data: expected {event_size} bytes, got {len(chunk)}")
            event = Event.from_bytes(chunk)
            trace.append(event)
    return trace


def save_trace(program_name: str, trace: list[Event]):
    os.makedirs("out/traces", exist_ok=True)
    with open(f"out/traces/{program_name}.bin", "wb") as f:
        for ev in trace:
            f.write(bytes(ev))
    print(f"Trace saved to out/traces/{program_name}.bin")


def load_analysis(program_name: str) -> dict:
    with open(f"out/analysis/{program_name}.json", "r") as f:
        return json.load(f)


def save_analysis(program_name: str, trace_analyser: TraceAnalyser):
    os.makedirs("out/analysis", exist_ok=True)
    with open(f"out/analysis/{program_name}.json", "w") as f:
        f.write(trace_analyser.to_json())
    print(f"Analysis saved to out/analysis/{program_name}.json")
