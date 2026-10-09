"""Private worker protocol. Browser input cannot choose code, modules or filesystem paths."""

import ctypes
import json
import os
import signal
import sys
import traceback
from pathlib import Path


def main():
    job = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    if sys.platform == "linux":
        # Stop this child if its owning application dies; never affect another process.
        if ctypes.CDLL(None).prctl(1, signal.SIGTERM) != 0:
            raise RuntimeError("Cannot establish parent-death signal")
        if os.getppid() != job["parent_pid"]:
            raise SystemExit(2)
    from .import_worker import constrain

    constrain()
    output = Path(job["output"])
    try:
        from .task_registry import run_registered

        def progress(phase, percent):
            temp = output / ".progress.tmp"
            temp.write_text(json.dumps({"phase": phase, "progress": percent}))
            temp.replace(output / ".progress.json")

        run_registered(job, progress)
    except MemoryError:
        (output / ".error.json").write_text(json.dumps({"code": "memory_limit"}))
        raise SystemExit(3) from None
    except Exception as exc:
        from .import_formats import DataIssue

        if isinstance(exc, DataIssue):
            (output / ".error.json").write_text(
                json.dumps({"code": exc.code, "message": exc.message})
            )
            raise SystemExit(2) from None
        traceback.print_exc()
        (output / ".error.json").write_text(json.dumps({"code": "worker_error"}))
        raise SystemExit(2) from None


if __name__ == "__main__":
    main()
