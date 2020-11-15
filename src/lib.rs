use pyo3::prelude::*;

use core::time::Duration;
use std::cmp::min;
use std::time::Instant;

use crossbeam::channel::bounded;
use crossbeam::channel::unbounded;
use crossbeam::channel::Receiver;
use crossbeam::channel::RecvTimeoutError;
use crossbeam::channel::SendTimeoutError;
use crossbeam::channel::Sender;
use crossbeam::channel::TryRecvError;
use crossbeam::channel::TrySendError;
use pyo3::exceptions::PyValueError;
use pyo3::once_cell::GILOnceCell;
use pyo3::types::PyType;

#[pyclass]
struct Queue {
        sender: Sender<PyObject>,
        receiver: Receiver<PyObject>,
}

static EMPTY: GILOnceCell<PyResult<Py<PyType>>> = GILOnceCell::new();
static FULL: GILOnceCell<PyResult<Py<PyType>>> = GILOnceCell::new();
const TIME_BETWEEN_CHECKING_SIGNALS: Duration = Duration::from_millis(200);

pub fn import_exc(py: Python, name: &str) -> PyResult<Py<PyType>> {
        PyModule::import(py, "queue")?
                .get(name)?
                .extract::<Py<PyType>>()
                .map(|x| x.into())
}

pub fn get_exc_from_gil_once_cell<'a>(
        py: Python<'a>,
        name: &'static str,
        cell: &'static GILOnceCell<PyResult<Py<PyType>>>,
) -> PyResult<&'a PyType> {
        Ok(cell.get_or_init(py, || import_exc(py, name))
                .as_ref()
                .map_err(|x| x.clone_ref(py))?
                .extract(py)?)
}

pub fn empty(py: Python) -> PyResult<&PyType> {
        get_exc_from_gil_once_cell(py, "Empty", &EMPTY)
}

pub fn full(py: Python) -> PyResult<&PyType> {
        get_exc_from_gil_once_cell(py, "Full", &FULL)
}

impl Queue {
        fn send_timeout(
                &self,
                py: Python,
                item: PyObject,
                timeout: Option<Duration>,
        ) -> PyResult<()> {
                let mut item = item;

                // first try non-blocking in order to prevent paying the cost of releasing and re-acquiring the GIL
                let result = self.sender.try_send(item);

                match result {
                        Ok(_) => return Ok(()),
                        Err(TrySendError::Disconnected(_)) => panic!("BUG"),
                        Err(TrySendError::Full(item_)) => item = item_,
                }

                let end = timeout.map(|timeout| Instant::now() + timeout);
                loop {
                        let next_check_time = Instant::now() + TIME_BETWEEN_CHECKING_SIGNALS;
                        let next_deadline =
                                end.map_or(next_check_time, |end| min(next_check_time, end));

                        let result =
                                py.allow_threads(|| self.sender.send_deadline(item, next_deadline));

                        match result {
                                Ok(_) => return Ok(()),
                                Err(SendTimeoutError::Disconnected(_)) => panic!("BUG"),
                                Err(SendTimeoutError::Timeout(item_)) => {
                                        let timed_out =
                                                end.map_or(false, |end| Instant::now() > end);
                                        if timed_out {
                                                return Err(PyErr::from_type(full(py)?, "Timeout"));
                                        } else {
                                                item = item_
                                        }
                                }
                        };
                        py.check_signals()?;
                }
        }

        fn recv_timeout(&self, py: Python, timeout: Option<Duration>) -> PyResult<PyObject> {
                // first try non-blocking in order to prevent paying the cost of releasing and re-acquiring the GIL
                let result = self.receiver.try_recv();

                match result {
                        Ok(item) => return Ok(item),
                        Err(TryRecvError::Disconnected) => panic!("BUG"),
                        Err(TryRecvError::Empty) => (),
                }

                let end = timeout.map(|timeout| Instant::now() + timeout);
                loop {
                        let next_check_time = Instant::now() + TIME_BETWEEN_CHECKING_SIGNALS;
                        let next_deadline =
                                end.map_or(next_check_time, |end| min(next_check_time, end));

                        let result =
                                py.allow_threads(|| self.receiver.recv_deadline(next_deadline));

                        match result {
                                Ok(result) => return Ok(result),
                                Err(RecvTimeoutError::Disconnected) => panic!("BUG"),
                                Err(RecvTimeoutError::Timeout) => {
                                        let timed_out =
                                                end.map_or(false, |end| Instant::now() > end);
                                        if timed_out {
                                                return Err(PyErr::from_type(
                                                        empty(py)?,
                                                        "Timeout",
                                                ));
                                        }
                                }
                        };
                        py.check_signals()?;
                }
        }
}

#[pymethods]
impl Queue {
        #[new]
        #[args(maxsize = "0")]
        fn new(maxsize: usize) -> Self {
                let (sender, receiver) = if maxsize == 0 {
                        unbounded()
                } else {
                        bounded(maxsize)
                };
                Self { sender, receiver }
        }

        #[args(block = "true", timeout = "None")]
        fn put(
                &self,
                py: Python,
                item: PyObject,
                block: bool,
                timeout: Option<f64>,
        ) -> PyResult<()> {
                if block == false {
                        self.put_nowait(py, item)
                } else {
                        if let Some(timeout) = timeout {
                                if timeout < 0.0 {
                                        return Err(PyValueError::new_err("Negative timeout"));
                                }
                        }
                        let timeout =
                                timeout.map(|timeout| Duration::from_nanos((timeout * 1e9) as u64));
                        self.send_timeout(py, item, timeout)
                }
        }

        fn put_nowait(&self, py: Python, item: PyObject) -> PyResult<()> {
                self.sender
                        .try_send(item)
                        .or_else(|_| Err(PyErr::from_type(full(py)?, "Full")))
        }

        #[args(block = "true", timeout = "None")]
        fn get(&self, py: Python, block: bool, timeout: Option<f64>) -> PyResult<PyObject> {
                if block == false {
                        self.get_nowait(py)
                } else {
                        if let Some(timeout) = timeout {
                                if timeout < 0.0 {
                                        return Err(PyValueError::new_err("Negative timeout"));
                                }
                        }
                        let timeout =
                                timeout.map(|timeout| Duration::from_nanos((timeout * 1e9) as u64));
                        self.recv_timeout(py, timeout)
                }
        }

        fn get_nowait(&self, py: Python) -> PyResult<PyObject> {
                py.allow_threads(|| self.receiver.try_recv())
                        .or_else(|_| Err(PyErr::from_type(empty(py)?, "Empty")))
        }

        fn qsize(&self) -> usize {
                self.receiver.len()
        }

        fn empty(&self) -> bool {
                self.receiver.is_empty()
        }
}

/// A Python module implemented in Rust.
#[pymodule]
fn py_crossbeam_channel(py: Python, m: &PyModule) -> PyResult<()> {
        m.add_class::<Queue>()?;
        m.add("Empty", empty(py)?)?;
        m.add("Full", full(py)?)?;
        Ok(())
}
