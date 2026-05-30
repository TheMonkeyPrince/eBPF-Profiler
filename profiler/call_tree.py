from profiler_types import *

class CallTreeNode:
	def __init__(self, record: Record, parent: 'CallTreeNode'=None):
		self.record = record
		self.children: list[CallTreeNode] = []
		self.parent = parent

	def is_within(self, other: 'CallTreeNode') -> bool:
		return self.record.start_time >= other.record.start_time and self.record.end_time <= other.record.end_time
	
	def path(self):
		path: list[str] = []
		node = self
		while node is not None:
			path.append(f"{node.record.file_id}:{node.record.line}")
			node = node.parent
		return ",".join(reversed(path))
	
class CallTree:
	def __init__(self, records: list[Record]):
		self.roots: list[CallTreeNode] = []
		self.records = records

		stack = []
		for record in reversed(records):
			if record.get_record_type() not in {RecordType.BLOCK, RecordType.CALL}:
				raise ValueError(f"Unexpected record type {record.get_record_type().name} in call tree construction. Only BLOCK and CALL records are expected.")

			node = CallTreeNode(record)
			while stack and not node.is_within(stack[-1]):
				stack.pop()

			if stack:
				parent = stack[-1]
				parent.children.append(node)
				node.parent = parent
			else:
				self.roots.append(node)
			stack.append(node)

		self.roots.reverse()  # Reverse to maintain original order
		def reverse_children(node: CallTreeNode):
			node.children.reverse()
			for child in node.children:
				reverse_children(child)
		for root in self.roots:
			reverse_children(root)

	def print_node(self, node: CallTreeNode, indent=0):
		print(" " * indent + f"{node.record.file_id}:{node.record.line}")
		for child in node.children:
			self.print_node(child, indent + 2)

class RecordSite:
	def __init__(self, file_id: FileId, line: LineNumber, is_call: bool):
		self.file_id = file_id
		self.line = line
		self.is_call = is_call
		self.durations: dict[InsnIdx, list[int]] = {}
		self.children: list[RecordSite] = []

		self._inclusive_duration = -1
		self._exclusive_duration = -1
		self._children_duration = -1

	@property
	def inclusive_duration(self) -> int:
		if self._inclusive_duration >= 0:
			return self._inclusive_duration
		
		self._inclusive_duration = sum(sum(durations) for durations in self.durations.values())
		if self._inclusive_duration < 0:
			raise ValueError(f"RecordSite {self.file_id}:{self.line} has negative inclusive duration {self._inclusive_duration}. This should be impossible.")
		return self._inclusive_duration

	@property
	def exclusive_duration(self) -> int:
		if self._exclusive_duration >= 0:
			return self._exclusive_duration
		
		self._exclusive_duration = self.inclusive_duration - self.children_duration
		if self._exclusive_duration < 0:
			raise ValueError(f"RecordSite {self.file_id}:{self.line} has negative exclusive duration {self._exclusive_duration}. This should be impossible.")
		if self._exclusive_duration > self.inclusive_duration:
			raise ValueError(f"RecordSite {self.file_id}:{self.line} has exclusive duration {self._exclusive_duration} greater than inclusive duration {self.inclusive_duration}. This should be impossible.")
		return self._exclusive_duration
	
	@property
	def children_duration(self) -> int:
		if self._children_duration >= 0:
			return self._children_duration
		
		self._children_duration = sum(child.inclusive_duration for child in self.children)
		if self._children_duration < 0:
			raise ValueError(f"RecordSite {self.file_id}:{self.line} has negative children duration {self._children_duration}. This should be impossible.")
		return self._children_duration
	
	def __str__(self):
		return f"RecordSite(file_id={self.file_id}, line={self.line}, is_call={self.is_call}, inclusive_duration={self.inclusive_duration}, exclusive_duration={self.exclusive_duration}, children_duration={self.children_duration})"
	
	def serialize(self, resolve_site: callable, resolve_insn_name: callable, compact=False):
		filename, end_line_or_func_name = resolve_site(self.file_id, self.line, self.is_call)
		if compact:
			key = f"{self.file_id}:{self.line}:{end_line_or_func_name}"
		else:
			key = f"{filename}:{self.line}:{end_line_or_func_name}"

		if list(self.durations.keys())[0] == Record.NO_INSN_IDX:
			serialized = {
			"inclusive_duration": self.inclusive_duration,
			"exclusive_duration": self.exclusive_duration,
			"children_duration": self.children_duration,
			"children": [child.serialize(resolve_site=resolve_site, resolve_insn_name=resolve_insn_name, compact=compact) for child in self.children],
			"nb_visits": sum(len(durations) for durations in self.durations.values()),
			}
	
		else:
			nb_visits = sum(len(durations) for durations in self.durations.values())
			avg_time_per_visit = self.inclusive_duration / float(nb_visits)

			# save top 10 slowest instructions for this site
			def compute_insn_score(durations: list[int]) -> float:
				avg_duration = sum(durations) / float(len(durations))
				return avg_duration / avg_time_per_visit # this score represents how much slower this instruction is compared to the average time per visit for this site, so a score of 2 means this instruction is on average twice as slow as the average time per visit for this site
			
			s = sorted(self.durations.items(), key=lambda item: compute_insn_score(item[1]), reverse=True)[:10]
			slowest_insns: dict[InsnIdx, dict[str, int | float]] = {}
			for insn_idx, durations in s:
				slowest_insns[insn_idx] = {
					"count": len(durations),
					"score": compute_insn_score(durations),
				}

			s = sorted(self.durations.items(), key=lambda item: compute_insn_score(item[1]), reverse=True)[10:]
			if len(s) > 0:
				other_insns_count = sum(len(durations) for _, durations in s)
				slowest_insns["other"] = {
					"count": other_insns_count,
					"score": compute_insn_score([duration for _, durations in s for duration in durations]),
				}
			
			# save top 10 slowest instruction types for this site
			durations_per_insn_type: dict[str, list[int]] = {}
			for insn_idx, durations in self.durations.items():
				insn_name = resolve_insn_name(insn_idx)
				if insn_name not in durations_per_insn_type:
					durations_per_insn_type[insn_name] = []
				durations_per_insn_type[insn_name].extend(durations)

			avg: dict[str, float] = {insn_name: sum(durations) / float(len(durations)) for insn_name, durations in durations_per_insn_type.items()}
			nb_insn_types = len(durations_per_insn_type)
			avg_time_per_insn_type = sum(avg.values()) / float(len(avg))
			def compute_insn_type_score(durations: list[int]) -> float:
				avg_duration = sum(durations) / float(len(durations))
				return avg_duration / avg_time_per_insn_type # this score represents how much slower this instruction type is compared to the average time per instruction type for this site, so a score of 2 means this instruction type is on average twice as slow as the average time per instruction typefor this site

			s = sorted(durations_per_insn_type.items(), key=lambda item: compute_insn_type_score(item[1]), reverse=True)[:10]
			slowest_insn_types: dict[str, dict[str, int | float]] = {}
			for insn_name, durations in s:
				slowest_insn_types[insn_name] = {
					"count": len(durations),
					"score": compute_insn_type_score(durations),
				}

			s = sorted(durations_per_insn_type.items(), key=lambda item: compute_insn_type_score(item[1]), reverse=True)[10:]
			if len(s) > 0:
				other_insn_types_count = sum(len(durations) for _, durations in s)
				slowest_insn_types["other"] = {
					"count": other_insn_types_count,
					"score": compute_insn_type_score([duration for _, durations in s for duration in durations]),
				}

			serialized = {
				"inclusive_duration": self.inclusive_duration,
				"exclusive_duration": self.exclusive_duration,
				"children_duration": self.children_duration,
				"children": [child.serialize(resolve_site=resolve_site, resolve_insn_name=resolve_insn_name, compact=compact) for child in self.children],
				"nb_visits": nb_visits,
				"nb_insn_types": nb_insn_types,
				"slowest_insns": slowest_insns,
				"slowest_insn_types": slowest_insn_types,
			}
			
		if compact:
			return (key, serialized.values())
		return (key, serialized)

