"""Run every tests/test_*.py; print one line per file, then the count and the time.

    python tests/run_all.py                    all files in one app (one process)
    python tests/run_all.py --isolated         each file in its own process (slower)
    python tests/run_all.py plots select       only test_plots.py and test_select.py

In one app the imports, the app and VTK's first window are paid once; each file still
starts with its own scratch settings and no window open (conftest.fresh_start). A file
that crashes the shared process is run again on its own, and so are the files after it.
"""
import os
import runpy
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).parent
START, END = "@@start ", "@@end "


def _cmd():
    cmd = [sys.executable]
    if sys.platform.startswith("linux") and not os.environ.get("DISPLAY") and shutil.which("xvfb-run"):
        cmd = ["xvfb-run", "-a", "-s", "-screen 0 1600x1200x24", sys.executable]
    return cmd


def _worker(paths):
    """In the subprocess: every file in one app."""
    import conftest
    conftest.SHARED["app"] = app = conftest.make_app()
    for path in paths:
        conftest.fresh_start(app)
        t = time.time()
        print(START + Path(path).name, flush=True)
        try:
            runpy.run_path(path, run_name="__main__")
        except SystemExit:
            pass
        except Exception:
            import traceback
            traceback.print_exc()
            print("0 passed, 1 failed (exception)", flush=True)
        print(f"{END}{Path(path).name} {time.time() - t:.1f}", flush=True)
    sys.stderr.flush()
    os._exit(0)                                   # no teardown of VTK / Qt at exit


def _report(name, out, err="", rc=0, took=None):
    """One line for a file; its failures under it. Returns (checks, failed)."""
    lines = [l for l in out.splitlines() if l.startswith(("PASS", "FAIL")) or "passed," in l]
    fails = [l for l in lines if l.startswith("FAIL")]
    summary = next((l for l in reversed(lines) if "passed," in l), None)
    print(f"{name:24s} {took or '':>6s}  {summary or 'no result'}")
    for l in fails:
        print("   ", l)
    n = sum(l.startswith(("PASS", "FAIL")) for l in lines)
    bad = bool(fails) or summary is None or "exception" in out or rc != 0
    if summary is None or "exception" in out or rc != 0:
        print(out[-1500:], err[-1500:])
    return n, bad


def _isolated(path):
    t = time.time()
    r = subprocess.run(_cmd() + [str(path)], capture_output=True, text=True)
    return _report(path.name, r.stdout, r.stderr, r.returncode, f"{time.time() - t:.1f}s")


def _start(tests):
    """A worker process running these files in one app (the files in the environment,
    not argv: macOS hands argv to the app as files to open)."""
    env = {**os.environ, "MESHVIEWER_TESTS": os.pathsep.join(map(str, tests))}
    return subprocess.Popen(_cmd() + [__file__, "--worker"], stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True, env=env)


def _chunks(out):
    """{file name: [its output, its time]} from a worker's output."""
    chunks, cur = {}, None
    for line in out.splitlines(keepends=True):
        if line.startswith(START):
            cur = line[len(START):].strip()
            chunks[cur] = [""]
        elif line.startswith(END):
            name, took = line[len(END):].split()
            chunks[name].append(took + "s")
            cur = None
        elif cur is not None:
            chunks[cur][0] += line
    return chunks


def main(args):
    t0 = time.time()
    names = [a for a in args if not a.startswith("-")]
    tests = sorted(HERE.glob("test_*.py"))
    if names:
        tests = [t for t in tests if any(t.stem in (n, f"test_{n}", Path(n).stem) for n in names)]
    checks = failed = 0
    if "--isolated" in args:
        todo = tests
    else:
        # (not in parallel: a second app's windows and popup menus get in the way of
        # the screen grabs and menus checked here)
        out, err = _start(tests).communicate()
        chunks = _chunks(out)
        todo = []
        for t in tests:
            c = chunks.get(t.name)
            if c is None or len(c) < 2:                # the worker stopped before its end
                todo.append(t)
                continue
            n, bad = _report(t.name, c[0], took=c[1])
            checks, failed = checks + n, failed + bad
        if todo:
            print(f"(the shared run stopped in {todo[0].name}: run again one by one)")
            print(out[-1500:], err[-3000:])
    for t in todo:
        n, bad = _isolated(t)
        checks, failed = checks + n, failed + bad
    print(f"{checks} checks in {len(tests)} files, {failed} file(s) failing, "
          f"{time.time() - t0:.1f} s")
    return 1 if failed else 0


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--worker":
        sys.path.insert(0, str(HERE))
        _worker(os.environ["MESHVIEWER_TESTS"].split(os.pathsep))
    sys.exit(main(sys.argv[1:]))
