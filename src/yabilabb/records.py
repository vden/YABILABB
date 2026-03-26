"""Fixed-width 500-character record generation for Modelo 349.

Per BOB 2020-03-11, Orden Foral 570/2020, Anexo II.
All records are exactly 500 characters, ISO-8859-1 encoding.
"""

from datetime import date, datetime
from decimal import Decimal

from yabilabb.models import Declaration, Operator, Rectification

RECORD_LEN = 500


def _alpha(value: str, width: int) -> str:
    """Left-aligned, space-padded, uppercase, no accents."""
    return value.upper().ljust(width)[:width]


def _numeric(value: int, width: int) -> str:
    """Right-aligned, zero-padded."""
    return str(value).zfill(width)[:width]


def _amount_cents(amount: Decimal) -> int:
    """Convert euro amount to integer cents."""
    return int(round(amount * 100))


def build_type1_record(
    decl: Declaration,
    creation_date: date | None = None,
) -> str:
    """Build the Type 1 (declarant) record, 500 chars.

    Field positions per BOB 2020 spec, 1-indexed.
    """
    if creation_date is None:
        creation_date = date.today()

    total_cents = _amount_cents(decl.total_amount)
    rect_cents = _amount_cents(decl.total_rectified_amount)

    parts = [
        "1",                                              # 1:     tipo
        "349",                                            # 2-4:   modelo
        _numeric(decl.exercise_year, 4),                  # 5-8:   ejercicio
        _alpha(decl.declarant.nif, 9),                    # 9-17:  NIF declarante
        _alpha(decl.declarant.name, 40),                  # 18-57: nombre
        "I",                                              # 58:    tipo soporte (I=Internet)
        _numeric(int(decl.declarant.phone or "0"), 9),    # 59-67: teléfono
        _alpha(decl.declarant.contact_name or decl.declarant.name, 40),  # 68-107
        _numeric(0, 13),                                  # 108-120: ceros
        " ",                                              # 121: blanco
        "S" if decl.substitutive else " ",                # 122: sustitutiva
        _numeric(0, 13),                                  # 123-135: ceros
        decl.period.ljust(2)[:2],                         # 136-137: período
        _numeric(decl.num_operators, 9),                  # 138-146: num operadores
        _numeric(total_cents, 15),                        # 147-161: importe
        _numeric(decl.num_rectifications, 9),             # 162-170: num rectificaciones
        _numeric(rect_cents, 15),                         # 171-185: importe rectificaciones
        " ",                                              # 186: cambio periodicidad
        " " * 204,                                        # 187-390: blancos
        " " * 9,                                          # 391-399: NIF representante
    ]
    # Positions 400-500: BILA metadata tail or blanks
    tail = decl.bila_metadata.record_tail if decl.bila_metadata.record_tail.strip() else ""
    if tail:
        parts.append(tail.ljust(101)[:101])
    else:
        # Generate BILA-compatible tail
        parts.append(
            " " * 23                                          # 400-422: blancos
            + "CKI"                                           # 423-425: app code
            + "21"                                            # 426-427: format
            + "S"                                             # 428: sign
            + "10100"                                         # 429-433: version
            + " " * 12                                        # 434-445: blancos
            + creation_date.strftime("%Y%m%d")                # 446-453: creation date
            + _alpha("INTERNET", 17)                          # 454-470: medium
            + "2020"                                          # 471-474: preimp year
            + " " * 26                                        # 475-500: blancos
        )
    record = "".join(parts)
    assert len(record) == RECORD_LEN, f"Type 1 record is {len(record)}, expected {RECORD_LEN}"
    return record


def build_type2_operator_record(
    decl: Declaration,
    op: Operator,
) -> str:
    """Build a Type 2 (operator) record, 500 chars."""
    amount_cents = _amount_cents(op.amount)

    parts = [
        "2",                                              # 1:     tipo
        "349",                                            # 2-4:   modelo
        _numeric(decl.exercise_year, 4),                  # 5-8:   ejercicio
        _alpha(decl.declarant.nif, 9),                    # 9-17:  NIF declarante
        " " * 58,                                         # 18-75: blancos
        _alpha(op.country_code, 2),                       # 76-77: código país
        _alpha(op.nif, 15),                               # 78-92: NIF operador
        _alpha(op.name, 40),                              # 93-132: nombre
        op.operation_key,                                 # 133:   clave operación
        _numeric(amount_cents, 13),                       # 134-146: base imponible
        " " * 32,                                         # 147-178: blancos
        _alpha(op.substitute_country, 2) if op.operation_key == "C" else "  ",   # 179-180
        _alpha(op.substitute_nif, 15) if op.operation_key == "C" else " " * 15,  # 181-195
        _alpha(op.substitute_name, 40) if op.operation_key == "C" else " " * 40, # 196-235
        " " * 265,                                        # 236-500: blancos
    ]
    record = "".join(parts)
    assert len(record) == RECORD_LEN, f"Type 2 operator record is {len(record)}, expected {RECORD_LEN}"
    return record


def build_type2_rectification_record(
    decl: Declaration,
    rect: Rectification,
) -> str:
    """Build a Type 2 (rectification) record, 500 chars."""
    rect_cents = _amount_cents(rect.rectified_amount)
    prev_cents = _amount_cents(rect.previous_amount)

    parts = [
        "2",                                              # 1:     tipo
        "349",                                            # 2-4:   modelo
        _numeric(decl.exercise_year, 4),                  # 5-8:   ejercicio
        _alpha(decl.declarant.nif, 9),                    # 9-17:  NIF declarante
        " " * 58,                                         # 18-75: blancos
        _alpha(rect.country_code, 2),                     # 76-77: código país
        _alpha(rect.nif, 15),                             # 78-92: NIF operador
        _alpha(rect.name, 40),                            # 93-132: nombre
        rect.operation_key,                               # 133:   clave operación
        " " * 13,                                         # 134-146: blancos
        _numeric(rect.rectified_year, 4),                 # 147-150: ejercicio corregido
        rect.rectified_period.ljust(2)[:2],               # 151-152: período corregido
        _numeric(rect_cents, 13),                         # 153-165: base rectificada
        _numeric(prev_cents, 13),                         # 166-178: base declarada anteriormente
        _alpha(rect.substitute_country, 2) if rect.operation_key == "C" else "  ",   # 179-180
        _alpha(rect.substitute_nif, 15) if rect.operation_key == "C" else " " * 15,  # 181-195
        _alpha(rect.substitute_name, 40) if rect.operation_key == "C" else " " * 40, # 196-235
        " " * 265,                                        # 236-500: blancos
    ]
    record = "".join(parts)
    assert len(record) == RECORD_LEN, f"Type 2 rect record is {len(record)}, expected {RECORD_LEN}"
    return record


def build_all_records(decl: Declaration, creation_date: date | None = None) -> list[str]:
    """Build all records for a declaration in presentation order."""
    records = [build_type1_record(decl, creation_date)]
    for op in decl.operators:
        records.append(build_type2_operator_record(decl, op))
    for rect in decl.rectifications:
        records.append(build_type2_rectification_record(decl, rect))
    return records
