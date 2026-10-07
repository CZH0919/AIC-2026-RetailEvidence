import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def project_path(value: str | Path) -> Path:
    path = Path(value).expanduser()
    return (path if path.is_absolute() else PROJECT_ROOT / path).resolve()


def configured_path(variable: str, default: str) -> Path:
    return project_path(os.environ.get(variable, default))


MAX_FILE_BYTES = 100 * 1024 * 1024
MAX_ROWS = 1_500_000
MAX_COLUMNS = 200
MAX_XLSX_BYTES = 1024 * 1024 * 1024
MAX_CELL_CHARS = 32768
PREVIEW_ROWS = 20
