# import threading

# from programs.some_test import some_test
# from programs.dns_matching.dns_matching import run_dns_matching

# def launch_bpf_program(program_path) -> threading.Thread:
# 	# thread = threading.Thread(target=some_test)
# 	thread = threading.Thread(target=run_dns_matching)
# 	thread.start()
# 	return thread

import subprocess
import threading
from typing import Callable, Optional

from selftests import run_selftest


def launch_bpf_program(
    program_name: str,
    on_completed: Optional[Callable[[subprocess.Popen[str]], None]] = None
) -> subprocess.Popen[str]:
    
    if program_name.startswith("selftest_"):
        process = run_selftest(program_name)

        if on_completed:
            def _wait_and_callback():
                process.wait()
                on_completed(process)

            threading.Thread(target=_wait_and_callback, daemon=True).start()

        return process

    raise ValueError(f"Unknown program name: {program_name}")