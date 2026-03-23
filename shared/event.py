import ctypes as ct
from enum import Enum

class EventData(ct.Union):
	_fields_ = [
		("func_name", ct.c_char * 64),
		("insn_idx", ct.c_int),
	]

class Event(ct.Structure):
	_anonymous_ = ("data",)  # allows direct access to union fields
	_fields_ = [
		("type", ct.c_int),         # event_type_t mapped to int
		("timestamp", ct.c_ulonglong),
		("file", ct.c_char * 64),
		("line", ct.c_int),
		("data", EventData),        # union
	]

	class EVENT_TYPE(Enum):
		VERIFIER_START = 0
		VERIFIER_END = 1
		FUNC_START = 2
		FUNC_END = 3
		TRACE_POINT = 4

	def get_event_type(self):
		return Event.EVENT_TYPE(self.type)
	
	def __str__(self):
		return super().__str__() + f" [type={self.get_event_type().name}, file={self.file.decode()}, line={self.line}, timestamp={self.timestamp} {', func_name=' + self.func_name.decode() if self.get_event_type() in (Event.EVENT_TYPE.FUNC_START, Event.EVENT_TYPE.FUNC_END) else ''}{', insn_idx=' + str(self.insn_idx) if self.get_event_type() == Event.EVENT_TYPE.TRACE_POINT else ''}]"
	
	def from_data(data):
		return ct.cast(data, ct.POINTER(Event)).contents