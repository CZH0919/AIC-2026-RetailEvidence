"""Acquire pinned official datasets. Run from any cwd; never downloads to a PC implicitly."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import urllib.request
import zipfile
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARULES_REVISION = "1eccd3800209b4ec62c7f41abd2ff5f584a20ec7"
ARULES_BASE = f"https://raw.githubusercontent.com/mhahsler/arules/{ARULES_REVISION}"
SOURCES = {
    "online_retail": {
        "title": "UCI Online Retail",
        "id": 352,
        "url": "https://archive.ics.uci.edu/static/public/352/online%2Bretail.zip",
        "page": "https://archive.ics.uci.edu/dataset/352/online+retail",
        "doi": "10.24432/C5BW33",
        "license": "CC BY 4.0",
        "attribution": "Daqing Chen (2015), UCI Machine Learning Repository",
        "expected_rows": 541909,
    },
    "online_retail_ii": {
        "title": "UCI Online Retail II",
        "id": 502,
        "url": "https://archive.ics.uci.edu/static/public/502/online%2Bretail%2Bii.zip",
        "page": "https://archive.ics.uci.edu/dataset/502/online+retail+ii",
        "doi": "10.24432/C5CG6D",
        "license": "CC BY 4.0",
        "attribution": "Daqing Chen (2012), UCI Machine Learning Repository",
        "expected_rows": 1067371,
    },
    "groceries": {
        "title": "arules Groceries",
        "url": f"{ARULES_BASE}/data/Groceries.rda",
        "page": f"{ARULES_BASE}/man/Groceries.Rd",
        "revision": ARULES_REVISION,
        "attribution": "Michael Hahsler, Kurt Hornik, Thomas Reutterer (2006)",
        "expected_baskets": 9835,
        "expected_items": 169,
        "license": "See pinned arules DESCRIPTION and Groceries source notice",
    },
}


def digest(path: Path) -> str:
    sha = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            sha.update(chunk)
    return sha.hexdigest()


def retrieve(url: str, target: Path, maximum: int = 100 * 1024 * 1024) -> None:
    if target.exists():
        return
    partial = target.with_name(target.name + ".part")
    if partial.exists():
        raise RuntimeError(f"A partial download already exists: {partial.name}")
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "RetailEvidence/0.2"})
        with urllib.request.urlopen(request, timeout=60) as response, partial.open("xb") as out:
            total = 0
            for chunk in iter(lambda: response.read(1024 * 1024), b""):
                total += len(chunk)
                if total > maximum:
                    raise RuntimeError("Download exceeds declared resource budget")
                out.write(chunk)
        if target.exists():
            raise RuntimeError("Destination appeared during download")
        partial.rename(target)
    finally:
        partial.unlink(missing_ok=True)


def acquire(root: Path, key: str):
    folder = root / key
    folder.mkdir(parents=True, exist_ok=True)
    meta = folder / "dataset_manifest.json"
    previous = json.loads(meta.read_text()) if meta.exists() else None
    if previous:
        for asset in previous["assets"]:
            assert digest(folder / asset["file"]) == asset["sha256"], "Existing dataset changed"
        print(key, "already acquired", flush=True)
        return
    source = SOURCES[key]
    files = []
    if key.startswith("online_retail"):
        archive = folder / "download.zip"
        retrieve(source["url"], archive)
        with zipfile.ZipFile(archive) as z:
            names = [i for i in z.infolist() if i.filename.lower().endswith(".xlsx")]
            if len(names) != 1 or names[0].file_size > 100 * 1024 * 1024:
                raise RuntimeError("Unexpected official archive layout")
            target = folder / "source.xlsx"
            if not target.exists():
                with z.open(names[0]) as src, target.open("xb") as out:
                    shutil.copyfileobj(src, out)
            files = [(archive, source["url"]), (target, source["url"])]
            source = {**source, "original_filename": names[0].filename}
    else:
        for filename, suffix in [
            ("Groceries.rda", "data/Groceries.rda"),
            ("DESCRIPTION", "DESCRIPTION"),
            ("Groceries.Rd", "man/Groceries.Rd"),
        ]:
            target = folder / filename
            url = f"{ARULES_BASE}/{suffix}"
            retrieve(url, target, 4 * 1024 * 1024)
            files.append((target, url))
    manifest = {
        "dataset": key,
        "source": source,
        "retrieved_at": datetime.now(UTC).isoformat(),
        "preparation_script_sha256": digest(Path(__file__)),
        "assets": [
            {"file": p.name, "bytes": p.stat().st_size, "sha256": digest(p), "url": url}
            for p, url in files
        ],
        "profile_status": "pending",
        "distribution": "Original/converted data excluded from code repository",
    }
    with meta.open("x", encoding="utf-8") as out:
        json.dump(manifest, out, ensure_ascii=False, indent=2)
        out.write("\n")
    print(key, "acquired", [(p.name, p.stat().st_size) for p, _ in files], flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="storage/datasets/public")
    parser.add_argument("--dataset", choices=[*SOURCES, "all"], default="all")
    args = parser.parse_args()
    output = Path(args.output)
    if not output.is_absolute():
        output = ROOT / output
    if hasattr(os, "sched_setaffinity"):
        os.sched_setaffinity(0, sorted(os.sched_getaffinity(0))[:2])
    for key in SOURCES if args.dataset == "all" else [args.dataset]:
        acquire(output, key)


if __name__ == "__main__":
    main()
