"""Daily update: new trending days -> READMEs of new repos -> incremental index.

    uv run update.py

Registered with Windows Task Scheduler by schedule_daily.ps1. Output is appended
to data/update.log.
"""

import datetime as dt
import os
import subprocess
import sys
from pathlib import Path

STEPS = [
    ["scrape.py"],
    ["fetch_readmes.py"],
    ["build_index.py"],
]
LOG = Path("data/update.log")


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # Task Scheduler / cp949 consoles
    LOG.parent.mkdir(exist_ok=True)
    with LOG.open("a", encoding="utf-8") as log:
        def say(msg: str) -> None:
            line = f"[{dt.datetime.now():%Y-%m-%d %H:%M:%S}] {msg}"
            print(line, flush=True)
            log.write(line + "\n")
            log.flush()

        say("update started")
        for step in STEPS:
            say("run " + " ".join(step))
            proc = subprocess.run(
                [sys.executable, *step], capture_output=True, text=True, encoding="utf-8", errors="replace",
                env={**os.environ, "PYTHONIOENCODING": "utf-8"},
            )
            # progress bars write \r-separated noise to stderr; keep the final lines only
            for line in (proc.stdout + proc.stderr).splitlines()[-8:]:
                say("  " + line.split("\r")[-1])
            if proc.returncode != 0:
                say(f"FAILED ({step[0]} exit {proc.returncode})")
                return proc.returncode
        say("update finished")
    return 0


if __name__ == "__main__":
    sys.exit(main())
