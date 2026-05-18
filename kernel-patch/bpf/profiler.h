#ifndef BPF_PROFILER_H
#define BPF_PROFILER_H
#include <linux/types.h>
#include <linux/bpf.h>
#include <linux/bpf_verifier.h>

#define BPF_PROFILE_NO_ARG ((u32)-1)
#define BPF_PROFILE_MAX_RECORDS 819200

#define BPF_PROFILE_VERIFIER_FILE_ID 0
#define BPF_PROFILE_LIVENESS_FILE_ID 1
#define BPF_PROFILE_STATES_FILE_ID 2

typedef unsigned char bpf_profile_record_type_t;
enum {
    START,
    END,
    BLOCK,
    CALL,
};

typedef struct __attribute__((packed)) {
    bpf_profile_record_type_t type;
    unsigned char file_id;
    int line;
    u32 arg;
    u64 start_time;
    u64 end_time;
} bpf_profile_record_t;

typedef struct __attribute__((packed)) {
    u32 count;
    bpf_profile_record_t records[BPF_PROFILE_MAX_RECORDS];
} bpf_profile_record_list_t;

/* Mirrors print_verification_stats(): */
typedef struct __attribute__((packed)) {
    u32 subprog_cnt;
    u32 insn_processed;
    u32 complexity_limit_insns;
    u32 max_states_per_insn;
    u32 total_states;
    u32 peak_states;
    u32 longest_mark_read_walk;
} bpf_verification_profile_stats_t;

#define BPF_PROFILE_BLOCK_END(file_id) \
    do { \
        u64 __bpf_timer_end = ktime_get_ns(); \
        bpf_profiler_add_record(BLOCK, file_id, __bpf_timer_line, __bpf_timer_arg, __bpf_timer_start, __bpf_timer_end); \
    } while (0)

#define BPF_PROFILE_BLOCK_ARG(file_id, arg, code_block)                                                        \
    do {                                                                                              \
        int __bpf_timer_line = __LINE__;                                                              \
        u32 __bpf_timer_arg = arg;                                                                    \
        u64 __bpf_timer_start = ktime_get_ns();                                                       \
        do { code_block } while (0);                                                                  \
        BPF_PROFILE_BLOCK_END(file_id);                                                                      \
    } while (0)

#define BPF_PROFILE_BLOCK(file_id, code_block)                     \
    BPF_PROFILE_BLOCK_ARG(file_id, BPF_PROFILE_NO_ARG, code_block)


#define BPF_PROFILE_CALL_ARG(file_id, arg, func, ...)                                                            \
({                                                                                                      \
    u64 __bpf_timer_start = ktime_get_ns();                                                             \
    __auto_type __ret_val = func(__VA_ARGS__);                                                          \
    u64 __bpf_timer_end = ktime_get_ns();                                                               \
    bpf_profiler_add_record(CALL, file_id, __LINE__, arg, __bpf_timer_start, __bpf_timer_end); \
    __ret_val;                                                                                          \
})

#define BPF_PROFILE_CALL(file_id, func, ...) \
    BPF_PROFILE_CALL_ARG(file_id, BPF_PROFILE_NO_ARG, func, __VA_ARGS__)

#define BPF_PROFILE_CALL_VOID_ARG(file_id, arg, func, ...)                                     \
do {                                                                                  \
    u64 __bpf_timer_start = ktime_get_ns();                                           \
    func(__VA_ARGS__);                                                                \
    u64 __bpf_timer_end = ktime_get_ns();                                             \
    bpf_profiler_add_record(CALL, file_id, __LINE__, arg,                     \
                                  __bpf_timer_start, __bpf_timer_end);                \
} while (0)

#define BPF_PROFILE_CALL_VOID(file_id, func, ...) \
    BPF_PROFILE_CALL_VOID_ARG(file_id, BPF_PROFILE_NO_ARG, func, __VA_ARGS__)

#define BPF_PROFILE_START() \
do {                                                                                                 \
    bpf_profiler_start(*prog);                                                                       \
    bpf_profiler_add_record(START, BPF_PROFILE_VERIFIER_FILE_ID, __LINE__, BPF_PROFILE_NO_ARG, ktime_get_ns(), 0); \
} while (0)   

#define BPF_PROFILE_END() \
do {                                                                                               \
    bpf_profiler_add_record(END, BPF_PROFILE_VERIFIER_FILE_ID, __LINE__, BPF_PROFILE_NO_ARG, 0, ktime_get_ns()); \
    bpf_profiler_end(env);                                                                         \
} while (0)

void bpf_profiler_add_record(bpf_profile_record_type_t type, unsigned char file_id, int line, u32 arg, u64 start_time, u64 end_time);

int bpf_profiler_start(struct bpf_prog *prog);
int bpf_profiler_end(struct bpf_verifier_env *env);
void bpf_profile_estimate_overhead(void);


#endif