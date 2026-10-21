"""Web app: API validation and one real end-to-end flow
(upload a program -> BO search -> verify comparison), isolated in a temp dir."""
import time
from pathlib import Path

import pytest

pytest.importorskip("flask")

TOY = (Path(__file__).parent / "data" / "toy" / "toy.c").read_text()
# the uploaded copy lives one level deeper (benchmarks/custom/<name>/), so fix the include path
TOY_UPLOAD = TOY.replace('"../../../benchmarks/common/bench_timer.h"', '"../../common/bench_timer.h"')


@pytest.fixture
def client(tmp_path, monkeypatch, cc):
    import web.app as webapp
    import web.custom as custom
    import web.jobs as jobs

    cdir = tmp_path / "custom"
    monkeypatch.setattr(custom, "CUSTOM_DIR", cdir)
    monkeypatch.setattr(custom, "REGISTRY", cdir / "custom.yaml")
    for mod in (jobs, webapp):
        monkeypatch.setattr(mod, "SEARCH_DIR", tmp_path / "web" / "search")
        monkeypatch.setattr(mod, "COMPARE_DIR", tmp_path / "web" / "compare")
    app = webapp.create_app(jobs_store=tmp_path / "web" / "jobs.json")
    app.testing = True
    # uploaded sources must sit where '../../common/bench_timer.h' resolves
    common = cdir.parent / "common"
    common.mkdir(parents=True, exist_ok=True)
    root_common = Path(__file__).resolve().parents[1] / "benchmarks" / "common"
    for f in root_common.iterdir():
        (common / f.name).write_text(f.read_text())
    return app.test_client()


def wait_job(client, job_id, timeout=240):
    t0 = time.time()
    while time.time() - t0 < timeout:
        j = client.get(f"/api/jobs/{job_id}").get_json()
        if j["status"] not in ("queued", "running"):
            return j
        time.sleep(0.5)
    raise AssertionError("job did not finish")


def test_info_and_pages(client):
    assert client.get("/").status_code == 200
    info = client.get("/api/info").get_json()
    assert info["dim"] >= 2 and info["n_configs"] == 2 ** info["dim"]
    assert {b["name"] for b in info["benchmarks"]} >= {"matmul", "sort"}


def test_project_endpoints(client):
    d = client.get("/api/dashboard").get_json()
    assert {"runs", "evaluations", "programs", "recent"} <= set(d)
    p = client.get("/api/params").get_json()
    assert p["experiment"]["budget"] > 0 and p["bo"]["xi"] > 0 and p["dim"] >= 2
    c = client.get("/api/corpus").get_json()
    if c["available"]:
        assert c["bytes"] > 1_000_000 and c["words"] > 100_000 and len(c["top_words"]) == 20
        assert {p["name"] for p in c["programs"]} >= {"compress", "sha256", "wordfreq"}
    src = client.get("/api/source/matmul").get_json()
    assert "int main" in src["code"]
    assert client.get("/api/source/../../etc").status_code == 404
    assert client.get("/api/curves?bench=matmul").status_code == 200
    assert client.get("/api/manuscript/info").status_code == 200
    for js in ("core.js", "pages-run.js", "pages-project.js", "style.css"):
        assert client.get(f"/static/{js}").status_code == 200


def test_validation(client):
    assert client.post("/api/jobs", json={"type": "search", "bench": "nope"}).status_code == 400
    assert client.post("/api/jobs", json={"type": "search", "bench": "matmul", "budget": 1}).status_code == 400
    assert client.post("/api/jobs", json={"type": "search", "bench": "matmul", "method": "x"}).status_code == 400
    bad = {"type": "compare", "bench": "matmul", "candidates": [{"name": "evil", "flags": ["-O3", "-o", "/tmp/x"]}]}
    assert client.post("/api/jobs", json=bad).status_code == 400
    bad2 = {"type": "compare", "bench": "matmul", "candidates": [{"name": "x", "flags": ["-fno-tree-pre"]}]}
    assert client.post("/api/jobs", json=bad2).status_code == 400          # must start with an -O level
    assert client.post("/api/benchmarks", json={"name": "Bad Name", "source": "int main(){}"}).status_code == 400
    assert client.post("/api/benchmarks", json={"name": "matmul", "source": "int main(){}"}).status_code == 400
    assert client.get("/api/runs/web/..%2F..").status_code == 404


def test_upload_rejects_broken_program(client):
    r = client.post("/api/benchmarks", json={"name": "broken", "source": "int main(void) { return 0 }"})
    assert r.status_code == 400 and "compilation failed" in r.get_json()["error"]


def test_end_to_end_upload_search_verify(client):
    r = client.post("/api/benchmarks", json={"name": "toyweb", "source": TOY_UPLOAD, "args": "100000 40"})
    assert r.status_code == 200, r.get_json()
    assert r.get_json()["timing"] == "kernel"
    plain = '#include <stdio.h>\nint main(void){unsigned long long s=0;for(unsigned i=0;i<30000000u;i++)s+=i%7;printf("%llu\\n",s);return 0;}\n'
    r2 = client.post("/api/benchmarks", json={"name": "plainweb", "source": plain})
    assert r2.status_code == 200 and r2.get_json()["timing"] == "wall"

    jobs = client.post("/api/jobs", json={"type": "search", "bench": "toyweb", "method": "both",
                                          "budget": 6, "reps": 1, "n_init": 3, "seed": 1}).get_json()
    assert len(jobs) == 2
    for j in jobs:
        done = wait_job(client, j["id"])
        assert done["status"] == "done", done
        run = client.get(f"/api/runs/web/{j['exp_id']}").get_json()
        assert len(run["evals"]) == 6 and run["summary"]["best_flags"]
    runs = client.get("/api/runs").get_json()
    best = next(r for r in runs if r["exp_id"] == jobs[0]["exp_id"])
    cmp = client.post("/api/jobs", json={"type": "compare", "bench": "toyweb", "reps": 3,
                                         "candidates": [{"name": "O2", "flags": ["-O2"]},
                                                        {"name": "bo best", "flags": best["best_flags"]}]}).get_json()
    done = wait_job(client, cmp[0]["id"])
    assert done["status"] == "done", done
    res = client.get(f"/api/compare/{cmp[0]['id']}").get_json()
    names = {c["name"] for c in res["candidates"]}
    assert names == {"O3", "O2", "bo best"}
    assert all(len(c["times_ms"]) == 3 for c in res["candidates"])
    assert "verdict" in next(c for c in res["candidates"] if c["name"] == "O2")

    w = client.post("/api/jobs", json={"type": "search", "bench": "plainweb", "method": "random",
                                       "budget": 5, "reps": 1, "n_init": 2}).get_json()
    assert wait_job(client, w[0]["id"])["status"] == "done"
    assert client.delete("/api/benchmarks/plainweb").status_code == 200


def test_cancel(client):
    client.post("/api/benchmarks", json={"name": "toycancel", "source": TOY_UPLOAD, "args": "100000 40"})
    j = client.post("/api/jobs", json={"type": "search", "bench": "toycancel", "method": "random",
                                       "budget": 100, "reps": 1, "n_init": 2}).get_json()[0]
    time.sleep(3)
    client.post(f"/api/jobs/{j['id']}/cancel")
    done = wait_job(client, j["id"])
    assert done["status"] == "cancelled"
    run = client.get(f"/api/runs/web/{j['exp_id']}").get_json()
    assert len(run["evals"]) < 100
