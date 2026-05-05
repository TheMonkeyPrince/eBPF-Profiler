#ifndef BPF_PROFILER_H
#define BPF_PROFILER_H
#include <linux/types.h>

#define BPF_PROFILE_NO_ARG ((u32)-1)
#define BPF_PROFILER_MAX_EVENT_RESULTS 4096

enum bpf_profiler_event_type {
    BPF_PROFILER_BLOCK_TIMER_RESULT = 0,
    BPF_PROFILER_FUNC_TIMER_RESULT = 1,
};

struct bpf_profiler_event_result {
    enum bpf_profiler_event_type type;
    const char *file;
    int line;
    const char *func_name;
    u32 arg;
    u64 start_time;
    u64 end_time;
};

#define BPF_PROFILE_BLOCK_END() \
    do { \
        u64 __bpf_timer_end = ktime_get_ns(); \
        bpf_profiler_add_event_result(BPF_PROFILER_BLOCK_TIMER_RESULT, __FILE__, __bpf_timer_line, NULL, __bpf_timer_arg, __bpf_timer_start, __bpf_timer_end); \
    } while (0)

#define BPF_PROFILE_BLOCK_ARG(arg, code_block)                                                        \
    do {                                                                                              \
        int __bpf_timer_line = __LINE__;                                                        \
        u32 __bpf_timer_arg = arg;                                                                    \
        u64 __bpf_timer_start = ktime_get_ns();                                                       \
        do { code_block } while (0);                                                                  \
        BPF_PROFILE_BLOCK_END();                                                                      \
    } while (0)

#define BPF_PROFILE_BLOCK(code_block)                     \
    BPF_PROFILE_BLOCK_ARG(BPF_PROFILE_NO_ARG, code_block)


#define BPF_PROFILE_CALL_ARG(arg, func, ...)                                                     \
({                                                                                                      \
    u64 __bpf_timer_start = ktime_get_ns();                                                             \
    __auto_type __ret_val = func(__VA_ARGS__);                                                          \
    u64 __bpf_timer_end = ktime_get_ns();                                                               \
    bpf_profiler_add_event_result(BPF_PROFILER_FUNC_TIMER_RESULT, __FILE__, __LINE__, #func, arg, __bpf_timer_start, __bpf_timer_end); \
    __ret_val;                                                                                          \
})

#define BPF_PROFILE_CALL(func, ...) \
    BPF_PROFILE_CALL_ARG(BPF_PROFILE_NO_ARG, func, __VA_ARGS__)

#define BPF_PROFILE_CALL_VOID_ARG(arg, func, ...)                              \
do {                                                                                  \
    u64 __bpf_timer_start = ktime_get_ns();                                           \
    func(__VA_ARGS__);                                                                \
    u64 __bpf_timer_end = ktime_get_ns();                                             \
    bpf_profiler_add_event_result(BPF_PROFILER_FUNC_TIMER_RESULT, __FILE__, __LINE__, #func, arg, \
                                  __bpf_timer_start, __bpf_timer_end);                \
} while (0)

#define BPF_PROFILE_CALL_VOID(func, ...) \
    BPF_PROFILE_CALL_VOID_ARG(BPF_PROFILE_NO_ARG, func, __VA_ARGS__)

void bpf_profiler_add_event_result(enum bpf_profiler_event_type type, const char *file,
                                   int line, const char *func_name, u32 arg,
                                   u64 start_time, u64 end_time);
void bpf_profiler_push_event_results(const struct bpf_profiler_event_result *results,
                                     u32 count);
const struct bpf_profiler_event_result *bpf_profiler_get_event_results(void);
u32 bpf_profiler_get_event_results_count(void);
void bpf_profiler_reset_event_results(void);

#endif