import os
from pathlib import Path
import tempfile
from contextlib import contextmanager

import numpy as np


def table(root, name):
    return np.array([[float(x.text) for x in row] for row in root.find(name)])


@contextmanager
def atomic_output(path,mode):
    path=Path(path)
    with tempfile.NamedTemporaryFile(mode=mode,dir=path.parent,delete=False) as f:
        tmp=Path(f.name)
        try:
            yield f
            f.flush()
            os.fsync(f.fileno())
        except BaseException:
            tmp.unlink(missing_ok=True)
            raise
    try:
        os.replace(tmp,path)
        fd=os.open(path.parent,os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    finally:
        tmp.unlink(missing_ok=True)
