"""Run CSV/XLSX browsers sequentially with separate evidence and profiles.
Requires an already running isolated app and explicit RETAIL_TEST_ROOT, browser,
font and cache environment. Never starts or migrates an application database.
"""
import json
import os
from pathlib import Path
import subprocess

root = Path(os.environ["RETAIL_TEST_ROOT"]).resolve()
source = Path(__file__).resolve().parent
node = os.environ["RETAIL_NODE"]
results = []
for kind, script in [("csv", "browser_e2e.cjs"), ("xlsx", "browser_xlsx.cjs")]:
    target = root / kind
    (target / "evidence").mkdir(parents=True, exist_ok=True)
    if not (target / "data").exists():
        (target / "data").symlink_to(root / "data", target_is_directory=True)
    env = {**os.environ, "RETAIL_TEST_ROOT": str(target)}
    with (target / "evidence/browser.log").open("w") as log:
        run = subprocess.run([node, str(source / script)], env=env, cwd=source.parent.parent,
                             stdout=log, stderr=subprocess.STDOUT, timeout=540)
    results.append({"kind": kind, "exit": run.returncode})
    (root / "evidence/import-suite.json").write_text(json.dumps(results, indent=2))
    run.check_returncode()
