#include "profiler.h"
#include <linux/types.h>

noinline __used void bpf_profiler_block_timer_result(const char* file, const int start_line, const u64 duration, u32 insn_idx) {}
noinline __used void bpf_profiler_func_timer_result(const char* file, const int line, const u64 duration, u32 insn_idx, const char* func_name) {}