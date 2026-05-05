#include "profiler.h"
#include <linux/spinlock.h>
#include <linux/types.h>

static DEFINE_SPINLOCK(bpf_profiler_event_results_lock);
static struct bpf_profiler_event_result
    bpf_profiler_event_results[BPF_PROFILER_MAX_EVENT_RESULTS];
static u32 bpf_profiler_event_results_count;

noinline __used void bpf_profiler_add_event_result(
    enum bpf_profiler_event_type type, const char *file, int line,
    const char *func_name, u32 arg, u64 start_time, u64 end_time)
{
    unsigned long flags;
    u32 idx;

    spin_lock_irqsave(&bpf_profiler_event_results_lock, flags);
    idx = bpf_profiler_event_results_count;
    if (idx < BPF_PROFILER_MAX_EVENT_RESULTS) {
        bpf_profiler_event_results[idx].type = type;
        bpf_profiler_event_results[idx].file = file;
        bpf_profiler_event_results[idx].line = line;
        bpf_profiler_event_results[idx].func_name = func_name;
        bpf_profiler_event_results[idx].arg = arg;
        bpf_profiler_event_results[idx].start_time = start_time;
        bpf_profiler_event_results[idx].end_time = end_time;
        bpf_profiler_event_results_count = idx + 1;
    }
    spin_unlock_irqrestore(&bpf_profiler_event_results_lock, flags);
}

noinline __used void bpf_profiler_push_event_results(
    const struct bpf_profiler_event_result *results, u32 count)
{
}

const struct bpf_profiler_event_result *bpf_profiler_get_event_results(void)
{
    return bpf_profiler_event_results;
}

u32 bpf_profiler_get_event_results_count(void)
{
    return bpf_profiler_event_results_count;
}

void bpf_profiler_reset_event_results(void)
{
    unsigned long flags;

    spin_lock_irqsave(&bpf_profiler_event_results_lock, flags);
    bpf_profiler_event_results_count = 0;
    spin_unlock_irqrestore(&bpf_profiler_event_results_lock, flags);
}