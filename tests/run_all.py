"""Run every tests/test_*.py in its own process; print one line per file."""
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
cmd = [sys.executable]
if sys.platform.startswith("linux") and not os.environ.get("DISPLAY") and shutil.which("xvfb-run"):
    cmd = ["xvfb-run", "-a", "-s", "-screen 0 1600x1200x24", sys.executable]
bad = 0
for t in sorted(HERE.glob("test_*.py")):
    r = subprocess.run(cmd + [str(t)], capture_output=True, text=True)
    lines = [l for l in r.stdout.splitlines() if l.startswith(("PASS", "FAIL")) or "passed," in l]
    fails = [l for l in lines if l.startswith("FAIL")]
    print(f"{t.name:28s} {lines[-1] if lines else 'no result'}")
    for l in fails:
        print("   ", l)
    if r.returncode:
        bad += 1
        if not lines or "exception" in r.stdout:
            print(r.stdout[-1500:], r.stderr[-1500:])
sys.exit(1 if bad else 0)
