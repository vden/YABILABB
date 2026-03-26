"""Assemble .349 ZIP files for submission.

Produces Java-compatible ZIP files matching BILA's ZipOutputStream output:
- Data descriptor present (flag bit 3)
- UTF-8 filename encoding flag (flag bit 11)
- create_system = 0 (MSDOS/Windows)
- external_attr = 0
"""

import struct
import zlib
from datetime import datetime
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

    nif = decl.declarant.nif
    nif_short = nif[1:] if len(nif) == 9 and nif[0].isalpha() else nif

    return f"{decl.exercise_year}{period_str}_{nif_short}"


def _dos_datetime(dt: datetime) -> int:
    """Convert datetime to MSDOS date/time format (2 x 16-bit)."""
    date = ((dt.year - 1980) << 9) | (dt.month << 5) | dt.day
    time = (dt.hour << 11) | (dt.minute << 5) | (dt.second // 2)
    return (date << 16) | time


def _build_java_zip(filename: str, data: bytes, dt: datetime) -> bytes:
    """Build a ZIP file matching Java's ZipOutputStream format.

    Java uses: flag_bits=0x0808 (data descriptor + UTF-8),
    create_system=0, external_attr=0, version=20.
    """
    fname_bytes = filename.encode("utf-8")
    crc = zlib.crc32(data) & 0xFFFFFFFF
    compressed = zlib.compress(data, 6)[2:-4]  # raw deflate (strip zlib header/trailer)

    dos_dt = _dos_datetime(dt)
    dos_time = dos_dt & 0xFFFF
    dos_date = (dos_dt >> 16) & 0xFFFF

    flag_bits = 0x0808  # bit 3: data descriptor, bit 11: UTF-8

    # Local file header
    local_header = struct.pack(
        "<4sHHHHHIIIHH",
        b"PK\x03\x04",       # signature
        20,                   # version needed to extract
        flag_bits,            # general purpose bit flag
        8,                    # compression method (deflate)
        dos_time,             # last mod time
        dos_date,             # last mod date
        0,                    # crc-32 (0 because data descriptor)
        0,                    # compressed size (0 because data descriptor)
        0,                    # uncompressed size (0 because data descriptor)
        len(fname_bytes),     # filename length
        0,                    # extra field length
    )

    # Data descriptor (after compressed data)
    data_descriptor = struct.pack(
        "<4sIII",
        b"PK\x07\x08",       # signature
        crc,                  # crc-32
        len(compressed),      # compressed size
        len(data),            # uncompressed size
    )

    # Central directory entry
    central_dir = struct.pack(
        "<4sHHHHHHIIIHHHHHII",
        b"PK\x01\x02",       # signature
        20,                   # version made by (20 = 2.0, system=0 MSDOS)
        20,                   # version needed
        flag_bits,            # flags
        8,                    # compression
        dos_time,             # time
        dos_date,             # date
        crc,                  # crc-32
        len(compressed),      # compressed size
        len(data),            # uncompressed size
        len(fname_bytes),     # filename length
        0,                    # extra field length
        0,                    # file comment length
        0,                    # disk number start
        0,                    # internal file attributes
        0,                    # external file attributes (0 for Java/Windows)
        0,                    # relative offset of local header
    )

    # End of central directory
    cd_offset = len(local_header) + len(fname_bytes) + len(compressed) + len(data_descriptor)
    cd_size = len(central_dir) + len(fname_bytes)

    eocd = struct.pack(
        "<4sHHHHIIH",
        b"PK\x05\x06",       # signature
        0,                    # disk number
        0,                    # disk with central directory
        1,                    # entries on this disk
        1,                    # total entries
        cd_size,              # central directory size
        cd_offset,            # central directory offset
        0,                    # comment length
    )

    return (
        local_header + fname_bytes +
        compressed + data_descriptor +
        central_dir + fname_bytes +
        eocd
    )


def write_349(
    decl: Declaration,
    output_path: Path | None = None,
    creation_dt: datetime | None = None,
) -> Path:
    """Generate a .349 ZIP file from a Declaration."""
    if creation_dt is None:
        creation_dt = datetime.now()

    base_name = _make_filename(decl)
    tmp_name = f"{base_name}_349.tmp"

    envelope_bytes = build_envelope(decl, creation_dt)

    if output_path is None:
        output_path = Path(f"{base_name}.349")

    # Use preserved creation timestamp for the ZIP entry
    meta = decl.bila_metadata
    if meta.fcreac and meta.hcreac:
        dt = datetime.strptime(f"{meta.fcreac}{meta.hcreac}", "%Y%m%d%H%M%S")
    else:
        dt = creation_dt

    zip_bytes = _build_java_zip(tmp_name, envelope_bytes, dt)
    output_path.write_bytes(zip_bytes)
    return output_path
