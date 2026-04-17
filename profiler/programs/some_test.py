def some_test():
    from bcc import BPF
    # BPF program (in C)
    bpf_program = """
    #include <uapi/linux/ptrace.h>

    int trace_execve(struct pt_regs *ctx, const char __user *filename) {
        char comm[256];
        bpf_probe_read_user_str(comm, sizeof(comm), filename);
        bpf_trace_printk("execve: %s\\n", comm);
        return 0;
    }
    """

    # Load BPF program
    b = BPF(text=bpf_program)

    # Attach kprobe to sys_execve (kernel function)
    b.attach_kprobe(event="__x64_sys_execve", fn_name="trace_execve")



