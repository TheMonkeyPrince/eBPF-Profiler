import json
import struct
from pathlib import Path
from shutil import rmtree

from trace_analyser import TraceAnalyserResult
from profiler_types import BPFProgramInfo, BPFInsn, ProfilingResult, Record, ProfileStats

OUT_DIR = Path("out")
ANALYSIS_DIR = Path("out/analysis")
SAVED_PROGRAM_LIST_FILE = OUT_DIR / "program_list.txt"

def _read_block(f, item_size: int, from_bytes):
	hdr = f.read(4)
	if len(hdr) != 4:
		raise ValueError("corrupt profile: short header")
	(n,) = struct.unpack("<I", hdr)
	blob = f.read(n * item_size)
	if len(blob) != n * item_size:
		raise ValueError("corrupt profile: truncated block")
	return [from_bytes(blob[i * item_size : (i + 1) * item_size]) for i in range(n)]


# def read_profile_result_file(path: str | Path, program_info: BPFProgramInfo, trace_index: int) -> ProfilingResult:
# 	with open(path, "rb") as file:
# 		result = read_profiling_result(file, program_info, trace_index)
# 	return result

def read_profiling_result(file, program_info: BPFProgramInfo, trace_index: int) -> ProfilingResult:
	program = _read_block(file, BPFInsn.size(), BPFInsn.from_bytes)
	stats = ProfileStats.from_bytes(file.read(ProfileStats.size()))
	trace = _read_block(file, Record.size(), Record.from_bytes)
	return ProfilingResult(program_info, trace_index, program, stats, trace)

def save_analysis(program_info: BPFProgramInfo, analysis_result: TraceAnalyserResult, index: int = 0):
	filename = program_info.to_analysis_file_name() + f"-{index}"
	path = ANALYSIS_DIR / f"{filename}.json"
	path.parent.mkdir(parents=True, exist_ok=True)

	data = analysis_result.to_json()
	if len(data.encode("utf-8")) > 5 * 1024**3:  # 5 GiB
		print(f"Warning: analysis for {filename!r} is very large ({len(data.encode('utf-8')) / (1024**3):.2f} GiB): file discarded to avoid filling up the disk.")
		return

	path.write_text(data, encoding="utf-8")

def read_analysis(filename: str) -> TraceAnalyserResult:
	path = ANALYSIS_DIR / filename
	if not path.is_file():
		raise FileNotFoundError(f"No analysis found for program {filename!r}")
	with open(path, "r", encoding="utf-8") as f:
		return TraceAnalyserResult.from_json(f.read())

def list_analysis_files() -> list[str]:
	if not ANALYSIS_DIR.is_dir():
		return []
	
	return [path.name for path in ANALYSIS_DIR.glob("*.json")]

def list_analysed_programs() -> dict[BPFProgramInfo, list[TraceAnalyserResult]]:
	results = list_analysis_files()
	programs: dict[BPFProgramInfo, list[TraceAnalyserResult]] = {}
	for r in results:
		program_name = r.rsplit(".", 1)[0].rsplit("-", 1)[0]
		program_info = BPFProgramInfo.from_analysis_file_name(program_name)
		if program_info not in programs:
			programs[program_info] = []
		programs[program_info].append(read_analysis(r))
	return dict(sorted(programs.items(), key=lambda item: item[0]))


def save_program_list(programs: list[BPFProgramInfo]):
	SAVED_PROGRAM_LIST_FILE.parent.mkdir(parents=True, exist_ok=True)
	with open(SAVED_PROGRAM_LIST_FILE, "w") as f:
		for program in programs:
			f.write(str(program) + "\n")

def read_saved_program_list() -> list[BPFProgramInfo]:
	if not (SAVED_PROGRAM_LIST_FILE).is_file():
		return []
	with open(SAVED_PROGRAM_LIST_FILE, "r") as f:
		return [BPFProgramInfo.from_string(line.strip()) for line in f if line.strip()]
