import ctypes as ct
from enum import Enum


class Event(ct.Structure):
	_fields_ = [
		("type", ct.c_int),  # event_type_t mapped to int
		("timestamp", ct.c_ulonglong),
		("file", ct.c_char * 64),
		("line", ct.c_int),
		("duration", ct.c_ulonglong),
		("func_name", ct.c_char * 32),
	]

	class EVENT_TYPE(Enum):
		VERIFIER_START = 0
		VERIFIER_END = 1
		BLOCK_TIMER_RESULT = 2
		FUNC_TIMER_RESULT = 3

	def get_event_type(self):
		return Event.EVENT_TYPE(self.type)

	def __str__(self):
		match self.get_event_type():
			case Event.EVENT_TYPE.VERIFIER_START | Event.EVENT_TYPE.VERIFIER_END:
				return (
					super().__str__()
					+ f" [type={self.get_event_type().name}, file={self.file.decode()}, line={self.line}, timestamp={self.timestamp}, func_name={self.func_name.decode()}]"
				)
			case Event.EVENT_TYPE.BLOCK_TIMER_RESULT:
				return (
					super().__str__()
					+ f" [type={self.get_event_type().name}, file={self.file.decode()}, line={self.line}, timestamp={self.timestamp}, duration={self.duration}]"
				)
			case Event.EVENT_TYPE.FUNC_TIMER_RESULT:
				return (
					super().__str__()
					+ f" [type={self.get_event_type().name}, file={self.file.decode()}, line={self.line}, timestamp={self.timestamp}, func_name={self.func_name.decode()}, duration={self.duration}]"
				)
			case _:
				raise ValueError(f"Unknown event type: {self.get_event_type()}")

	def cast_from_pointer(data):
		return ct.cast(data, ct.POINTER(Event)).contents

	def from_bytes(data):
		if len(data) != ct.sizeof(Event):
			raise ValueError(f"Invalid data size: expected {ct.sizeof(Event)}, got {len(data)}")
		event = Event()                       # create a new instance
		ct.memmove(ct.addressof(event), data, ct.sizeof(Event))  # copy raw bytes into it
		return event

	@staticmethod
	def size():
		return ct.sizeof(Event)
