import subprocess

from dataclasses import dataclass
from abc import ABC, abstractmethod

from profiler.selftest import SelftestInfo

@dataclass
class BPFProgramInfo(ABC):
	name: str = None
	description: str = None

	@abstractmethod
	def launch(self) -> subprocess.Popen[str]:
		pass

	@abstractmethod
	def to_analysis_file_name(self) -> str:
		pass

	@staticmethod
	@abstractmethod
	def from_analysis_file_name(file_name: str) -> 'BPFProgramInfo':
		pass

	@staticmethod
	def from_string(full_name: str) -> 'BPFProgramInfo':
		if full_name.startswith("selftest_"):
			return SelftestInfo.from_string(full_name)
		else:
			raise ValueError(f"Unknown program type for name: {full_name}")

	def __str__(self):
		return f"{self.name}: {self.description}"
