#ifndef BPF_PROFILER_H
#define BPF_PROFILER_H
#include <linux/types.h>
#include <linux/bpf.h>
#include <linux/bpf_verifier.h>

#define BPF_PROFILE_NO_INSN ((u32)-1)
#define BPF_PROFILE_MAX_RECORDS 805306368 // 24GB of records, should be enough for profiling the verifier

#define BPF_PROFILE_VERIFIER_FILE_ID 0
#define BPF_PROFILE_LIVENESS_FILE_ID 1
#define BPF_PROFILE_STATES_FILE_ID 2

typedef enum {
    START,
    END,
    BLOCK,
    CALL,
} bpf_profile_record_type_t;

// sizeof(bpf_profile_record_t) = 32
typedef struct {
    u64 start_time;
    u64 end_time;
    u32 line;
    u32 insn_idx;
    bpf_profile_record_type_t type;
    u8 file_id;
    u8 _pad[3];
} bpf_profile_record_t;
_Static_assert(sizeof(bpf_profile_record_t) == 32, "bad size");

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
        bpf_profiler_add_record(BLOCK, file_id, __bpf_timer_line, __bpf_timer_insn_idx, __bpf_timer_start, __bpf_timer_end); \
    } while (0)

#define BPF_PROFILE_BLOCK_INSN(file_id, insn_idx, code_block)                                                        \
    do {                                                                                              \
        int __bpf_timer_line = __LINE__;                                                              \
        u32 __bpf_timer_insn_idx = insn_idx;                                                                    \
        u64 __bpf_timer_start = ktime_get_ns();                                                       \
        do { code_block } while (0);                                                                  \
        BPF_PROFILE_BLOCK_END(file_id);                                                                      \
    } while (0)

#define BPF_PROFILE_BLOCK(file_id, code_block)                     \
    BPF_PROFILE_BLOCK_INSN(file_id, BPF_PROFILE_NO_INSN, code_block)


#define BPF_PROFILE_CALL_INSN(file_id, insn_idx, func, ...)                                                            \
({                                                                                                      \
    u64 __bpf_timer_start = ktime_get_ns();                                                             \
    __auto_type __ret_val = func(__VA_ARGS__);                                                          \
    u64 __bpf_timer_end = ktime_get_ns();                                                               \
    bpf_profiler_add_record(CALL, file_id, __LINE__, insn_idx, __bpf_timer_start, __bpf_timer_end); \
    __ret_val;                                                                                          \
})

#define BPF_PROFILE_CALL(file_id, func, ...) \
    BPF_PROFILE_CALL_INSN(file_id, BPF_PROFILE_NO_INSN, func, __VA_ARGS__)

#define BPF_PROFILE_CALL_VOID_INSN(file_id, insn_idx, func, ...)                                     \
do {                                                                                  \
    u64 __bpf_timer_start = ktime_get_ns();                                           \
    func(__VA_ARGS__);                                                                \
    u64 __bpf_timer_end = ktime_get_ns();                                             \
    bpf_profiler_add_record(CALL, file_id, __LINE__, insn_idx,                     \
                                  __bpf_timer_start, __bpf_timer_end);                \
} while (0)

#define BPF_PROFILE_CALL_VOID(file_id, func, ...) \
    BPF_PROFILE_CALL_VOID_INSN(file_id, BPF_PROFILE_NO_INSN, func, __VA_ARGS__)

#define BPF_PROFILE_START() \
do {                                                                                                 \
    bpf_profiler_start(*prog);                                                                       \
    bpf_profiler_add_record(START, BPF_PROFILE_VERIFIER_FILE_ID, __LINE__, BPF_PROFILE_NO_INSN, ktime_get_ns(), 0); \
} while (0)   

#define BPF_PROFILE_END() \
do {                                                                                               \
    bpf_profiler_add_record(END, BPF_PROFILE_VERIFIER_FILE_ID, __LINE__, BPF_PROFILE_NO_INSN, 0, ktime_get_ns()); \
    bpf_profiler_end(env);                                                                         \
} while (0)

void bpf_profiler_add_record(bpf_profile_record_type_t type, unsigned char file_id, int line, u32 insn_idx, u64 start_time, u64 end_time);

int bpf_profiler_start(struct bpf_prog *prog);
int bpf_profiler_end(struct bpf_verifier_env *env);


#endif