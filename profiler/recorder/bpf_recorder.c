#include <linux/sched.h>
#include <linux/string.h>
#include <uapi/linux/ptrace.h>

#define BPF_PROFILER_MAX_EVENT_RESULTS 4096

typedef enum {
    VERIFIER_START,
    VERIFIER_END,
    BLOCK_TIMER_RESULT,
    FUNC_TIMER_RESULT,
} event_type_t;

typedef enum {
    PROFILER_BLOCK_TIMER_RESULT,
    PROFILER_FUNC_TIMER_RESULT,
} profiler_event_type_t;

struct profiler_event_result {
    int type;
    const char *file;
    int line;
    const char *func_name;
    u32 arg;
    u64 start_time;
    u64 end_time;
};

struct __attribute__((packed)) event {
    event_type_t type;
    u64 timestamp;
    char file[64];
    int line;
    char func_name[32]; 
    u32 arg;

    u64 start_time;
    u64 end_time;   
};

struct __attribute__((packed)) event_batch {
    u32 count;
    struct event events[BPF_PROFILER_MAX_EVENT_RESULTS];
};

#define INIT_EVENT(_type, _timestamp, _file, _line) ({      \
    struct event _e = {0};                                        \
    _e.type = (_type);                                            \
    _e.timestamp = (_timestamp);                                  \
    bpf_probe_read_kernel_str(_e.file, sizeof(_e.file), (_file)); \
    _e.line = (_line);                                \
    _e;                                                           \
})

// Perf output map
BPF_PERF_OUTPUT(events);
BPF_PERCPU_ARRAY(batch_buffer, struct event_batch, 1);

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

int push_event_results(struct pt_regs *ctx, const struct profiler_event_result *results, u32 count) {
    u32 i = 0;
    u32 batch_key = 0;
    struct profiler_event_result in = {0};
    struct event e = {0};
    struct event_batch *batch;

    batch = batch_buffer.lookup(&batch_key);
    if (!batch)
        return 0;

    if (count > BPF_PROFILER_MAX_EVENT_RESULTS)
        count = BPF_PROFILER_MAX_EVENT_RESULTS;

    for (i = 0; i < count; i++) {
        bpf_probe_read_kernel(&in, sizeof(in), &results[i]);

        switch ((profiler_event_type_t)in.type) {
        case PROFILER_BLOCK_TIMER_RESULT:
            e = INIT_EVENT(BLOCK_TIMER_RESULT, bpf_ktime_get_ns(), in.file, in.line);
            break;
        case PROFILER_FUNC_TIMER_RESULT:
            e = INIT_EVENT(FUNC_TIMER_RESULT, bpf_ktime_get_ns(), in.file, in.line);
            bpf_probe_read_kernel_str(e.func_name, sizeof(e.func_name), in.func_name);
            break;
        default:
            continue;
        }

        e.arg = in.arg;
        e.start_time = in.start_time;
        e.end_time = in.end_time;
        batch->events[i] = e;
    }

    batch->count = count;
    events.perf_submit(ctx, batch, sizeof(batch->count) + count * sizeof(struct event));
    return 0;
}