class SiteTree:
	def __init__(self, call_tree: CallTree):
		self.roots: list[RecordSite] = []
		
		path_to_site: dict[list[str], RecordSite] = {}
		def process_call_nodes(nodes: list[CallTreeNode]):
			for node in nodes:
				record = node.record
				path_key = node.path()
				if path_key not in path_to_site:
					path_to_site[path_key] = RecordSite(record.file_id, record.line, record.get_record_type() == RecordType.CALL)
				site = path_to_site[path_key]

				if record.insn_idx not in site.durations:
					site.durations[record.insn_idx] = []
				site.durations[record.insn_idx].append(record.duration())

				process_call_nodes(node.children)

		process_call_nodes(call_tree.roots)

		# Build tree structure
		for path_key, site in path_to_site.items():
			path_parts = path_key.split(",")
			if len(path_parts) == 1:
				self.roots.append(site)
			else:
				parent_path_key = ",".join(path_parts[:-1])
				parent_site = path_to_site[parent_path_key]
				parent_site.children.append(site)

	def number_of_sites(self) -> int:
		def count_sites(site: RecordSite) -> int:
			count = 1
			for child in site.children:
				count += count_sites(child)
			return count
		
		count = 0
		for root in self.roots:
			count += count_sites(root)
		return count

	def serialize(self, resolve_site: callable, resolve_insn_name: callable, compact=False):
		return dict([site.serialize(resolve_site=resolve_site, resolve_insn_name=resolve_insn_name, compact=compact) for site in self.roots])

	def print_node(self, node: RecordSite, indent=0):
		print(" " * indent + str(node))
		for child in node.children:
			self.print_node(child, indent + 2)

	def print_tree(self):
		for root in self.roots:
			self.print_node(root, 0)

if __name__ == "__main__":
	records = [
		Record(line=ord('D'), start_time=630, end_time=670, type=RecordType.CALL.value),
		Record(line=ord('C'), start_time=660, end_time=680, type=RecordType.CALL.value),
		Record(line=ord('B'), start_time=610, end_time=690, type=RecordType.CALL.value),
		Record(line=ord('A'), start_time=600, end_time=700, type=RecordType.CALL.value),

		Record(line=ord('C'), start_time=820, end_time=870, type=RecordType.CALL.value),
		Record(line=ord('B'), start_time=810, end_time=890, type=RecordType.CALL.value),
		Record(line=ord('A'), start_time=800, end_time=900, type=RecordType.CALL.value),

		Record(line=ord('C'), start_time=950, end_time=960, type=RecordType.CALL.value),
		Record(line=ord('Z'), start_time=901, end_time=1000, type=RecordType.CALL.value),
	]

	site_tree = SiteTree(CallTree(records))
	site_tree.print_tree()
