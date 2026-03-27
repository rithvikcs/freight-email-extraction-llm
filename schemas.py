"""Pydantic models for email extraction output validation."""

from typing import Optional
from pydantic import BaseModel, Field


class ShipmentExtraction(BaseModel):
    """Schema for extracted shipment data from an email."""

    id: str = Field(..., description="Email ID")
    product_line: Optional[str] = Field(
        None, description="pl_sea_import_lcl or pl_sea_export_lcl"
    )
    origin_port_code: Optional[str] = Field(None, description="5-letter UN/LOCODE")
    origin_port_name: Optional[str] = Field(None, description="Port name from reference")
    destination_port_code: Optional[str] = Field(None, description="5-letter UN/LOCODE")
    destination_port_name: Optional[str] = Field(None, description="Port name from reference")
    incoterm: Optional[str] = Field(
        None,
        description="FOB, CIF, CFR, EXW, DDP, DAP, FCA, CPT, CIP, DPU",
    )
    cargo_weight_kg: Optional[float] = Field(
        None, description="Weight in kg, rounded to 2 decimals"
    )
    cargo_cbm: Optional[float] = Field(None, description="CBM, rounded to 2 decimals")
    is_dangerous: bool = Field(False, description="Dangerous goods flag")

    class Config:
        json_schema_extra = {
            "example": {
                "id": "EMAIL_001",
                "product_line": "pl_sea_import_lcl",
                "origin_port_code": "HKHKG",
                "origin_port_name": "Hong Kong",
                "destination_port_code": "INMAA",
                "destination_port_name": "Chennai",
                "incoterm": "FOB",
                "cargo_weight_kg": None,
                "cargo_cbm": 5.0,
                "is_dangerous": False,
            }
        }
