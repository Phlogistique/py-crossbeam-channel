import threading
import pytest

def put_100_items(q):
    for i in range(100):
        q.put(i)

def get_100_items(q):
    for _ in range(100):
        q.get()

def put_nowait_100_items(q):
    for i in range(100):
        q.put_nowait(i)

def get_nowait_100_items(q):
    for _ in range(100):
        q.get_nowait()

def put_contention(queue_class):
    q = queue_class()
    ts = [threading.Thread(target=put_100_items, args=(q,)) for i in range(100)]
    for t in ts:
        t.start()

    for _ in range(100*100):
        q.get()

    for t in ts:
        t.join()

def get_contention(queue_class):
    q = queue_class()
    ts = [threading.Thread(target=get_100_items, args=(q,)) for i in range(100)]
    for t in ts:
        t.start()

    for i in range(100*100):
        q.put(i)

    for t in ts:
        t.join()

def put_and_get_contention(queue_class):
    q = queue_class()
    ts = [threading.Thread(target=put_100_items, args=(q,)) for i in range(100)]+[threading.Thread(target=get_100_items, args=(q,)) for i in range(100)] 
    for t in ts:
        t.start()

    for t in ts:
        t.join()

def put_nowait_contention(queue_class):
    q = queue_class()
    ts = [threading.Thread(target=put_nowait_100_items, args=(q,)) for i in range(100)]
    for t in ts:
        t.start()

    for t in ts:
        t.join()

    for _ in range(100*100):
        q.get()

def get_nowait_contention(queue_class):
    q = queue_class()
    ts = [threading.Thread(target=get_nowait_100_items, args=(q,)) for i in range(100)]
    for i in range(100*100):
        q.put(i)

    for t in ts:
        t.start()

    for t in ts:
        t.join()

def put_and_get_nowait_contention(queue_class):
    q = queue_class()
    ts = [threading.Thread(target=put_nowait_100_items, args=(q,)) for i in range(100)]
    for t in ts:
        t.start()

    for t in ts:
        t.join()

    ts = [threading.Thread(target=get_nowait_100_items, args=(q,)) for i in range(100)] 
    for t in ts:
        t.start()

    for t in ts:
        t.join()

def put_backpressure_contention(queue_class):
    q = queue_class(10)
    ts = [threading.Thread(target=put_100_items, args=(q,)) for i in range(100)] 
    for t in ts:
        t.start()

    for _ in range(100*100):
        q.get()

    for t in ts:
        t.join()

def single_thread_perf(queue_class):
    q = queue_class()
    for i in range(100*100):
        q.put(i)
    for _ in range(100*100):
        q.get()


import py_crossbeam_channel
import queue

@pytest.mark.parametrize("queue_class", [py_crossbeam_channel.Queue, queue.Queue, queue.SimpleQueue], ids=["crossbeam", "queue.Queue", "queue.SimpleQueue"])
def test_single_thread_perf(queue_class, benchmark):
    benchmark(single_thread_perf, queue_class)
@pytest.mark.parametrize("queue_class", [py_crossbeam_channel.Queue, queue.Queue, queue.SimpleQueue], ids=["crossbeam", "queue.Queue", "queue.SimpleQueue"])
def test_put_contention(queue_class, benchmark):
    benchmark(put_contention, queue_class)
@pytest.mark.parametrize("queue_class", [py_crossbeam_channel.Queue, queue.Queue, queue.SimpleQueue], ids=["crossbeam", "queue.Queue", "queue.SimpleQueue"])
def test_get_contention(queue_class, benchmark):
    benchmark(get_contention, queue_class)
@pytest.mark.parametrize("queue_class", [py_crossbeam_channel.Queue, queue.Queue, queue.SimpleQueue], ids=["crossbeam", "queue.Queue", "queue.SimpleQueue"])
def test_put_and_get_contention(queue_class, benchmark):
    benchmark(put_and_get_contention, queue_class)
@pytest.mark.parametrize("queue_class", [py_crossbeam_channel.Queue, queue.Queue], ids=["crossbeam", "queue.Queue"])
def test_put_backpressure_contention(queue_class, benchmark):
    benchmark(put_backpressure_contention, queue_class)
@pytest.mark.parametrize("queue_class", [py_crossbeam_channel.Queue, queue.Queue, queue.SimpleQueue], ids=["crossbeam", "queue.Queue", "queue.SimpleQueue"])
def test_put_nowait_contention(queue_class, benchmark):
    benchmark(put_nowait_contention, queue_class)
@pytest.mark.parametrize("queue_class", [py_crossbeam_channel.Queue, queue.Queue, queue.SimpleQueue], ids=["crossbeam", "queue.Queue", "queue.SimpleQueue"])
def test_get_nowait_contention(queue_class, benchmark):
    benchmark(get_nowait_contention, queue_class)
@pytest.mark.parametrize("queue_class", [py_crossbeam_channel.Queue, queue.Queue, queue.SimpleQueue], ids=["crossbeam", "queue.Queue", "queue.SimpleQueue"])
def test_put_and_get_nowait_contention(queue_class, benchmark):
    benchmark(put_and_get_nowait_contention, queue_class)
