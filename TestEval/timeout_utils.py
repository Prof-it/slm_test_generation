import signal

class TimeoutException(Exception):
    """Custom exception to be raised on a timeout."""
    pass

class timeout:
    """Context manager to handle timeouts."""
    def __init__(self, seconds=60, error_message='Timeout'):
        self.seconds = seconds
        self.error_message = error_message

    def handle_timeout(self, signum, frame):
        raise TimeoutException(self.error_message)

    def __enter__(self):
        # Set the signal handler for the alarm signal
        signal.signal(signal.SIGALRM, self.handle_timeout)
        # Schedule the alarm
        signal.alarm(self.seconds)

    def __exit__(self, type, value, traceback):
        # Cancel the alarm
        signal.alarm(0)