from __future__ import annotations

import hashlib
from pathlib import Path


_WANTED_TAGS = (
    "PatientID",
    "StudyDate",
    "StudyDescription",
    "SeriesDescription",
    "Modality",
    "BodyPartExamined",
    "InstitutionName",
    "Manufacturer",
    "SliceThickness",
)


def dicom_file_node_id(path: Path) -> str:
    digest = hashlib.sha1(str(path.resolve()).encode("utf-8")).hexdigest()[:16]
    return f"dicom_{digest}"


def read_dicom_metadata(path: Path) -> dict[str, str]:
    """Read key metadata from DICOM.

    Returns empty dict when pydicom is unavailable or file parsing fails.
    """
    try:
        import pydicom  # type: ignore
    except Exception:
        return {}

    try:
        ds = pydicom.dcmread(str(path), stop_before_pixels=True, force=True)
    except Exception:
        return {}

    out: dict[str, str] = {}
    for key in _WANTED_TAGS:
        value = getattr(ds, key, None)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            out[key] = text
    return out

