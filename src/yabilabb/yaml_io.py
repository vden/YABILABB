"""YAML input/output for declarations."""

from decimal import Decimal
from pathlib import Path

import yaml

from yabilabb.models import Declaration, Declarant, Operator, Rectification, BilaMetadata


def load_declaration(path: Path) -> Declaration:
    """Load a Declaration from a YAML file."""
    data = yaml.safe_load(path.read_text(encoding="utf-8"))

    declarant = Declarant(**data["declarant"])

    operators = []
    for op in data.get("operators", []):
        operators.append(Operator(
            country_code=op["country"],
            nif=str(op["nif"]),
            name=op["name"],
            operation_key=op["key"],
            amount=Decimal(str(op["amount"])),
            substitute_country=op.get("substitute_country", ""),
            substitute_nif=str(op.get("substitute_nif", "")),
            substitute_name=op.get("substitute_name", ""),
        ))

    rectifications = []
    for r in data.get("rectifications", []):
        rectifications.append(Rectification(
            country_code=r["country"],
            nif=str(r["nif"]),
            name=r["name"],
            operation_key=r["key"],
            rectified_year=r["rectified_year"],
            rectified_period=r["rectified_period"],
            rectified_amount=Decimal(str(r["rectified_amount"])),
            previous_amount=Decimal(str(r["previous_amount"])),
            substitute_country=r.get("substitute_country", ""),
            substitute_nif=str(r.get("substitute_nif", "")),
            substitute_name=r.get("substitute_name", ""),
        ))

    bila_meta = BilaMetadata()
    if "bila_metadata" in data:
        m = data["bila_metadata"]
        bila_meta = BilaMetadata(
            origen=m.get("origen", "YBM34920"),
            version=m.get("version", "510104"),
            ver_preimp_orig=m.get("ver_preimp_orig", "V1.1.4 1-2020"),
            version_plataforma=m.get("version_plataforma", "010161"),
            sellohoja=m.get("sellohoja", ""),
            impresos=m.get("impresos", ""),
            record_tail=m.get("record_tail", ""),
            hash=m.get("hash", ""),
            fcreac=m.get("fcreac", ""),
            hcreac=m.get("hcreac", ""),
        )

    return Declaration(
        exercise_year=data["exercise_year"],
        period=str(data["period"]),
        declarant=declarant,
        operators=operators,
        rectifications=rectifications,
        substitutive=data.get("substitutive", False),
        idioma=data.get("idioma", "C"),
        bila_metadata=bila_meta,
    )


def save_declaration(decl: Declaration, path: Path) -> None:
    """Save a Declaration to a YAML file."""
    data = {
        "exercise_year": decl.exercise_year,
        "period": decl.period,
        "declarant": {
            "nif": decl.declarant.nif,
            "name": decl.declarant.name,
            "phone": decl.declarant.phone,
            "contact_name": decl.declarant.contact_name,
            "email": decl.declarant.email,
        },
    }

    if decl.operators:
        data["operators"] = [
            {
                "country": op.country_code,
                "nif": op.nif,
                "name": op.name,
                "key": op.operation_key,
                "amount": float(op.amount),
                **({"substitute_country": op.substitute_country} if op.substitute_country else {}),
                **({"substitute_nif": op.substitute_nif} if op.substitute_nif else {}),
                **({"substitute_name": op.substitute_name} if op.substitute_name else {}),
            }
            for op in decl.operators
        ]

    if decl.rectifications:
        data["rectifications"] = [
            {
                "country": r.country_code,
                "nif": r.nif,
                "name": r.name,
                "key": r.operation_key,
                "rectified_year": r.rectified_year,
                "rectified_period": r.rectified_period,
                "rectified_amount": float(r.rectified_amount),
                "previous_amount": float(r.previous_amount),
            }
            for r in decl.rectifications
        ]

    if decl.substitutive:
        data["substitutive"] = True
    if decl.idioma != "C":
        data["idioma"] = decl.idioma

    # Always preserve BILA metadata for re-export compatibility
    meta = decl.bila_metadata
    meta_dict = {
        "origen": meta.origen,
        "version": meta.version,
        "ver_preimp_orig": meta.ver_preimp_orig,
        "version_plataforma": meta.version_plataforma,
    }
    if meta.sellohoja:
        meta_dict["sellohoja"] = meta.sellohoja
    if meta.impresos:
        meta_dict["impresos"] = meta.impresos
    if meta.record_tail and meta.record_tail.strip():
        meta_dict["record_tail"] = meta.record_tail
    if meta.hash:
        meta_dict["hash"] = meta.hash
    if meta.fcreac:
        meta_dict["fcreac"] = meta.fcreac
    if meta.hcreac:
        meta_dict["hcreac"] = meta.hcreac
    data["bila_metadata"] = meta_dict

    path.write_text(
        yaml.dump(data, allow_unicode=True, default_flow_style=False, sort_keys=False),
        encoding="utf-8",
    )
