"""BILA XML envelope generation for Modelo 349.

The .349 file format uses a pseudo-XML envelope wrapping
fixed-width records. We use string templates rather than
XML libraries to match BILA's exact formatting.
"""

import hashlib
from datetime import datetime

from yabilabb.models import Declaration
from yabilabb.records import build_all_records

CRLF = "\r\n"


def _cmp(field_id: str, value: str = "") -> str:
    """Build a CMP tag."""
    if value:
        return f"<CMP ID='{field_id}' IMP='S' PRC='S'>{value}</CMP>"
    return f"<CMP ID='{field_id}' IMP='S' PRC='S' />"


def _format_amount(amount_cents: int) -> str:
    """Format amount as Spanish decimal string (e.g., '53.763,11')."""
    euros = amount_cents // 100
    cents = amount_cents % 100
    # Format with dots as thousands separator
    euro_str = f"{euros:,}".replace(",", ".")
    return f"{euro_str},{cents:02d}"


def _build_rc_section(datos_hash: str) -> str:
    """Build the <RC> receipt control section."""
    lines = [
        "<RC>",
        f"<HASH>{datos_hash}</HASH>",
        "<NENVIO />",
        "<FRECP />",
        "<HRECP />",
        "<FPROC />",
        "<NIFP />",
        "<DISP />",
        "<NOMP />",
        "<IDIOMA />",
        "</RC>",
    ]
    return CRLF.join(lines)


def _build_r0_section(decl: Declaration, creation_dt: datetime) -> str:
    """Build the <R0> metadata section using BILA-compatible values."""
    meta = decl.bila_metadata
    period_val = decl.period
    if period_val.endswith("T"):
        period_val = period_val[0]
    lines = [
        "<R0>",
        "<PROC>H</PROC>",
        f"<EJER>{decl.exercise_year}</EJER>",
        "<MOD>349</MOD>",
        f"<PERIODO>{period_val}</PERIODO>",
        f"<FCREAC>{creation_dt.strftime('%Y%m%d')}</FCREAC>",
        f"<HCREAC>{creation_dt.strftime('%H%M%S')}</HCREAC>",
        f"<ORIGEN>{meta.origen}</ORIGEN>",
        "<LEUSK />",
        "<LCAST />",
        f"<VERSION>{meta.version}</VERSION>",
        f"<VER_PREIMP_ORIG>{meta.ver_preimp_orig}</VER_PREIMP_ORIG>",
        "<ENTORNO>P</ENTORNO>",
        "<ORIGEN_DECLARACION>PL</ORIGEN_DECLARACION>",
        "<SISTEMA_OPERATIVO>W</SISTEMA_OPERATIVO>",
        f"<VERSION_PLATAFORMA>{meta.version_plataforma}</VERSION_PLATAFORMA>",
        "</R0>",
    ]
    return CRLF.join(lines)


