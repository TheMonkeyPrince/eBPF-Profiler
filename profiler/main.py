from profiler import BPFProfiler

if __name__ == "__main__":
    profiler = BPFProfiler()
    trace = profiler.profile_program("dns_matching")

    profiler.analyse_trace("dns_matching", trace)
    # profiler.analyse_trace_from_file("dns_matching")