from dataclasses import dataclass
from datetime import date
from typing import Optional


@dataclass(frozen=True)
class Principal:
    name: str
    role: str
    org_id: Optional[str]


@dataclass(frozen=True)
class Invoice:
    number: str
    org_id: str
    issued_on: date
    archived: bool = False
