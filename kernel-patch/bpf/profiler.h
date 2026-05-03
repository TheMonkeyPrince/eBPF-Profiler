#ifndef BPF_PROFILER_H
#define BPF_PROFILER_H
#include <linux/types.h>

#define BPF_PROFILE_NO_ARG ((u32)-1)

#define BPF_PROFILE_BLOCK_END() \
    do { \
        u64 __bpf_timer_end = ktime_get_ns(); \
        bpf_profiler_block_timer_result(__FILE__, __bpf_timer_start_line, __bpf_timer_arg, __bpf_timer_start, __bpf_timer_end); \
    } while (0)

#define BPF_PROFILE_BLOCK_ARG(arg, code_block)                                             \
    do {                                                                                              \
        int __bpf_timer_start_line = __LINE__;                                                        \
        u32 __bpf_timer_arg = arg;                                                                    \
        u64 __bpf_timer_start = ktime_get_ns();                                                       \
        do code_block while (0);                                                                      \
        STOP_BPF_TIMER();                                                                             \
    } while (0)

#define BPF_PROFILE_BLOCK(code_block)                     \
    BPF_PROFILE_BLOCK_ARG(BPF_PROFILE_NO_ARG, code_block)


#define BPF_PROFILE_CALL_ARG(arg, func, ...)                                                     \
({                                                                                                      \
    u64 __bpf_timer_start = ktime_get_ns();                                                             \
    __auto_type __ret_val = func(__VA_ARGS__);                                                          \
    u64 __bpf_timer_end = ktime_get_ns();                                                               \
    bpf_profiler_func_timer_result(__FILE__, __LINE__, #func, arg, __bpf_timer_start, __bpf_timer_end); \
    __ret_val;                                                                                          \
})

#define BPF_PROFILE_CALL(func, ...) \
    BPF_PROFILE_CALL_ARG(BPF_PROFILE_NO_ARG, func, __VA_ARGS__)

#define BPF_PROFILE_CALL_VOID_ARG(arg, func, ...)                              \
do {                                                                                  \
    u64 __bpf_timer_start = ktime_get_ns();                                           \
    func(__VA_ARGS__);                                                                \
    u64 __bpf_timer_end = ktime_get_ns();                                             \
    bpf_profiler_func_timer_result(__FILE__, __LINE__, #func, arg,                    \
                                   __bpf_timer_start, __bpf_timer_end);              \
} while (0)

#define BPF_PROFILE_CALL_VOID(func, ...) \
    BPF_PROFILE_CALL_VOID_ARG(BPF_PROFILE_NO_ARG, func, __VA_ARGS__)

void bpf_profiler_block_timer_result(const char* file, const int start_line, u32 arg, const u64 start_time, const u64 end_time);
void bpf_profiler_func_timer_result(const char* file, const int line, char* func_name, u32 arg, const u64 start_time, const u64 end_time); 

#endif