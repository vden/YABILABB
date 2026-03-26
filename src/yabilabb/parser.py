"""Parse existing .349 files back to Declaration models."""

import re
import zipfile
from decimal import Decimal
from pathlib import Path

from yabilabb.models import Declaration, Declarant, Operator, Rectification, BilaMetadata


def _extract_tmp(path: Path) -> str:
    """Extract the .tmp file content from a .349 ZIP."""
    with zipfile.ZipFile(path, "r") as zf:
        names = zf.namelist()
        tmp_name = next((n for n in names if n.endswith(".tmp")), names[0])
        return zf.read(tmp_name).decode("iso-8859-1")


def _parse_cmp_fields(content: str) -> dict[str, str]:
    """Extract CMP field values from the XML."""
    fields = {}
    for m in re.finditer(r"<CMP ID='(\w+)'[^>]*>([^<]*)</CMP>", content):
        fields[m.group(1)] = m.group(2)
    for m in re.finditer(r"<CMP ID='(\w+)'[^/]*/\s*>", content):
        if m.group(1) not in fields:
            fields[m.group(1)] = ""
    return fields


def _extract_xml_tag(content: str, tag: str) -> str:
    """Extract the text content of an XML tag."""
    m = re.search(rf"<{tag}>([^<]*)</{tag}>", content)
    return m.group(1) if m else ""


def _extract_impresos(content: str) -> str:
    """Extract the raw IMPRESOS section."""
    m = re.search(r"(<IMPRESOS>.*?</IMPRESOS>)", content, re.DOTALL)
    return m.group(1) if m else ""


def _parse_type1(record: str) -> dict:
    """Parse a Type 1 record into a dict."""
    return {
        "exercise_year": int(record[4:8]),
        "nif": record[8:17].strip(),
        "name": record[17:57].strip(),
        "phone": record[58:67].strip(),
        "contact_name": record[67:107].strip(),
        "period": record[135:137].strip(),
        "num_operators": int(record[137:146]),
        "total_cents": int(record[146:161]),
        "num_rectifications": int(record[161:170]),
        "rect_cents": int(record[170:185]),
        "substitutive": record[121] == "S",
        "record_tail": record[399:500],
    }


def _parse_type2_operator(record: str) -> Operator:
    """Parse a Type 2 operator record."""
    amount_cents = int(record[133:146])
    return Operator(
        country_code=record[75:77].strip(),
        nif=record[77:92].strip(),
        name=record[92:132].strip(),
        operation_key=record[132],
        amount=Decimal(amount_cents) / 100,
        substitute_country=record[178:180].strip(),
        substitute_nif=record[180:195].strip(),
        substitute_name=record[195:235].strip(),
    )


def _parse_type2_rectification(record: str) -> Rectification:
    """Parse a Type 2 rectification record."""
    rect_cents = int(record[152:165])
    prev_cents = int(record[165:178])
    return Rectification(
        country_code=record[75:77].strip(),
        nif=record[77:92].strip(),
        name=record[92:132].strip(),
        operation_key=record[132],
        rectified_year=int(record[146:150]),
        rectified_period=record[150:152].strip(),
        rectified_amount=Decimal(rect_cents) / 100,
        previous_amount=Decimal(prev_cents) / 100,
        substitute_country=record[178:180].strip(),
        substitute_nif=record[180:195].strip(),
        substitute_name=record[195:235].strip(),
    )


def _is_rectification(record: str) -> bool:
    """A Type 2 record is a rectification if pos 134-146 is blank and 147-150 has a year."""
    return record[133:146].strip() == "" and record[146:150].strip() != ""


def parse_349(path: Path) -> Declaration:
    """Parse a .349 file into a Declaration model."""
    content = _extract_tmp(path)

    # Extract R0 metadata and RC hash
    bila_meta = BilaMetadata(
        origen=_extract_xml_tag(content, "ORIGEN") or "YBM34920",
        version=_extract_xml_tag(content, "VERSION") or "510104",
        ver_preimp_orig=_extract_xml_tag(content, "VER_PREIMP_ORIG") or "V1.1.4 1-2020",
        version_plataforma=_extract_xml_tag(content, "VERSION_PLATAFORMA") or "010161",
        impresos=_extract_impresos(content),
        hash=_extract_xml_tag(content, "HASH"),
        fcreac=_extract_xml_tag(content, "FCREAC"),
        hcreac=_extract_xml_tag(content, "HCREAC"),
    )

    # Extract DATOS section records
    datos_match = re.search(r"<DATOS>(.*?)</DATOS>", content, re.DOTALL)
    if not datos_match:
        raise ValueError("No DATOS section found in file")

    subregs = re.findall(
        r"<SUBREG ORDEN='\d+'>(.*?)</SUBREG>",
        datos_match.group(1),
        re.DOTALL,
    )

    if not subregs:
        raise ValueError("No SUBREG records found")

    records = [s for s in subregs if len(s) == 500]

    type1 = records[0]
    if type1[0] != "1":
        raise ValueError(f"Expected Type 1 record, got type '{type1[0]}'")

    header = _parse_type1(type1)
    bila_meta.record_tail = header["record_tail"]

    cmp = _parse_cmp_fields(content)
    bila_meta.sellohoja = cmp.get("SELLOHOJA", "")

    operators = []
    rectifications = []

    for rec in records[1:]:
        if rec[0] != "2":
            continue
        if _is_rectification(rec):
            rectifications.append(_parse_type2_rectification(rec))
        else:
            operators.append(_parse_type2_operator(rec))

    return Declaration(
        exercise_year=header["exercise_year"],
        period=header["period"],
        declarant=Declarant(
            nif=header["nif"],
            name=header["name"],
            phone=header["phone"],
            contact_name=header["contact_name"],
            email=cmp.get("EMAILC", ""),
        ),
        operators=operators,
        rectifications=rectifications,
        substitutive=header["substitutive"],
        idioma=cmp.get("IDIOMA", "C"),
        bila_metadata=bila_meta,
    )
