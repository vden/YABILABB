"""Test fixed-width record generation."""

import re
from decimal import Decimal
from pathlib import Path

import pytest

from yabilabb.models import Declaration, Declarant, Operator
from yabilabb.records import (
    build_type1_record,
    build_type2_operator_record,
    build_all_records,
    RECORD_LEN,
)

EXAMPLE_PATH = Path(__file__).parent.parent / "examples" / "extracted"


def _find_example_tmp() -> Path | None:
    """Find the first .tmp file in examples/extracted/."""
    if not EXAMPLE_PATH.exists():
        return None
    tmps = list(EXAMPLE_PATH.glob("*.tmp"))
    return tmps[0] if tmps else None


def _extract_subregs(path: Path) -> dict[int, str]:
    """Extract SUBREG contents from the DATOS section of a .tmp file."""
    content = path.read_text(encoding="iso-8859-1")
    datos_match = re.search(r"<DATOS>(.*?)</DATOS>", content, re.DOTALL)
    assert datos_match, "No DATOS section found"
    datos = datos_match.group(1)
    subregs = re.findall(r"<SUBREG ORDEN='(\d+)'>(.*?)</SUBREG>", datos, re.DOTALL)
    return {int(orden): data for orden, data in subregs}


def _make_test_declaration() -> Declaration:
    """Build a synthetic test declaration with fake data."""
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


def test_record_lengths():
    decl = _make_test_declaration()
    records = build_all_records(decl)
    assert len(records) == 3  # 1 type1 + 2 type2
    for i, rec in enumerate(records):
        assert len(rec) == RECORD_LEN, f"Record {i} is {len(rec)} chars"


def test_type1_header_fields():
    decl = _make_test_declaration()
    rec = build_type1_record(decl)

    assert rec[0] == "1"                                       # tipo
    assert rec[1:4] == "349"                                   # modelo
    assert rec[4:8] == "2025"                                  # ejercicio
    assert rec[8:17] == "B12345678"                            # NIF
    assert rec[17:57].startswith("EMPRESA EJEMPLO SL")         # nombre
    assert rec[57] == "I"                                      # soporte
    assert rec[58:67] == "944000000"                           # telefono
    assert rec[67:107].startswith("GARCIA LOPEZ JUAN")         # contacto
    assert rec[107:120] == "0000000000000"                     # ceros
    assert rec[135:137] == "2T"                                # periodo
    assert rec[137:146] == "000000002"                         # num operadores
    assert rec[146:161] == "000000000820050"                   # importe (8200.50)
    assert rec[161:170] == "000000000"                         # num rectificaciones
    assert rec[170:185] == "000000000000000"                   # importe rectificaciones


def test_type2_operator_fields():
    decl = _make_test_declaration()
    rec = build_type2_operator_record(decl, decl.operators[0])

    assert rec[0] == "2"                                       # tipo
    assert rec[1:4] == "349"                                   # modelo
    assert rec[4:8] == "2025"                                  # ejercicio
    assert rec[8:17] == "B12345678"                            # NIF declarante
    assert rec[17:75] == " " * 58                              # blancos
    assert rec[75:77] == "DE"                                  # pais
    assert rec[77:92] == "123456789      "                     # NIF operador
    assert rec[92:132].startswith("DEUTSCHE FIRMA GMBH")       # nombre
    assert rec[132] == "A"                                     # clave
    assert rec[133:146] == "0000000500000"                     # base imponible (5000.00)


def test_total_amount():
    decl = _make_test_declaration()
    assert decl.total_amount == Decimal("8200.50")
    assert decl.num_operators == 2


# --- Tests that require BILA example files (examples/ is gitignored) ---

def _parse_declaration_from_example(tmp_path: Path) -> Declaration:
    """Parse a Declaration from an example .tmp file's SUBREG records."""
    from yabilabb.records import _alpha, _numeric
    subregs = _extract_subregs(tmp_path)
    rec1 = subregs[1]

    operators = []
    for i in range(2, max(subregs.keys()) + 1):
        rec = subregs.get(i)
        if rec is None or len(rec) != RECORD_LEN or rec[0] != "2":
            continue
        operators.append(Operator(
            country_code=rec[75:77].strip(),
            nif=rec[77:92].strip(),
            name=rec[92:132].strip(),
            operation_key=rec[132],
            amount=Decimal(int(rec[133:146])) / 100,
        ))

    return Declaration(
        exercise_year=int(rec1[4:8]),
        period=rec1[135:137].strip(),
        declarant=Declarant(
            nif=rec1[8:17].strip(),
            name=rec1[17:57].strip(),
            phone=rec1[58:67].strip(),
            contact_name=rec1[67:107].strip(),
        ),
        operators=operators,
    )


def test_type1_matches_example():
    """Compare our Type 1 record against BILA's, field by field."""
    tmp_path = _find_example_tmp()
    if tmp_path is None:
        pytest.skip("No example files in examples/extracted/")

    subregs = _extract_subregs(tmp_path)
    example = subregs[1]
    assert len(example) == RECORD_LEN

    decl = _parse_declaration_from_example(tmp_path)
    ours = build_type1_record(decl)

    # Compare positions 1-399 (official spec fields)
    # Positions 400-500 are "BLANCOS" per spec but BILA puts metadata there
    for pos in range(399):
        if ours[pos] != example[pos]:
            assert False, (
                f"Mismatch at position {pos + 1}: "
                f"ours={repr(ours[pos])}, example={repr(example[pos])}"
            )


def test_type2_matches_example():
    """Compare Type 2 records against BILA example."""
    tmp_path = _find_example_tmp()
    if tmp_path is None:
        pytest.skip("No example files in examples/extracted/")

    subregs = _extract_subregs(tmp_path)
    decl = _parse_declaration_from_example(tmp_path)

    for i, op in enumerate(decl.operators):
        example = subregs[i + 2]
        ours = build_type2_operator_record(decl, op)

        assert len(example) == RECORD_LEN, f"Example record {i+2} is {len(example)} chars"
        assert ours == example, (
            f"Type 2 record {i} mismatch at position: "
            f"{next((j+1 for j in range(RECORD_LEN) if ours[j] != example[j]), 'none')}"
        )
