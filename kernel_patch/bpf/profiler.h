#ifndef BPF_PROFILER_H
#define BPF_PROFILER_H
#include <linux/types.h>

#define BPF_PROFILER_NO_INSN_IDX ((u32)-1)

#define RUN_BLOCK_WITH_BPF_TIMER_AND_INSN_IDX(insn_idx, code_block)                     \
    do {                                                         \
        u64 __bpf_timer_start = ktime_get_ns();                              \
        code_block                                               \
        u64 __bpf_timer_end = ktime_get_ns();                                \
        u64 duration = __bpf_timer_end - __bpf_timer_start;                              \
        bpf_profiler_block_timer_result(__FILE__, __LINE__, duration, insn_idx); \
    } while (0)

#define RUN_BLOCK_WITH_BPF_TIMER(code_block)                     \
    RUN_BLOCK_WITH_BPF_TIMER_AND_INSN_IDX(BPF_PROFILER_NO_INSN_IDX, code_block)

#define CALL_WITH_BPF_TIMER_AND_INSN_IDX(insn_idx, func, ...)                                     \
({                                                                         \
    u64 __bpf_timer_start = ktime_get_ns();                                          \
    __auto_type __ret_val = func(__VA_ARGS__);                             \
    u64 __bpf_timer_end = ktime_get_ns();                                            \
    u64 __duration = __bpf_timer_end - __bpf_timer_start;                                      \
    bpf_profiler_func_timer_result(__FILE__, __LINE__, __duration, insn_idx, #func); \
    __ret_val;                                                             \
})

#define CALL_WITH_BPF_TIMER(func, ...) \
    CALL_WITH_BPF_TIMER_AND_INSN_IDX(BPF_PROFILER_NO_INSN_IDX, func, __VA_ARGS__)

void bpf_profiler_block_timer_result(const char* file, const int start_line, const u64 duration, u32 insn_idx);
void bpf_profiler_func_timer_result(const char* file, const int line, const u64 duration, u32 insn_idx, const char* func_name);

#endif