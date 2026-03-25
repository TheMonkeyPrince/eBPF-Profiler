#include <linux/sched.h>
#include <linux/string.h>
#include <uapi/linux/ptrace.h>

typedef enum {
    VERIFIER_START,
    VERIFIER_END,
    BLOCK_TIMER_RESULT,
    FUNC_TIMER_RESULT,
} event_type_t;

struct event {
    event_type_t type;
    u64 timestamp;
    char file[64];
    int line;
    u64 duration;
    char func_name[32];    
};

#define INIT_EVENT(_type, _timestamp, _file, _line) ({            \
    struct event _e = {0};                                        \
    _e.type = (_type);                                            \
    _e.timestamp = (_timestamp);                                  \
    bpf_probe_read_kernel_str(_e.file, sizeof(_e.file), (_file)); \
    _e.line = (_line);                                            \
    _e;                                                           \
})

// Perf output map
BPF_PERF_OUTPUT(events);

int verifier_start(struct pt_regs *ctx) {
    struct event e = INIT_EVENT(VERIFIER_START, bpf_ktime_get_ns(), NULL, 0);
    strcpy(e.func_name, "verifier_start");
    events.perf_submit(ctx, &e, sizeof(e));
    return 0;
}

int verifier_end(struct pt_regs *ctx) {
    struct event e = INIT_EVENT(VERIFIER_END, bpf_ktime_get_ns(), NULL, 0);
    strcpy(e.func_name, "verifier_end");
    events.perf_submit(ctx, &e, sizeof(e));
    return 0;
}

int block_timer_result(struct pt_regs *ctx, const char* file, const int start_line, const u64 duration) {
    struct event e = INIT_EVENT(BLOCK_TIMER_RESULT, bpf_ktime_get_ns(), file, start_line);
    e.duration = duration;
    events.perf_submit(ctx, &e, sizeof(e));
    return 0;
}

int func_timer_result(struct pt_regs *ctx, const char* file, const int line, const u64 duration, const char* func_name) {
    struct event e = INIT_EVENT(FUNC_TIMER_RESULT, bpf_ktime_get_ns(), file, line);
    e.duration = duration;
    bpf_probe_read_kernel_str(e.func_name, sizeof(e.func_name), func_name);
    events.perf_submit(ctx, &e, sizeof(e));
    return 0;
}