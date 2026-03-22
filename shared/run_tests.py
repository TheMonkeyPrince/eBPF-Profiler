import threading

from tests.strlen_count import strlen_count_test


def run_tests():
	threading.Thread(target=strlen_count_test).start()