#include <uapi/linux/ptrace.h>
#include <linux/sched.h>
#include <linux/string.h>

typedef enum {
    VERIFIER_START,
    VERIFIER_END,
    FUNC_START,
    FUNC_END,
    TRACE_POINT,
} event_type_t;

struct event {
    event_type_t type;
    u64 timestamp;
    char file[64];
    int line;
    
    union {
        char func_name[64];
        int insn_idx;
    };
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
    struct event e = INIT_EVENT(VERIFIER_START, bpf_ktime_get_ns(), __FILE__, __LINE__);
    strcpy(e.func_name, "verifier_start");
    events.perf_submit(ctx, &e, sizeof(e));
    return 0;
}

int verifier_end(struct pt_regs *ctx) {
    struct event e = INIT_EVENT(VERIFIER_END, bpf_ktime_get_ns(), __FILE__, __LINE__);
    strcpy(e.func_name, "verifier_end");
    events.perf_submit(ctx, &e, sizeof(e));
    return 0;
}

int func_start(struct pt_regs *ctx, const u64 timestamp, const char* file, const int line, const char* func_name) {
    struct event e = INIT_EVENT(FUNC_START, timestamp, file, line);
    bpf_probe_read_kernel_str(e.func_name, sizeof(e.func_name), func_name);
    events.perf_submit(ctx, &e, sizeof(e)); 
    return 0;
}

int func_end(struct pt_regs *ctx, const u64 timestamp, const char* file, const int line, const char* func_name) {
    struct event e = INIT_EVENT(FUNC_END, timestamp, file, line);
    bpf_probe_read_kernel_str(e.func_name, sizeof(e.func_name), func_name);
    events.perf_submit(ctx, &e, sizeof(e));
    return 0;
}

int trace_point(struct pt_regs *ctx, const u64 timestamp, const char* file, const int line, u32 insn_idx) {
    struct event e = INIT_EVENT(TRACE_POINT, timestamp, file, line);

    e.insn_idx = insn_idx;

    events.perf_submit(ctx, &e, sizeof(e));
    return 0;
}