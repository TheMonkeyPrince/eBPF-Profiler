from profiler import load_profiler, listen_for_events
from run_tests import run_tests

if __name__ == "__main__":
    
    print("Loading BPF profiler...")
    profiler_module = load_profiler()
    
    # print("Running tests...")
    # run_tests()

    print("Starting event listener...")
    listen_for_events(profiler_module)