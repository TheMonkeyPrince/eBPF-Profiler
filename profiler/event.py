import ctypes as ct
from enum import Enum

event_type_t = ct.c_int
u64 = ct.c_uint64
u32 = ct.c_uint32
NO_INSN_IDX = u32(-1).value


class Event(ct.Structure):
	_pack_ = 1
	_fields_ = [
		("type", event_type_t),
		("timestamp", u64),
		("file", ct.c_char * 64),
		("line", ct.c_int),
		("duration", u64),
		("insn_idx", u32),
		("func_name", ct.c_char * 32),
	]

	class EVENT_TYPE(Enum):
		VERIFIER_START = 0
		VERIFIER_END = 1
		BLOCK_TIMER_RESULT = 2
		FUNC_TIMER_RESULT = 3

	def get_event_type(self):
		return Event.EVENT_TYPE(self.type)

	def has_insn_idx(self):
		return (
			self.get_event_type()
			in {Event.EVENT_TYPE.BLOCK_TIMER_RESULT, Event.EVENT_TYPE.FUNC_TIMER_RESULT}
			and self.insn_idx != NO_INSN_IDX
		)

	def __str__(self):
		return f"[type={self.get_event_type().name}, file={self.file.decode()}, line={self.line}, timestamp={self.timestamp}, func_name={self.func_name.decode()}, duration={self.duration}, insn_idx={self.insn_idx}]"

	def from_bytes(data):
		if len(data) != ct.sizeof(Event):
			raise ValueError(
				f"Invalid data size: expected {ct.sizeof(Event)}, got {len(data)}"
			)
		event = Event()  # create a new instance
		ct.memmove(
			ct.addressof(event), data, ct.sizeof(Event)
		)  # copy raw bytes into it
		return event

	@staticmethod
	def size():
		return ct.sizeof(Event)
