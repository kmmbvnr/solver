"""Compile the optional, dependency-free Rust calendar backend for this machine."""
import argparse
from importlib.resources import as_file,files
from pathlib import Path
import subprocess
import sys


def main():
    extension='.dll' if sys.platform=='win32' else '.dylib' if sys.platform=='darwin' else '.so'
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,default=Path('libshiftopt_calendar'+extension))
    a=p.parse_args()
    source=files('shiftopt').joinpath('native','calendar.rs')
    with as_file(source) as path:
        subprocess.run(['rustc','-C','opt-level=3','--crate-type','cdylib',str(path),'-o',str(a.output)],check=True)
    print(a.output.resolve())


if __name__=='__main__':
    main()
