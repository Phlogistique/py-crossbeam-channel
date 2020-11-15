import sys
import subprocess
import signal
import time

import pytest

TEST_PUT_SIGINT_CODE = """
from py_crossbeam_channel import Queue

q = Queue(1)
q.put(None)
q.put(None)
"""

TEST_GET_SIGINT_CODE = """
from py_crossbeam_channel import Queue

q = Queue()
q.get()
"""

@pytest.mark.parametrize("code", [TEST_PUT_SIGINT_CODE, TEST_GET_SIGINT_CODE])
def test_queue_sigint(code):
    process = subprocess.Popen([sys.executable, "-c", TEST_PUT_SIGINT_CODE])
    time.sleep(1)
    process.send_signal(signal.SIGINT)
    process.wait(timeout=1)
