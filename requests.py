"""
Modelos de request (DTOs de entrada)
"""
from pydantic import BaseModel, Field
from typing import Optional, Union


class UploadFileVendorRequest(BaseModel):
    """
    DTO para carga de archivo OBR de vendor
    Compatible con UploadFileVendorDto del backend .NET
    """
    vendor_name: str = Field(..., alias="VendorName", description="Nombre del proveedor (ej: Belgacom Platinum)")
    user: str = Field(..., alias="User", description="Usuario que realiza la carga")
    file_content: Union[str, bytes] = Field(..., alias="File", description="Contenido del archivo Excel (base64 string o bytes)")
    max_line: Optional[int] = Field(None, alias="MaxLine", description="Número máximo de línea a procesar del Excel")

    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "VendorName": "Belgacom Platinum",
                "User": "admin@company.com",
                "File": "<base64_encoded_bytes>",
                "MaxLine": 10000
            }
        }


class UploadFileVendorQxtelRequest(BaseModel):
    """
    DTO para carga de archivos OBR de Qxtel (3 archivos)
    Compatible con UploadFileVendorQxtelDto del backend .NET
    """
    file_one: Union[str, bytes] = Field(..., alias="FileOne", description="Price List file (base64 string o bytes)")
    file_two: Union[str, bytes] = Field(..., alias="FileTwo", description="New Price file (base64 string o bytes)")
    file_three: Union[str, bytes] = Field(..., alias="FileThree", description="Origin Codes file (base64 string o bytes)")
    user: str = Field(..., alias="User", description="Usuario que realiza la carga")
    vendor_name: str = Field(..., alias="VendorName", description="Nombre del proveedor (debe contener 'Qxtel')")
    file_name: Optional[str] = Field(None, alias="FileName", description="Nombre del archivo principal")
    max_line: Optional[int] = Field(None, alias="MaxLine", description="Número máximo de línea a procesar")

    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "FileOne": "<base64_encoded_bytes>",
                "FileTwo": "<base64_encoded_bytes>",
                "FileThree": "<base64_encoded_bytes>",
                "User": "admin@company.com",
                "VendorName": "Qxtel",
                "FileName": "qxtel_rates.xlsx",
                "MaxLine": 10000
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
