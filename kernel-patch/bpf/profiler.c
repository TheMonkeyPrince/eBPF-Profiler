#include "profiler.h"
#include <linux/types.h>

noinline __used void bpf_profiler_block_timer_result(const char* file, const int start_line, u32 arg, const u64 start_time, const u64 end_time) {}
noinline __used void bpf_profiler_func_timer_result(const char* file, const int line, char* func_name, u32 arg, const u64 start_time, const u64 end_time) {}