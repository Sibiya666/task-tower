"""Fixed exec bootstrap: undo the trusted parent's launch-time TERM mask."""
import os
import signal
import sys

signal.pthread_sigmask(signal.SIG_UNBLOCK, {signal.SIGTERM})
os.execvpe(sys.argv[1], sys.argv[1:], os.environ)
