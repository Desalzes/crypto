import sys
import time
import threading
from contextlib import contextmanager

class SpinnerIndicator:
    def __init__(self):
        self.spinner_chars = ['⠋','⠙','⠹','⠸','⠼','⠴','⠦','⠧','⠇','⠏']
        self.busy = False
        self.delay = 0.1
        self.spinner_thread = None

    def spinner_task(self):
        while self.busy:
            for char in self.spinner_chars:
                if not self.busy:
                    break
                sys.stdout.write(f'\r{char} Analyzing markets...')
                sys.stdout.flush()
                time.sleep(self.delay)
        sys.stdout.write('\r')
        sys.stdout.flush()

    def __enter__(self):
        self.busy = True
        self.spinner_thread = threading.Thread(target=self.spinner_task)
        self.spinner_thread.start()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.busy = False
        if self.spinner_thread:
            self.spinner_thread.join()

@contextmanager
def trading_spinner():
    spinner = SpinnerIndicator()
    with spinner:
        yield