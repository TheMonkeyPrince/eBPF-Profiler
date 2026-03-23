import threading

from tests.some_test import some_test


def run_tests():
	threading.Thread(target=some_test).start()