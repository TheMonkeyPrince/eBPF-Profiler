import os
import json
import struct

from profiler_types import ProfilingResult, BPFInsn, Record
from analyser import TraceAnalyser

def fix_program_name(program_name: str) -> str:
    return program_name.replace("/", ".")

def load_trace(program_name: str) -> list[Record]:
    program_name = fix_program_name(program_name)
    trace = []
    event_size = Record.size()
    with open(f"out/traces/{program_name}.bin", "rb") as f:
        while chunk := f.read(event_size):
            if len(chunk) != event_size:
                raise ValueError(f"Incomplete event data: expected {event_size} bytes, got {len(chunk)}")
            event = Record.from_bytes(chunk)
            trace.append(event)
    return trace


def save_result(result: ProfilingResult):
    program_name = fix_program_name(program_name)
    os.makedirs("out/results", exist_ok=True)
    with open(f"out/results/{program_name}.bin", "wb") as f:
        
        for ev in result.trace:
            f.write(bytes(ev))
    # print(f"Trace saved to out/traces/{program_name}.bin")

def load_analysis(program_name: str) -> dict:
    program_name = fix_program_name(program_name)
    with open(f"out/analysis/{program_name}.json", "r") as f:        return json.load(f)

def save_analysis(program_name: str, trace_analyser: TraceAnalyser):
    program_name = fix_program_name(program_name)
    os.makedirs("out/analysis", exist_ok=True)
    with open(f"out/analysis/{program_name}.json", "w") as f:
        f.write(trace_analyser.to_json())
    # print(f"Analysis saved to out/analysis/{program_name}.json")

def read_profile_file(file_path: str, program_name: str) -> ProfilingResult:
    with open(file_path, "rb") as f:
        return read_result(f, program_name)

def read_result(file, program_name: str) -> ProfilingResult:
    program = read_bpf_program(file)
    trace = read_trace(file)
    return ProfilingResult(program_name, program, trace)

def read_bpf_program(file) -> list[BPFInsn]:
    len_bytes = file.read(4)
    if len(len_bytes) != 4:
        raise ValueError("Corrupted file: partial count")

    (program_len,) = struct.unpack("<I", len_bytes)
    insn_size = BPFInsn.size()
    raw = file.read(program_len * insn_size)
    if len(raw) != program_len * insn_size:
        raise ValueError("Corrupted file: truncated BPF program block")

    program = []
    for i in range(program_len):
        chunk = raw[i * insn_size : (i + 1) * insn_size]
        program.append(BPFInsn.from_bytes(chunk))

    return program

def read_trace(file) -> list[Record]:
    len_bytes = file.read(4)
    if len(len_bytes) != 4:
        raise ValueError("Corrupted file: partial count")

    (record_count,) = struct.unpack("<I", len_bytes)
    record_size = Record.size()
    raw = file.read(record_count * record_size)
    if len(raw) != record_count * record_size:
        raise ValueError("Corrupted file: truncated record block")

    records = []
    for i in range(record_count):
        chunk = raw[i * record_size : (i + 1) * record_size]
        records.append(Record.from_bytes(chunk))

    return records

def save_result(result: ProfilingResult):
    program_name = fix_program_name(result.program_name)
    os.makedirs("out/results", exist_ok=True)
    with open(f"out/results/{program_name}.bin", "wb") as f:
        # Write program
        program_len = len(result.program)
        f.write(struct.pack("<I", program_len))
        for insn in result.program:
            f.write(bytes(insn))

        # Write trace
        record_count = len(result.trace)
        f.write(struct.pack("<I", record_count))
        for record in result.trace:
            f.write(bytes(record))
        