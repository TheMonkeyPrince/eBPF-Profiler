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