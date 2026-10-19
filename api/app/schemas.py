"""Schémas d'entrée de l'API (validation stricte : première barrière contre les injections applicatives)."""
from decimal import Decimal
from pydantic import BaseModel, Field


class PaymentIn(BaseModel):
    to: str = Field(min_length=1, max_length=32, pattern=r"^[a-z0-9_]+$")
    amount: Decimal = Field(gt=0, le=10000, max_digits=12, decimal_places=2)
    label: str = Field(default="", max_length=64, pattern=r"^[\w .,'()\-]*$")
