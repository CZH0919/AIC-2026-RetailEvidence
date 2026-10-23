"""Preserve current SQLite state and external planning files before handoff."""
import argparse
from datetime import datetime
from pathlib import Path
import shutil
import sqlite3


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--destination', required=True)
    args = parser.parse_args()
    project = Path(__file__).resolve().parents[1]
    home = project.parent
    target = Path(args.destination).resolve() / datetime.now().strftime('%Y%m%d_%H%M%S')
    target.mkdir(parents=True, exist_ok=False)
    for name in ['项目选题设计.md', '项目开发规划.md']:
        shutil.copy2(home / name, target / name)
    shutil.copy2(home / 'Project_Progress/Overall_Progress.md', target / 'Overall_Progress.md')
    with sqlite3.connect(project / 'storage/state/retailevidence.sqlite3') as source:
        with sqlite3.connect(target / 'retailevidence.sqlite3') as backup:
            source.backup(backup)
    print(target)


if __name__ == '__main__':
    main()
