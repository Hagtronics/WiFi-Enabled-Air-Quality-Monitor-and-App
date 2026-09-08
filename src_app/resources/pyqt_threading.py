"""
Threading Class is taken from Martin Fitzpatrick's excellent website: PythonGUI's,

https://www.pythonguis.com/tutorials/multithreading-pyqt-applications-qthreadpool/

Martin lists his license for this code as:
    Python GUIs Copyright ©2014-2026 Martin Fitzpatrick - Public code BSD & MIT
"""

try:
    from PyQt6.QtCore import QObject, QRunnable, QThreadPool, pyqtSignal, pyqtSlot
except:
    from PyQt5.QtCore import QObject, QRunnable, QThreadPool, pyqtSignal, pyqtSlot

import sys
import traceback


class WorkerSignals(QObject):
    """
    Signals from a running worker thread.

    finished
        int thread_id

    error
        tuple (exctype, value, traceback.format_exc())

    result
        object data returned from processing, anything

    progress
        tuple (thread_id, progress_value)
    """

    finished = pyqtSignal(int)  # thread_id
    error = pyqtSignal(tuple)
    result = pyqtSignal(object)
    progress = pyqtSignal(tuple)  # (thread_id, progress_value)

class Worker(QRunnable):
    """
    Worker thread.

    Inherits from QRunnable to handler worker thread setup, signals and wrap-up.

    :param callback: The function callback to run on this worker thread.
                     Supplied args and
                     kwargs will be passed through to the runner.
    :type callback: function
    :param args: Arguments to pass to the callback function
    :param kwargs: Keywords to pass to the callback function
    """

    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()
        self.thread_id = kwargs.get("thread_id", 0)
        # Add the callback to our kwargs
        self.kwargs["progress_callback"] = self.signals.progress

    @pyqtSlot()
    def run(self):
        try:
            result = self.fn(*self.args, **self.kwargs)
        except Exception:
            traceback.print_exc()
            exctype, value = sys.exc_info()[:2]
            self.signals.error.emit((exctype, value, traceback.format_exc()))
        else:
            self.signals.result.emit(result)
        finally:
            self.signals.finished.emit(self.thread_id)

"""
Example calls usage:

    def progress_fn(self, data):
        thread_id, n = data
        print(f"THREAD #{thread_id}: {n:d}% done")

    def execute_this_fn(self, progress_callback, thread_id):
        for n in range(0, 5):
            time.sleep(1)
            progress = n * 100 / 4
            progress_callback.emit((thread_id, progress))
        return "Done."

    def print_output(self, s):
        print(s)

    def thread_complete(self, thread_id):
        print(f"THREAD #{thread_id} COMPLETE!")

    def oh_no(self):
        # Pass the function to execute
        self.thread_id += 1
        worker = Worker(
            self.execute_this_fn, thread_id=self.thread_id
        )  # Any other args, kwargs are passed to the run function
        worker.signals.result.connect(self.print_output)
        worker.signals.finished.connect(self.thread_complete)
        worker.signals.progress.connect(self.progress_fn)
        # Execute
        self.threadpool.start(worker)

    def recurring_timer(self):
        self.counter += 1
        self.label.setText(f"Counter: {self.counter}")

"""
