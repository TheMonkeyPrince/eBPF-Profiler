#ifndef BPF_PROFILER_H
#define BPF_PROFILER_H
#include <linux/types.h>

#define BPF_PROFILE_NO_ARG ((u32)-1)
#define BPF_PROFILE_MAX_RECORDS 4096

typedef enum {
    START,
    END,
    BLOCK,
    CALL,
} bpf_profile_record_type_t;

typedef struct __attribute__((packed)) {
    bpf_profile_record_type_t type;
    char file[64];
    int line;
    char func_name[32];
    u32 arg;
    u64 start_time;
    u64 end_time;
} bpf_profile_record_t;

typedef struct __attribute__((packed)) {
    u32 count;
    bpf_profile_record_t records[BPF_PROFILE_MAX_RECORDS];
} bpf_profile_record_list_t;

#define BPF_PROFILE_BLOCK_END() \
    do { \
        u64 __bpf_timer_end = ktime_get_ns(); \
        bpf_profiler_add_record(BLOCK, __FILE__, __bpf_timer_line, NULL, __bpf_timer_arg, __bpf_timer_start, __bpf_timer_end); \
    } while (0)

#define BPF_PROFILE_BLOCK_ARG(arg, code_block)                                                        \
    do {                                                                                              \
        int __bpf_timer_line = __LINE__;                                                              \
        u32 __bpf_timer_arg = arg;                                                                    \
        u64 __bpf_timer_start = ktime_get_ns();                                                       \
        do { code_block } while (0);                                                                  \
        BPF_PROFILE_BLOCK_END();                                                                      \
    } while (0)

#define BPF_PROFILE_BLOCK(code_block)                     \
    BPF_PROFILE_BLOCK_ARG(BPF_PROFILE_NO_ARG, code_block)


#define BPF_PROFILE_CALL_ARG(arg, func, ...)                                                            \
({                                                                                                      \
    u64 __bpf_timer_start = ktime_get_ns();                                                             \
    __auto_type __ret_val = func(__VA_ARGS__);                                                          \
    u64 __bpf_timer_end = ktime_get_ns();                                                               \
    bpf_profiler_add_record(CALL, __FILE__, __LINE__, #func, arg, __bpf_timer_start, __bpf_timer_end); \
    __ret_val;                                                                                          \
})

#define BPF_PROFILE_CALL(func, ...) \
    BPF_PROFILE_CALL_ARG(BPF_PROFILE_NO_ARG, func, __VA_ARGS__)

#define BPF_PROFILE_CALL_VOID_ARG(arg, func, ...)                                     \
do {                                                                                  \
    u64 __bpf_timer_start = ktime_get_ns();                                           \
    func(__VA_ARGS__);                                                                \
    u64 __bpf_timer_end = ktime_get_ns();                                             \
    bpf_profiler_add_record(CALL, __FILE__, __LINE__, #func, arg, \
                                  __bpf_timer_start, __bpf_timer_end);                \
} while (0)

#define BPF_PROFILE_CALL_VOID(func, ...) \
    BPF_PROFILE_CALL_VOID_ARG(BPF_PROFILE_NO_ARG, func, __VA_ARGS__)

#define BPF_PROFILE_START() \
    bpf_profiler_add_record(START, __FILE__, __LINE__, NULL, BPF_PROFILE_NO_ARG, ktime_get_ns(), 0)

#define BPF_PROFILE_END() \
do {                                                                                               \
    bpf_profiler_add_record(END, __FILE__, __LINE__, NULL, BPF_PROFILE_NO_ARG, 0, ktime_get_ns()); \
    bpf_profiler_push_records();                                                                    \
} while (0)

void bpf_profiler_add_record(bpf_profile_record_type_t type, const char *file,
                                   int line, const char *func_name, u32 arg,
                                   u64 start_time, u64 end_time);

void bpf_profiler_push_records(void);

// bpf_profile_records_t *bpf_profile_get_records(void);

void bpf_profiler_hook(const bpf_profile_record_t *record);

#endif