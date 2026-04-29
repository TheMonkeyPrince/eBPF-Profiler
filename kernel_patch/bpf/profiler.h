#ifndef BPF_PROFILER_H
#define BPF_PROFILER_H
#include <linux/types.h>

#define BPF_PROFILER_NO_ARG ((u32)-1)

#define STOP_BPF_TIMER() \
    do { \
        u64 __bpf_timer_end = ktime_get_ns(); \
        bpf_profiler_block_timer_result(__FILE__, __bpf_timer_start_line, __bpf_timer_arg, __bpf_timer_start, __bpf_timer_end); \
    } while (0)

#define RUN_BLOCK_WITH_BPF_TIMER_AND_ARG(arg, code_block)                                             \
    do {                                                                                              \
        int __bpf_timer_start_line = __LINE__;                                                        \
        u32 __bpf_timer_arg = arg;                                                                    \
        u64 __bpf_timer_start = ktime_get_ns();                                                       \
        do code_block while (0);                                                                      \
        STOP_BPF_TIMER();                                                                             \
    } while (0)

#define RUN_BLOCK_WITH_BPF_TIMER(code_block)                     \
    RUN_BLOCK_WITH_BPF_TIMER_AND_ARG(BPF_PROFILER_NO_ARG, code_block)

#define CALL_WITH_BPF_TIMER_AND_ARG(arg, func, ...)                                                     \
({                                                                                                      \
    u64 __bpf_timer_start = ktime_get_ns();                                                             \
    __auto_type __ret_val = func(__VA_ARGS__);                                                          \
    u64 __bpf_timer_end = ktime_get_ns();                                                               \
    bpf_profiler_func_timer_result(__FILE__, __LINE__, #func, arg, __bpf_timer_start, __bpf_timer_end); \
    __ret_val;                                                                                          \
})

#define CALL_WITH_BPF_TIMER(func, ...) \
    CALL_WITH_BPF_TIMER_AND_ARG(BPF_PROFILER_NO_ARG, func, __VA_ARGS__)

void bpf_profiler_block_timer_result(const char* file, const int start_line, u32 arg, const u64 start_time, const u64 end_time);
void bpf_profiler_func_timer_result(const char* file, const int line, char* func_name, u32 arg, const u64 start_time, const u64 end_time); 

#endif