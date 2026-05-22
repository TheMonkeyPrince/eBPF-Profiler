import ctypes as ct
from enum import Enum

BPF_PROFILE_MAX_RECORDS = 805306368 # 24GB at 32 bytes per record

FileId = int
LineNumber = int
FunctionName = str
InsnIdx = int
Site = tuple[FileId, LineNumber]

class RecordType(Enum):
	START = 0
	END = 1
	BLOCK = 2
	CALL = 3


class Record(ct.Structure):
	NO_INSN_IDX = ct.c_uint32(-1).value

	_fields_ = [
		("start_time", ct.c_uint64),
        ("end_time", ct.c_uint64),
        ("line", ct.c_uint32),
        ("insn_idx", ct.c_uint32),
        ("type", ct.c_int),
        ("file_id", ct.c_uint8),
        ("_pad", ct.c_uint8 * 3),
	]

	def get_record_type(self):
		return RecordType(self.type)

	def has_insn_idx(self):
		return self.get_record_type() in {RecordType.BLOCK, RecordType.CALL} and self.insn_idx != Record.NO_INSN_IDX

	def duration(self):
		if self.get_record_type() in {RecordType.BLOCK, RecordType.CALL}:
			if self.end_time < self.start_time:
				raise ValueError(f"Record has end_time {self.end_time} less than start_time {self.start_time}, which should be impossible.")
			return self.end_time - self.start_time
		return None

	def _decode_cstr(self, field: bytes):
		return field.split(b"\x00", 1)[0].decode(errors="replace")

	def __str__(self):
		return (
			f"[type={self.get_record_type().name}, file_id={self.file_id}, "
			f"line={self.line}, "
			f"insn_idx={self.insn_idx}, start_time={self.start_time}, end_time={self.end_time}]"
		)

	@staticmethod
	def from_bytes(data):
		if len(data) != ct.sizeof(Record):
			raise ValueError(f"Invalid data size: expected {ct.sizeof(Record)}, got {len(data)}")
		record = Record()
		ct.memmove(ct.addressof(record), data, ct.sizeof(Record))
		return record

	@staticmethod
	def size():
		return ct.sizeof(Record)
assert ct.sizeof(Record) == 32

BPFInsnCode = ct.c_uint8
class BPFInsn(ct.Structure):
	_pack_ = 1
	_fields_ = [
		("code", BPFInsnCode),
		("_regs", ct.c_uint8),
		("off", ct.c_int16),
		("imm", ct.c_int32),
	]

	@property
	def dst_reg(self):
		return self._regs & 0x0F

	@dst_reg.setter
	def dst_reg(self, value):
		self._regs = (self._regs & 0xF0) | (value & 0x0F)

	@property
	def src_reg(self):
		return (self._regs >> 4) & 0x0F

	@src_reg.setter
	def src_reg(self, value):
		self._regs = (self._regs & 0x0F) | ((value & 0x0F) << 4)

	def __str__(self):
		return (
			f"[code=0x{self.code:02x}, "
			f"dst_reg={self.dst_reg}, "
			f"src_reg={self.src_reg}, "
			f"off={self.off}, "
			f"imm={self.imm}]"
		)

	@staticmethod
	def from_bytes(data):
		if len(data) != ct.sizeof(BPFInsn):
			raise ValueError(
				f"Invalid data size: expected {ct.sizeof(BPFInsn)}, got {len(data)}"
			)

		insn = BPFInsn()
		ct.memmove(ct.addressof(insn), data, ct.sizeof(BPFInsn))
		return insn

	@staticmethod
	def size():
		return ct.sizeof(BPFInsn)

	def __eq__(self, other):
		if not isinstance(other, BPFInsn):
			return NotImplemented
		a = ct.string_at(ct.addressof(self), ct.sizeof(self))
		b = ct.string_at(ct.addressof(other), ct.sizeof(other))
		return a == b
		
	def __hash__(self):
		return hash(ct.string_at(ct.addressof(self), ct.sizeof(self)))
	
	def to_json_dict(self, compact: bool = False) -> dict:
		return {
			"code" if not compact else "c": self.code,
			"dst_reg" if not compact else "d": self.dst_reg,
			"src_reg" if not compact else "s": self.src_reg,
			"off" if not compact else "o": self.off,
			"imm" if not compact else "i": self.imm,
		}

class ProfileStats(ct.Structure):
	_pack_ = 1
	_fields_ = [
		("subprog_cnt", ct.c_uint32),
		("insn_processed", ct.c_uint32),
		("complexity_limit_insns", ct.c_uint32),
		("max_states_per_insn", ct.c_uint32),
		("total_states", ct.c_uint32),
		("peak_states", ct.c_uint32),
		("longest_mark_read_walk", ct.c_uint32),
	]

	def __str__(self) -> str:
		return (
			f"ProfileStats(subprog_cnt={self.subprog_cnt}, "
			f"insn_processed={self.insn_processed}, "
			f"complexity_limit_insns={self.complexity_limit_insns}, "
			f"max_states_per_insn={self.max_states_per_insn}, "
			f"total_states={self.total_states}, "
			f"peak_states={self.peak_states}, "
			f"longest_mark_read_walk={self.longest_mark_read_walk})"
		)

	@staticmethod
	def from_bytes(data: bytes):
		if len(data) != ct.sizeof(ProfileStats):
			raise ValueError(
				f"Invalid data size: expected {ct.sizeof(ProfileStats)}, got {len(data)}"
			)
		s = ProfileStats()
		ct.memmove(ct.addressof(s), data, ct.sizeof(ProfileStats))
		return s

	@staticmethod
	def size() -> int:
		return ct.sizeof(ProfileStats)

	def to_json_dict(self) -> dict:
		return {
			"subprog_cnt": int(self.subprog_cnt),
			"insn_processed": int(self.insn_processed),
			"complexity_limit_insns": int(self.complexity_limit_insns),
			"max_states_per_insn": int(self.max_states_per_insn),
			"total_states": int(self.total_states),
			"peak_states": int(self.peak_states),
			"longest_mark_read_walk": int(self.longest_mark_read_walk),
		}

class ProfilingResult:
	def __init__(self, program_name: str, program: list[BPFInsn], stats: ProfileStats, records: list[Record]):
		self.program_name = program_name
		self.program = program
		self.stats = stats
		self.records = records

		if len(self.records) >= BPF_PROFILE_MAX_RECORDS:
			print(f"Warning: records for {self.program_name!r} has reached the maximum record limit of {BPF_PROFILE_MAX_RECORDS}. Some records may have been truncated.")

	"""Returns the duration of the profiling in nanoseconds, or 0 if there are no records. This assumes that the first record is of type START and the last record is of type END"""
	def duration(self):
		if not self.records:
			return 0
		if self.records[0].get_record_type() != RecordType.START:
			raise ValueError(f"First record for {self.program_name!r} should be of type START")
		if self.records[-1].get_record_type() != RecordType.END:
			raise ValueError(f"Last record for {self.program_name!r} should be of type END")
		start_time = self.records[0].start_time
		end_time = self.records[-1].end_time
		return end_time - start_time

	def __str__(self):
		return f"ProfilingResult(program_name={self.program_name}, program=[{len(self.program)} insns], stats={self.stats}, records=[{len(self.records)} records])"
	
if __name__ == "__main__":
	print(f"Record.size() = {Record.size()}")
	print(f"BPFInsn.size() = {BPFInsn.size()}")
	print(f"ProfileStats.size() = {ProfileStats.size()}")