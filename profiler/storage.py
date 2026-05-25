import json
import struct
from pathlib import Path

from analyser import TraceAnalyser
from profiler_types import BPFInsn, ProfilingResult, Record, ProfileStats

OUT_DIR = Path("out")
RESULTS_DIR = Path("out/results")
ANALYSIS_DIR = Path("out/analysis")
SAVED_PROGRAM_LIST_FILE = OUT_DIR / "program_list.txt"

def result_bin_paths(name: str) -> list[Path]:
	if not RESULTS_DIR.is_dir():
		return []
	out: list[Path] = []
	exact = RESULTS_DIR / f"{name}.bin"
	if exact.is_file():
		out.append(exact)
	prefix = f"{name}_"
	numbered = sorted(
		RESULTS_DIR.glob(f"{name}_*.bin"),
		key=lambda p: (
			int(p.stem[len(prefix) :])
			if p.stem.startswith(prefix) and p.stem[len(prefix) :].isdigit()
			else 10**9
		),
	)
	out.extend(p for p in numbered if p not in out)
	return out


def _read_block(f, item_size: int, from_bytes):
	hdr = f.read(4)
	if len(hdr) != 4:
		raise ValueError("corrupt profile: short header")
	(n,) = struct.unpack("<I", hdr)
	blob = f.read(n * item_size)
	if len(blob) != n * item_size:
		raise ValueError("corrupt profile: truncated block")
	return [from_bytes(blob[i * item_size : (i + 1) * item_size]) for i in range(n)]


def read_profile_file(path: str | Path, program_name: str) -> ProfilingResult:
	with open(path, "rb") as file:
		result = read_profile(file, program_name)
	return result

def read_profile(file, program_name: str) -> ProfilingResult:
	program = _read_block(file, BPFInsn.size(), BPFInsn.from_bytes)
	stats = ProfileStats.from_bytes(file.read(ProfileStats.size()))
	trace = _read_block(file, Record.size(), Record.from_bytes)
	return ProfilingResult(program_name, program, stats, trace)

def save_result(result: ProfilingResult):
	RESULTS_DIR.mkdir(parents=True, exist_ok=True)
	with open(RESULTS_DIR / f"{result.program_name}.bin", "wb") as f:
		f.write(struct.pack("<I", len(result.program)))
		for insn in result.program:
			f.write(bytes(insn))
		f.write(bytes(result.stats))
		f.write(struct.pack("<I", len(result.records)))
		for rec in result.records:
			f.write(bytes(rec))


# def load_analysis(name: str) -> dict:
# 	path = ANALYSIS_DIR / f"{name}.json"
# 	with open(path, "r", encoding="utf-8") as f:
# 		return json.load(f)


def save_analysis(name: str, analyser: TraceAnalyser):
	path = ANALYSIS_DIR / f"{name}.json"
	path.parent.mkdir(parents=True, exist_ok=True)

	data = analyser.to_json()
	if len(data.encode("utf-8")) > 5 * 1024**3:  # 5 GiB
		print(f"Warning: analysis for {name!r} is very large ({len(data.encode('utf-8')) / (1024**3):.2f} GiB): file discarded to avoid filling up the disk.")
		return

	path.write_text(data, encoding="utf-8")

def read_analysis(filename: str) -> dict:
	path = ANALYSIS_DIR / filename
	if not path.is_file():
		raise FileNotFoundError(f"No analysis found for program {filename!r}")
	with open(path, "r", encoding="utf-8") as f:
		return json.load(f)

def list_analysis_files():
	if not ANALYSIS_DIR.is_dir():
		return []
	
	return [path.name for path in ANALYSIS_DIR.glob("*.json")]

def list_analysed_programs():
	results = list_analysis_files()
	programs = set()
	for r in results:
		program_name = r.rsplit(".", 1)[0].rsplit("_", 1)[0]
		programs.add(program_name)

	return list(programs)

def list_analysis_for_program(program_name: str):
	return [path.name for path in ANALYSIS_DIR.glob(f"{program_name}*.json")]

def save_program_list(programs: list[str]):
	SAVED_PROGRAM_LIST_FILE.parent.mkdir(parents=True, exist_ok=True)
	with open(SAVED_PROGRAM_LIST_FILE, "w") as f:
		for program in programs:
			f.write(program + "\n")

def read_saved_program_list() -> list[str]:
	if not (SAVED_PROGRAM_LIST_FILE).is_file():
		return []
	with open(SAVED_PROGRAM_LIST_FILE, "r") as f:
		return [line.strip() for line in f if line.strip()]
	