"""
Modelos de request (DTOs de entrada)
"""
from pydantic import BaseModel, Field
from typing import Optional


class UploadFileVendorRequest(BaseModel):
    """
    DTO para carga de archivo OBR de vendor
    Compatible con UploadFileVendorDto del backend .NET
    """
    vendor_name: str = Field(..., description="Nombre del proveedor (ej: Belgacom Platinum)")
    user: str = Field(..., description="Usuario que realiza la carga")
    file_content: bytes = Field(..., description="Contenido del archivo Excel en bytes")
    file_name: str = Field(..., description="Nombre del archivo original")

    class Config:
        json_schema_extra = {
            "example": {
                "vendor_name": "Belgacom Platinum",
                "user": "admin@company.com",
                "file_name": "belgacom_rates_2024.xlsx"
            }
        }


class OBRProcessResponse(BaseModel):
    """Respuesta estándar para inicio de procesamiento OBR"""
    message: str = "The OBR Request was created successfully"
    vendor_name: str
    user: str
    status: str = "processing"

    class Config:
        json_schema_extra = {
            "example": {
                "message": "The OBR Request was created successfully",
                "vendor_name": "Belgacom Platinum",
                "user": "admin@company.com",
                "status": "processing"
            }
        }
