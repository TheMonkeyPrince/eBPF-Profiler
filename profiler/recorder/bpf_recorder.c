#include <linux/sched.h>
#include <linux/string.h>
#include <uapi/linux/ptrace.h>

typedef enum {
    VERIFIER_START,
    VERIFIER_END,
    BLOCK_TIMER_RESULT,
    FUNC_TIMER_RESULT,
} event_type_t;

struct __attribute__((packed)) event {
    event_type_t type;
    u64 timestamp;
    char file[64];
    int start_line;
    char func_name[32]; 
    u32 arg;

    u64 start_time;
    u64 end_time;   
};

#define INIT_EVENT(_type, _timestamp, _file, _start_line) ({      \
    struct event _e = {0};                                        \
    _e.type = (_type);                                            \
    _e.timestamp = (_timestamp);                                  \
    bpf_probe_read_kernel_str(_e.file, sizeof(_e.file), (_file)); \
    _e.start_line = (_start_line);                                \
    _e;                                                           \
})

// Perf output map
BPF_PERF_OUTPUT(events);

int verifier_start(struct pt_regs *ctx) {
    struct event e = INIT_EVENT(VERIFIER_START, bpf_ktime_get_ns(), NULL, 0);
    __builtin_memcpy(e.file, "kernel/bpf/verifier.c", sizeof("kernel/bpf/verifier.c"));
    __builtin_memcpy(e.func_name, "bpf_check", sizeof("bpf_check"));
    events.perf_submit(ctx, &e, sizeof(e));
    return 0;
}

int verifier_end(struct pt_regs *ctx) {
    struct event e = INIT_EVENT(VERIFIER_END, bpf_ktime_get_ns(), NULL, 0);
    __builtin_memcpy(e.file, "kernel/bpf/verifier.c", sizeof("kernel/bpf/verifier.c"));
    __builtin_memcpy(e.func_name, "bpf_check", sizeof("bpf_check"));
    events.perf_submit(ctx, &e, sizeof(e));
    return 0;
}

int block_timer_result(struct pt_regs *ctx, const char* file, const int start_line, u32 arg, const u64 start_time, const u64 end_time) {
    struct event e = INIT_EVENT(BLOCK_TIMER_RESULT, bpf_ktime_get_ns(), file, start_line);
    e.arg = arg;
    e.start_time = start_time;
    e.end_time = end_time;
    events.perf_submit(ctx, &e, sizeof(e));
    return 0;
}

int func_timer_result(struct pt_regs *ctx, const char* file, const int line, char* func_name, u32 arg, const u64 start_time, const u64 end_time) {
    struct event e = INIT_EVENT(FUNC_TIMER_RESULT, bpf_ktime_get_ns(), file, line);
    e.arg = arg;
    e.start_time = start_time;
    e.end_time = end_time;
    bpf_probe_read_kernel_str(e.func_name, sizeof(e.func_name), func_name);
    events.perf_submit(ctx, &e, sizeof(e));
    return 0;
}