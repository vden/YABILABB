"""Pydantic data models for Modelo 349 declarations."""

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, field_validator

OperationKey = Literal["E", "M", "H", "A", "T", "S", "I", "R", "D", "C"]

PERIOD_CODES = {
    "01", "02", "03", "04", "05", "06",
    "07", "08", "09", "10", "11", "12",
    "1T", "2T", "3T", "4T", "0A",
}


class Declarant(BaseModel):
    """The person/entity filing the declaration."""

    nif: str
    name: str
    phone: str = ""
    contact_name: str = ""
    email: str = ""

    @field_validator("name", "contact_name")
    @classmethod
    def uppercase_name(cls, v: str) -> str:
        return v.upper()

    @field_validator("nif")
    @classmethod
    def validate_nif(cls, v: str) -> str:
        v = v.strip().upper()
        if len(v) > 9:
            raise ValueError(f"NIF must be at most 9 characters, got {len(v)}")
        return v


class Operator(BaseModel):
    """An EU intra-community operator (Type 2 record)."""

    country_code: str
    nif: str
    name: str
    operation_key: OperationKey
    amount: Decimal

    # For clave C only:
    substitute_country: str = ""
    substitute_nif: str = ""
    substitute_name: str = ""

    @field_validator("country_code", "substitute_country")
    @classmethod
    def uppercase_country(cls, v: str) -> str:
        return v.strip().upper()

    @field_validator("name", "substitute_name")
    @classmethod
    def uppercase_name(cls, v: str) -> str:
        return v.upper()

    @field_validator("nif", "substitute_nif")
    @classmethod
    def strip_nif(cls, v: str) -> str:
        return v.strip()

    @field_validator("amount")
    @classmethod
    def positive_amount(cls, v: Decimal) -> Decimal:
        if v < 0:
            raise ValueError("Amount must be non-negative")
        return v


class Rectification(BaseModel):
    """A rectification of a previously declared operation."""

    country_code: str
    nif: str
    name: str
    operation_key: OperationKey
    rectified_year: int
    rectified_period: str
    rectified_amount: Decimal
    previous_amount: Decimal

    # For clave C only:
    substitute_country: str = ""
    substitute_nif: str = ""
    substitute_name: str = ""

    @field_validator("country_code", "substitute_country")
    @classmethod
    def uppercase_country(cls, v: str) -> str:
        return v.strip().upper()

    @field_validator("name", "substitute_name")
    @classmethod
    def uppercase_name(cls, v: str) -> str:
        return v.upper()

    @field_validator("rectified_period")
    @classmethod
    def validate_period(cls, v: str) -> str:
        if v not in PERIOD_CODES:
            raise ValueError(f"Invalid period: {v}")
        return v


class Declaration(BaseModel):
    """A complete Modelo 349 declaration."""

    exercise_year: int
    period: str
    declarant: Declarant
    operators: list[Operator] = []
    rectifications: list[Rectification] = []
    substitutive: bool = False
    idioma: str = "C"

    @field_validator("period")
    @classmethod
    def validate_period(cls, v: str) -> str:
        if v not in PERIOD_CODES:
            raise ValueError(f"Invalid period: {v}")
        return v

    @property
    def num_operators(self) -> int:
        return len(self.operators)

    @property
    def num_rectifications(self) -> int:
        return len(self.rectifications)

    @property
    def total_amount(self) -> Decimal:
        return sum((op.amount for op in self.operators), Decimal("0"))

    @property
    def total_rectified_amount(self) -> Decimal:
        return sum((r.rectified_amount for r in self.rectifications), Decimal("0"))
