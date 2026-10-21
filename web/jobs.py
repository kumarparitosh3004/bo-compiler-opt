"""Job queue for the web app.

One worker thread runs one job at a time: two searches running in parallel
would disturb each other's timings. Jobs survive a server restart in
results/web/jobs.json (a job that was running is marked "interrupted"; re-running
the same search resumes it).
"""
from __future__ import annotations

import json
import queue
import threading
import time
import traceback
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path

from bopass import compare as cmp
from bopass.config import BUILD_DIR, RESULTS_DIR, compiler_path, fixed_flags
from bopass.orchestrator import experiment_id, run_search

from .custom import all_benchmarks

WEB_DIR = RESULTS_DIR / "web"
SEARCH_DIR = WEB_DIR / "search"
COMPARE_DIR = WEB_DIR / "compare"


@dataclass
class Job:
    id: str
    type: str                      # "search" | "compare"
    params: dict
    status: str = "queued"         # queued | running | done | failed | cancelled | interrupted
    created_at: str = ""
    started_at: str | None = None
    finished_at: str | None = None
    exp_id: str | None = None      # search jobs: results/web/search/<exp_id>
    result_file: str | None = None # compare jobs: results/web/compare/<id>.json
    message: str = ""
    progress: dict = field(default_factory=dict)
    error: str | None = None
    summary: dict | None = None


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


class JobManager:
    def __init__(self, cfg: dict, store: Path = WEB_DIR / "jobs.json"):
        self.cfg = cfg
        self.store = store
        self.lock = threading.Lock()
        self.save_lock = threading.Lock()
        self.jobs: dict[str, Job] = {}
        self.cancel_events: dict[str, threading.Event] = {}
        self.q: queue.Queue[str] = queue.Queue()
        self._load()
        self.worker = threading.Thread(target=self._work, name="bopass-worker", daemon=True)
        self.worker.start()

    # ---- persistence ----------------------------------------------------------------
    def _load(self):
        if not self.store.exists():
            return
        for d in json.loads(self.store.read_text(encoding="utf-8")):
            j = Job(**d)
            if j.status in ("queued", "running"):
                j.status, j.message = "interrupted", "server restarted before this job finished"
            self.jobs[j.id] = j

    def _save(self):
        """Persist the job list. Serialized by its own lock: the worker thread and
        request threads both save, and on Windows two concurrent renames onto
        jobs.json fail. A save failure is retried and never kills the worker."""
        self.store.parent.mkdir(parents=True, exist_ok=True)
        with self.save_lock:
            with self.lock:
                data = [asdict(j) for j in self.jobs.values()]
            tmp = self.store.with_suffix(".tmp")
            for attempt in range(5):
                try:
                    tmp.write_text(json.dumps(data, indent=1), encoding="utf-8")
                    tmp.replace(self.store)
                    return
                except OSError:          # file briefly locked (antivirus, indexer)
                    time.sleep(0.05 * (attempt + 1))

    # ---- public API -----------------------------------------------------------------
    def submit(self, type_: str, params: dict) -> Job:
        j = Job(id=uuid.uuid4().hex[:8], type=type_, params=params, created_at=now())
        if type_ == "search":
            j.exp_id = experiment_id(params["bench"], params["method"], params["seed"], j.id)
            j.progress = {"done": 0, "total": params["budget"]}
        with self.lock:
            self.jobs[j.id] = j
            self.cancel_events[j.id] = threading.Event()
        self._save()
        self.q.put(j.id)
        return j

    def cancel(self, job_id: str) -> Job:
        j = self.jobs[job_id]
        if j.status == "queued":
            j.status, j.finished_at, j.message = "cancelled", now(), "cancelled before it started"
        elif j.status == "running":
            self.cancel_events[job_id].set()
            j.message = "cancelling after the current evaluation..."
        self._save()
        return j

    def list(self) -> list[dict]:
        with self.lock:
            return [asdict(j) for j in sorted(self.jobs.values(), key=lambda j: j.created_at, reverse=True)]

    def get(self, job_id: str) -> dict | None:
        j = self.jobs.get(job_id)
        return asdict(j) if j else None

    def busy(self) -> bool:
        return any(j.status in ("queued", "running") for j in self.jobs.values())

    # ---- worker ---------------------------------------------------------------------
    def _work(self):
        while True:
            job_id = self.q.get()
            j = self.jobs.get(job_id)
            if j is None or j.status != "queued":
                continue
            j.status, j.started_at, j.message = "running", now(), "starting"
            self._save()
            ev = self.cancel_events.setdefault(job_id, threading.Event())
            try:
                if j.type == "search":
                    self._run_search(j, ev)
                else:
                    self._run_compare(j, ev)
                j.status = "cancelled" if ev.is_set() else "done"
                j.message = "cancelled" if ev.is_set() else "finished"
            except cmp.Cancelled:
                j.status, j.message = "cancelled", "cancelled"
            except Exception as e:  # noqa: BLE001 - report any failure to the UI
                j.status, j.error = "failed", f"{type(e).__name__}: {e}"
                j.message = traceback.format_exc(limit=3)[-600:]
            j.finished_at = now()
            self._save()

    def _cfg_for(self, p: dict) -> dict:
        c = dict(self.cfg)
        c["search_reps"] = int(p.get("reps", c.get("search_reps", 5)))
        c["n_init"] = int(p.get("n_init", c.get("n_init", 8)))
        c["wallclock_cap_h"] = float(p.get("wallclock_cap_h", 2))
        return c

    def _run_search(self, j: Job, ev: threading.Event):
        p = j.params
        j.message = f"searching {p['bench']} with {p['method']}"
        summary = run_search(p["bench"], p["method"], int(p["seed"]), self._cfg_for(p), budget=int(p["budget"]),
                             results_root=SEARCH_DIR, build_root=BUILD_DIR / "web", tag=j.id,
                             benchmarks=all_benchmarks(), should_stop=ev.is_set)
        j.summary = {k: v for k, v in summary.items() if k != "length_scales"}
        j.progress = {"done": summary.get("evaluations", 0), "total": int(p["budget"])}

    def _run_compare(self, j: Job, ev: threading.Event):
        p = j.params
        bench = all_benchmarks()[p["bench"]]
        cands = [{"name": c["name"], "flags": c["flags"]} for c in p["candidates"]]

        def progress(msg, done=None, total=None):
            j.message = msg
            if done is not None:
                j.progress = {"done": done, "total": total}

        res = cmp.compare(bench, cands, compiler_path(self.cfg), fixed_flags(self.cfg), BUILD_DIR / "web_compare",
                          reps=int(p.get("reps", 15)), seed=int(p.get("seed", 0)), should_stop=ev.is_set,
                          progress=progress)
        res["kind"] = p.get("kind", "custom")
        res["job_id"] = j.id
        COMPARE_DIR.mkdir(parents=True, exist_ok=True)
        out = COMPARE_DIR / f"{j.id}.json"
        out.write_text(json.dumps(res, indent=1), encoding="utf-8")
        j.result_file = out.name
