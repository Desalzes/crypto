import sys
import threading
import time
import itertools
from contextlib import contextmanager

class SpinnerIndicator:
    def __init__(self, message="Processing", delay=0.1):
        self.spinner = itertools.cycle(['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏'])
        self.delay = delay
        self.message = message
        self.busy = False
        self.spinner_thread = None

    def spinner_task(self):
        while self.busy:
            sys.stdout.write(f'\r{next(self.spinner)} {self.message} ')
            sys.stdout.flush()
            time.sleep(self.delay)

    def __enter__(self):
        self.busy = True
        self.spinner_thread = threading.Thread(target=self.spinner_task)
        self.spinner_thread.start()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.busy = False
        time.sleep(self.delay)
        if self.spinner_thread is not None:
            self.spinner_thread.join()
        sys.stdout.write('\r')
        sys.stdout.flush()

@contextmanager
def progress_spinner(message="Processing"):
    """Context manager for showing a spinning progress indicator."""
    spinner = SpinnerIndicator(message)
    try:
        with spinner:
            yield
    finally:
        sys.stdout.write('\r\033[K')  # Clear the line
        sys.stdout.flush()