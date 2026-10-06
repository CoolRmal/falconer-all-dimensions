import errno
import os
import socket
from pathlib import Path

assert os.getuid() != 0, 'Comparator must run as an unprivileged user'
root = Path.cwd()

# systemd's address-family filter must be active, not merely configured.
try:
    socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
except OSError as error:
    assert error.errno in (errno.EAFNOSUPPORT, errno.EPERM, errno.EACCES), error
else:
    raise AssertionError('AF_UNIX was not blocked')

# Check the actual Landrun sandbox: source is read-only; build output is writable.
forbidden = root / '.sandbox-forbidden-write'
try:
    forbidden.write_text('sandbox failure\n')
except PermissionError:
    pass
else:
    forbidden.unlink(missing_ok=True)
    raise AssertionError('Landrun allowed modification outside .lake')

allowed = root / '.lake' / '.sandbox-allowed-write'
allowed.write_text('sandbox passed\n')
allowed.unlink()
print('Security preflight passed: non-root, AF_UNIX blocked, source read-only, .lake writable', flush=True)
