"""Assemble .349 ZIP files for submission."""

import zipfile
from datetime import datetime
from io import BytesIO
from pathlib import Path

from yabilabb.envelope import build_envelope
from yabilabb.models import Declaration


def _make_filename(decl: Declaration) -> str:
    """Generate the canonical filename matching BILA convention.

    BILA pattern: {year}T{quarter}_{nif_without_prefix}.349
    Examples: 2024T03_12345678.349, 2025T04_12345678.349
    The NIF prefix letter (NIE Z/X/Y or entity B/etc) is dropped.
    """
    period = decl.period
    if period.endswith("T"):
        period_str = f"T{period[:-1].zfill(2)}"
    else:
        period_str = period

    # BILA drops the first character of the NIF (type prefix)
    nif = decl.declarant.nif
    nif_short = nif[1:] if len(nif) == 9 and nif[0].isalpha() else nif

    return f"{decl.exercise_year}{period_str}_{nif_short}"


def write_349(
    decl: Declaration,
    output_path: Path | None = None,
    creation_dt: datetime | None = None,
) -> Path:
    """Generate a .349 ZIP file from a Declaration.

    Returns the path to the generated file.
    """
    if creation_dt is None:
        creation_dt = datetime.now()

    base_name = _make_filename(decl)
    tmp_name = f"{base_name}_349.tmp"

    envelope_bytes = build_envelope(decl, creation_dt)

    if output_path is None:
        output_path = Path(f"{base_name}.349")

    buf = BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(tmp_name, envelope_bytes)

    output_path.write_bytes(buf.getvalue())
    return output_path
