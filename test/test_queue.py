# Tests adapted from https://raw.githubusercontent.com/python/cpython/master/Lib/test/test_queue.py

# Some simple queue module tests, plus some failure conditions
# to ensure the Queue locks remain stable.
import itertools
import random
import threading
import time
import unittest
import weakref
from test.support import threading_helper


from queue import Empty, Full
from py_crossbeam_channel import Queue


class QueueTest(unittest.TestCase):

    def setUp(self):
        self.q = Queue()

    def feed(self, q, seq, rnd):
        while True:
            try:
                val = seq.pop()
            except IndexError:
                return
            q.put(val)
            if rnd.random() > 0.5:
                time.sleep(rnd.random() * 1e-3)

    def consume(self, q, results, sentinel):
        while True:
            val = q.get()
            if val == sentinel:
                return
            results.append(val)

    def consume_nonblock(self, q, results, sentinel):
        while True:
            while True:
                try:
                    val = q.get(block=False)
                except Empty:
                    time.sleep(1e-5)
                else:
                    break
            if val == sentinel:
                return
            results.append(val)

    def consume_timeout(self, q, results, sentinel):
        while True:
            while True:
                try:
                    val = q.get(timeout=1e-5)
                except Empty:
                    pass
                else:
                    break
            if val == sentinel:
                return
            results.append(val)

    def run_threads(self, n_feeders, n_consumers, q, inputs,
                    feed_func, consume_func):
        results = []
        sentinel = None
        seq = inputs + [sentinel] * n_consumers
        seq.reverse()
        rnd = random.Random(42)

        exceptions = []
        def log_exceptions(f):
            def wrapper(*args, **kwargs):
                try:
                    f(*args, **kwargs)
                except BaseException as e:
                    exceptions.append(e)
            return wrapper

        feeders = [threading.Thread(target=log_exceptions(feed_func),
                                    args=(q, seq, rnd))
                   for i in range(n_feeders)]
        consumers = [threading.Thread(target=log_exceptions(consume_func),
                                      args=(q, results, sentinel))
                     for i in range(n_consumers)]

        with threading_helper.start_threads(feeders + consumers):
            pass

        self.assertFalse(exceptions)
        self.assertTrue(q.empty())
        self.assertEqual(q.qsize(), 0)

        return results

    def test_basic(self):
        # Basic tests for get(), put() etc.
        q = self.q
        self.assertTrue(q.empty())
        self.assertEqual(q.qsize(), 0)
        q.put(1)
        self.assertFalse(q.empty())
        self.assertEqual(q.qsize(), 1)
        q.put(2)
        q.put_nowait(3)
        q.put(4)
        self.assertFalse(q.empty())
        self.assertEqual(q.qsize(), 4)

        self.assertEqual(q.get(), 1)
        self.assertEqual(q.qsize(), 3)

        self.assertEqual(q.get_nowait(), 2)
        self.assertEqual(q.qsize(), 2)

        self.assertEqual(q.get(block=False), 3)
        self.assertFalse(q.empty())
        self.assertEqual(q.qsize(), 1)

        self.assertEqual(q.get(timeout=0.1), 4)
        self.assertTrue(q.empty())
        self.assertEqual(q.qsize(), 0)

        with self.assertRaises(Empty):
            q.get(block=False)
        with self.assertRaises(Empty):
            q.get(timeout=1e-3)
        with self.assertRaises(Empty):
            q.get_nowait()
        self.assertTrue(q.empty())
        self.assertEqual(q.qsize(), 0)

    def test_negative_timeout_raises_exception(self):
        q = self.q
        q.put(1)
        with self.assertRaises(ValueError):
            q.get(timeout=-1)

    def test_order(self):
        # Test a pair of concurrent put() and get()
        q = self.q
        inputs = list(range(100))
        results = self.run_threads(1, 1, q, inputs, self.feed, self.consume)

        # One producer, one consumer => results appended in well-defined order
        self.assertEqual(results, inputs)

    def test_many_threads(self):
        # Test multiple concurrent put() and get()
        N = 50
        q = self.q
        inputs = list(range(10000))
        results = self.run_threads(N, N, q, inputs, self.feed, self.consume)

        # Multiple consumers without synchronization append the
        # results in random order
        self.assertEqual(sorted(results), inputs)

    def test_many_threads_nonblock(self):
        # Test multiple concurrent put() and get(block=False)
        N = 50
        q = self.q
        inputs = list(range(10000))
        results = self.run_threads(N, N, q, inputs,
                                   self.feed, self.consume_nonblock)

        self.assertEqual(sorted(results), inputs)

    def test_many_threads_timeout(self):
        # Test multiple concurrent put() and get(timeout=...)
        N = 50
        q = self.q
        inputs = list(range(1000))
        results = self.run_threads(N, N, q, inputs,
                                   self.feed, self.consume_timeout)

        self.assertEqual(sorted(results), inputs)

    def test_references(self):
        # The queue should lose references to each item as soon as
        # it leaves the queue.
        class C:
            pass

        N = 20
        q = self.q
        for i in range(N):
            q.put(C())
        for i in range(N):
            wr = weakref.ref(q.get())
            self.assertIsNone(wr())



    def test_reentrancy(self):
        # bpo-14976: put() may be called reentrantly in an asynchronous
        # callback.
        q = self.q
        gen = itertools.count()
        N = 10000
        results = []

        # This test exploits the fact that __del__ in a reference cycle
        # can be called any time the GC may run.

        class Circular(object):
            def __init__(self):
                self.circular = self

            def __del__(self):
                q.put(next(gen))

        while True:
            o = Circular()
            q.put(next(gen))
            del o
            results.append(q.get())
            if results[-1] >= N:
                break

        self.assertEqual(results, list(range(N + 1)))


if __name__ == "__main__":
    unittest.main()
