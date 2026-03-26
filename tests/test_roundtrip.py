"""Roundtrip tests: parse -> regenerate -> compare, and YAML I/O."""

import re
from decimal import Decimal
from pathlib import Path

import pytest

from yabilabb.models import Declaration, Declarant, Operator
from yabilabb.parser import parse_349
from yabilabb.records import build_all_records, RECORD_LEN
from yabilabb.yaml_io import load_declaration, save_declaration
from yabilabb.writer import write_349

EXAMPLES_DIR = Path(__file__).parent.parent / "examples"
DATA_DIR = Path(__file__).parent.parent / "data"


def _find_example_349() -> Path | None:
    if not EXAMPLES_DIR.exists():
        return None
    files = list(EXAMPLES_DIR.glob("*.349"))
    return files[0] if files else None


def _find_example_tmp() -> Path | None:
    extracted = EXAMPLES_DIR / "extracted"
    if not extracted.exists():
        return None
    tmps = list(extracted.glob("*.tmp"))
    return tmps[0] if tmps else None


def _find_example_yaml() -> Path | None:
    if not DATA_DIR.exists():
        return None
    yamls = list(DATA_DIR.glob("*.yaml"))
    return yamls[0] if yamls else None


def _extract_datos_records(tmp_path: Path) -> list[str]:
    content = tmp_path.read_text(encoding="iso-8859-1")
    datos_match = re.search(r"<DATOS>(.*?)</DATOS>", content, re.DOTALL)
    subregs = re.findall(r"<SUBREG ORDEN='\d+'>(.*?)</SUBREG>", datos_match.group(1), re.DOTALL)
    return [s for s in subregs if len(s) == RECORD_LEN]


def _make_test_declaration() -> Declaration:
    """Synthetic declaration with fake data for standalone tests."""
    return Declaration(
        exercise_year=2025,
        period="2T",
        declarant=Declarant(
            nif="B12345678",
            name="EMPRESA EJEMPLO SL",
            phone="944000000",
            contact_name="GARCIA LOPEZ JUAN",
            email="test@example.com",
        ),
        operators=[
            Operator(
                country_code="DE",
                nif="123456789",
                name="DEUTSCHE FIRMA GMBH",
                operation_key="A",
                amount=Decimal("5000.00"),
            ),
            Operator(
                country_code="FR",
                nif="12345678901",
                name="SOCIETE FRANCAISE SARL",
                operation_key="S",
                amount=Decimal("3200.50"),
            ),
        ],
    )


# --- Standalone tests (no example files needed) ---

def test_yaml_roundtrip(tmp_path: Path):
    """Save and reload YAML with synthetic data."""
    decl = _make_test_declaration()
    yaml_path = tmp_path / "test.yaml"
    save_declaration(decl, yaml_path)
    decl2 = load_declaration(yaml_path)

    assert decl2.exercise_year == decl.exercise_year
    assert decl2.period == decl.period
    assert decl2.declarant.nif == decl.declarant.nif
    assert decl2.num_operators == decl.num_operators
    assert decl2.total_amount == decl.total_amount


def test_generate_and_parse_roundtrip(tmp_path: Path):
    """Generate a .349 file and parse it back."""
    decl = _make_test_declaration()
    output = tmp_path / "test.349"
    write_349(decl, output)

    assert output.exists()
    assert output.stat().st_size > 0

    decl2 = parse_349(output)
    assert decl2.exercise_year == decl.exercise_year
    assert decl2.period == decl.period
    assert decl2.declarant.nif == decl.declarant.nif
    assert decl2.num_operators == decl.num_operators
    assert decl2.total_amount == decl.total_amount


# --- Tests requiring local example files (examples/ is gitignored) ---

def test_parse_example():
    """Parse a BILA-generated .349 file."""
    path = _find_example_349()
    if path is None:
        pytest.skip("No .349 example files in examples/")

    decl = parse_349(path)
    assert decl.exercise_year > 2000
    assert decl.period in ("1T", "2T", "3T", "4T") or decl.period.isdigit()
    assert len(decl.declarant.nif) <= 9
    assert decl.num_operators > 0
    assert decl.total_amount > 0


def test_roundtrip_records():
    """Parse example, regenerate records, compare byte-for-byte."""
    path_349 = _find_example_349()
    path_tmp = _find_example_tmp()
    if path_349 is None or path_tmp is None:
        pytest.skip("No example files in examples/")

    decl = parse_349(path_349)
    our_records = build_all_records(decl)
    example_records = _extract_datos_records(path_tmp)

    assert len(our_records) == len(example_records)

    # Compare Type 2 records (should match exactly)
    for i in range(1, len(our_records)):
        assert our_records[i] == example_records[i], (
            f"Type 2 record {i} mismatch at pos "
            f"{next((j+1 for j in range(RECORD_LEN) if our_records[i][j] != example_records[i][j]), '?')}"
        )

    # Compare Type 1 record positions 1-399 (400-500 has BILA metadata)
    for pos in range(399):
        assert our_records[0][pos] == example_records[0][pos], (
            f"Type 1 mismatch at pos {pos+1}: "
            f"ours={repr(our_records[0][pos])}, example={repr(example_records[0][pos])}"
        )


def test_yaml_load_from_data():
    """Load declaration from data/ YAML if present."""
    path = _find_example_yaml()
    if path is None:
        pytest.skip("No YAML files in data/")

    decl = load_declaration(path)
    assert decl.exercise_year > 2000
    assert decl.num_operators > 0
