from __future__ import annotations

import shutil
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_DIR = PROJECT_ROOT / 'templates' / 'patient-records-template-v2'


def template_dir() -> Path:
    return TEMPLATE_DIR


def init_patient_records(target_dir: str | Path, *, force: bool = False) -> Path:
    src = template_dir()
    if not src.exists():
        raise FileNotFoundError(f'template directory not found: {src}')

    target = Path(target_dir).expanduser().resolve()
    if target.exists():
        if any(target.iterdir()) and not force:
            raise FileExistsError(f'target directory is not empty: {target}')
    else:
        target.mkdir(parents=True, exist_ok=True)

    for item in src.iterdir():
        dst = target / item.name
        if item.is_dir():
            if dst.exists() and force:
                shutil.rmtree(dst)
            shutil.copytree(item, dst, dirs_exist_ok=force or True)
        else:
            shutil.copy2(item, dst)
    return target
