import ctypes as ct
from enum import Enum

u64 = ct.c_uint64
u32 = ct.c_uint32
NO_ARG = u32(-1).value

class RecordType(Enum):
	START = 0
	END = 1
	BLOCK = 2
	CALL = 3


class Record(ct.Structure):
	_pack_ = 1
	_fields_ = [
		("type", ct.c_int),
		("file", ct.c_char * 64),
		("line", ct.c_int),
		("func_name", ct.c_char * 32),
		("arg", u32),
		("start_time", u64),
		("end_time", u64),
	]

	def get_record_type(self):
		return RecordType(self.type)

	def has_arg(self):
		return self.get_record_type() in {RecordType.BLOCK, RecordType.CALL} and self.arg != NO_ARG

	def duration(self):
		if self.get_record_type() in {RecordType.BLOCK, RecordType.CALL}:
			return self.end_time - self.start_time
		return None

	def _decode_cstr(self, field: bytes):
		return field.split(b"\x00", 1)[0].decode(errors="replace")

	def __str__(self):
		return (
			f"[type={self.get_record_type().name}, file={self._decode_cstr(self.file)}, "
			f"line={self.line}, func_name={self._decode_cstr(self.func_name)}, "
			f"arg={self.arg}, start_time={self.start_time}, end_time={self.end_time}]"
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
	
class BPFInsn(ct.Structure):
	_pack_ = 1
	_fields_ = [
		("code", ct.c_uint8),
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
	
class ProfilingResult:
	def __init__(self, program_name: str, program: list[BPFInsn], trace: list[Record]):
		self.program_name = program_name
		self.program = program
		self.trace = trace

	def __str__(self):
		return f"ProfilingResult(program_name={self.program_name}, program=[{len(self.program)} insns], trace=[{len(self.trace)} records])"