def _build_rd_section(decl: Declaration) -> str:
    """Build the <RD> declaration data section with CMP fields."""
    from yabilabb.records import _amount_cents

    total_cents = _amount_cents(decl.total_amount)
    rect_cents = _amount_cents(decl.total_rectified_amount)

    cmp_fields = [
        _cmp("NIFD", decl.declarant.nif),
        _cmp("DISD"),
        _cmp("NOMD", decl.declarant.name.upper()),
        _cmp("CODCALLE"),
        _cmp("DOMI"),
        _cmp("NUMCASA"),
        _cmp("ELEMS"),
        _cmp("TELEFONO"),
        _cmp("MUNICIPIO"),
        _cmp("CODPOSTAL"),
        _cmp("PROVINCIA"),
        _cmp("NIFR"),
        _cmp("DISR"),
        _cmp("NOMR"),
        _cmp("EMAILR"),
        _cmp("CODCALLER"),
        _cmp("DOMIR"),
        _cmp("NUMCASAR"),
        _cmp("ELEMR"),
        _cmp("TELEFONOR"),
        _cmp("MUNICIPIOR"),
        _cmp("CODPOSTALR"),
        _cmp("PROVINCIAR"),
        _cmp("NIFC"),
        _cmp("NOMC", (decl.declarant.contact_name or decl.declarant.name).upper()),
        _cmp("TELEFONOC", decl.declarant.phone),
        _cmp("EMAILC", decl.declarant.email.upper() if decl.declarant.email else ""),
        _cmp("SUSTITUTIVA", "X" if decl.substitutive else ""),
        _cmp("NUM001", str(decl.num_operators) if decl.num_operators else ""),
        _cmp("PART002", _format_amount(total_cents) if total_cents else ""),
        _cmp("NUM003", str(decl.num_rectifications) if decl.num_rectifications else ""),
        _cmp("PART004", _format_amount(rect_cents) if rect_cents else ""),
        _cmp("NUM005"),
        _cmp("NUM006"),
        _cmp("CAMBIOPERIODO"),
        _cmp("SELLOHOJA", decl.bila_metadata.sellohoja),
        _cmp("IDIOMA", decl.idioma),
        _cmp("PRESIND", "X"),
        _cmp("PRESPRESENT"),
        _cmp("PRESDECLAR"),
        _cmp("CODENTIDAD"),
        _cmp("SUCURSAL"),
        _cmp("DC"),
        _cmp("CUENTA"),
        _cmp("FP", "3"),
        _cmp("RDO", "5"),
        _cmp("IMPORTETOTAL", "0,00"),
    ]

    lines = [
        "<RD NUMERO='1'>",
        "<DECLAR NAME='1'>",
        "<RI>",
        "<RHOST />",
        "<SELLO />",
        "<SECUENCIA />",
        "</RI>",
        "<RP>",
        *cmp_fields,
        "</RP>",
        "</DECLAR>",
        "</RD>",
    ]
    return CRLF.join(lines)


def _build_datos_section(records: list[str]) -> str:
    """Build the <DATOS> section with SUBREG-wrapped records."""
    lines = ["<DATOS>", "<REG NAME='1'>"]
    for i, record in enumerate(records, start=1):
        lines.append(f"<SUBREG ORDEN='{i}'>{record}</SUBREG>")
    lines.append("</REG>")
    lines.append("</DATOS>")
    return CRLF.join(lines)


def build_envelope(
    decl: Declaration,
    creation_dt: datetime | None = None,
) -> bytes:
    """Build the complete ENVIO XML document as bytes (ISO-8859-1, CRLF).

    When re-exporting an imported BILA file, preserves the original
    HASH and creation timestamp to produce a byte-identical file
    that BFA will accept.
    """
    meta = decl.bila_metadata

    # Use preserved creation timestamp if available, otherwise current
    if meta.fcreac and meta.hcreac:
        creation_dt = datetime.strptime(
            f"{meta.fcreac}{meta.hcreac}", "%Y%m%d%H%M%S"
        )
    elif creation_dt is None:
        creation_dt = datetime.now()

    records = build_all_records(decl, creation_dt.date())
    datos_section = _build_datos_section(records)

    # Use preserved IMPRESOS or empty
    impresos = meta.impresos if meta.impresos else f"<IMPRESOS>{CRLF}</IMPRESOS>"

    # Build the body (everything between </RC> and </ENVIO>)
    r0_section = _build_r0_section(decl, creation_dt)
    rd_section = _build_rd_section(decl)
    body = CRLF.join([r0_section, rd_section, datos_section, impresos])

    # Compute BILA hash: salted MD5 of body content
    # Salt = "BIZKAIKO FORU ALDUNDIA" padded to 64 chars
    # Reverse-engineered from net.bizkaia.bila.n4li.utils.MD5
    if meta.hash:
        datos_hash = meta.hash
    else:
        salt = "BIZKAIKO FORU ALDUNDIA".ljust(64)
        hash_input = (salt + body).encode("iso-8859-1")
        datos_hash = hashlib.md5(hash_input).hexdigest().upper()

    rc_section = _build_rc_section(datos_hash)

    sections = [
        "<ENVIO>",
        rc_section,
        body,
        "</ENVIO>",
    ]
    content = CRLF.join(sections)
    return content.encode("iso-8859-1")
