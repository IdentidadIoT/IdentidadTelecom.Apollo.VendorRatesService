"""
Rutas API para procesamiento de archivos de vendors
Endpoints para carga y gestión de tarifas de vendors (Belgacom, Qxtel, etc.)
"""
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session

from requests import OBRProcessResponse
from core.auth import verify_user_has_obr_permission, TokenData
from dependencies import get_db, SessionLocal
from core.obr_service import OBRService
from core.vendor_registry import find_vendor_by_name, get_supported_vendors
from core.logging import logger
import tempfile
import os
import threading
import asyncio


router = APIRouter(
    prefix="/api/vendorRates",
    tags=["Vendor Rates"]
)


def _process_vendor_file_background(
    process_method_name: str,
    temp_file_path: str,
    file_name: str,
    user_email: str
):
    """
    Procesa archivo en THREAD separado (igual que Task.Run en C#)
    """
    db = SessionLocal()
    try:
        # Leer archivo
        with open(temp_file_path, 'rb') as f:
            file_content = f.read()

        # Procesar (ejecutar async en nuevo event loop)
        obr_service = OBRService(db)
        process_method = getattr(obr_service, process_method_name)

        # Crear event loop para este thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(process_method(
            file_content=file_content,
            file_name=file_name,
            user_email=user_email
        ))
        loop.close()
    except Exception as e:
        logger.error(f"Error en procesamiento background: {e}", exc_info=True)
    finally:
        db.close()
        # Limpiar archivo temporal
        try:
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)
        except:
            pass


def _process_qxtel_background(
    temp_file_one_path: str,
    temp_file_two_path: str,
    temp_file_three_path: str,
    file_one_name: str,
    user_email: str
):
    """
    Procesa archivos Qxtel en THREAD separado (igual que Task.Run en C#)
    """
    db = SessionLocal()
    try:
        # Leer archivos
        with open(temp_file_one_path, 'rb') as f:
            file_one_content = f.read()
        with open(temp_file_two_path, 'rb') as f:
            file_two_content = f.read()
        with open(temp_file_three_path, 'rb') as f:
            file_three_content = f.read()

        # Procesar (ejecutar async en nuevo event loop)
        obr_service = OBRService(db)

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(obr_service.process_qxtel_file(
            file_one_content=file_one_content,
            file_two_content=file_two_content,
            file_three_content=file_three_content,
            file_one_name=file_one_name,
            user_email=user_email
        ))
        loop.close()
    except Exception as e:
        logger.error(f"Error en procesamiento Qxtel background: {e}", exc_info=True)
    finally:
        db.close()
        # Limpiar archivos temporales
        try:
            for path in [temp_file_one_path, temp_file_two_path, temp_file_three_path]:
                if os.path.exists(path):
                    os.remove(path)
        except:
            pass


@router.post("/fileObrComparison", response_model=OBRProcessResponse)
async def file_obr_comparison(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    vendor_name: str = Form(...),
    user_email: str = Form(...),
    current_user: TokenData = Depends(verify_user_has_obr_permission)
):
    """
    Comparación de tarifas OBR del vendor vs Mera (switches)
    Compatible con el endpoint del backend .NET: /api/ProcessRatesByCustomer/PostVendorOBRFileDirect

    Proceso:
    1. Lee archivo Excel con tarifas del vendor
    2. Compara contra OBR Master Data
    3. Compara contra configuración actual en Mera
    4. Genera CSV con diferencias (ADD/UPDATE/CLOSE)
    5. Envía reporte por email

    Soporta vendors: Belgacom Platinum, Sunrise, etc.

    Args:
        file: Archivo Excel del vendor
        vendor_name: Nombre del vendor (ej: "Belgacom Platinum", "Sunrise")
        user_email: Email del usuario para recibir reporte CSV
        current_user: Usuario autenticado (inyectado)
        db: Sesión de base de datos (inyectada)

    Returns:
        OBRProcessResponse: Respuesta inmediata (fire-and-forget)
    """
    logger.info(f"[OBR COMPARISON] Vendor: {vendor_name}, User: {user_email}")

    try:
        # Validar que el archivo sea Excel
        if not file.filename.endswith(('.xlsx', '.xls')):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El archivo debe ser un Excel (.xlsx o .xls)"
            )

        # Buscar vendor en el registro
        vendor_config = find_vendor_by_name(vendor_name)

        if not vendor_config:
            supported = ", ".join(get_supported_vendors())
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Vendor '{vendor_name}' no está soportado. Vendors disponibles: {supported}"
            )

        # Validar que no sea Qxtel
        if vendor_config["file_requirement"]["type"] == "multiple":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Vendor '{vendor_config['display_name']}' requiere el endpoint /fileObrComparisonQxtel (3 archivos)"
            )

        # Obtener método de procesamiento
        process_method_name = vendor_config.get("process_method_name")
        if not process_method_name:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Vendor '{vendor_config['display_name']}' no tiene método de procesamiento configurado"
            )

        # ===== GUARDAR ARCHIVO TEMPORALMENTE (COMO C#) =====
        # Igual que C#: file.CopyToAsync(stream)
        temp_fd, temp_file_path = tempfile.mkstemp(suffix=os.path.splitext(file.filename)[1])
        try:
            with os.fdopen(temp_fd, 'wb') as tmp:
                # Streaming por chunks (rápido)
                while chunk := await file.read(1024 * 1024):  # 1MB chunks
                    tmp.write(chunk)
        except:
            os.remove(temp_file_path)
            raise

        # ===== EJECUTAR EN THREAD SEPARADO (COMO Task.Run EN C#) =====
        thread = threading.Thread(
            target=_process_vendor_file_background,
            args=(process_method_name, temp_file_path, file.filename, user_email),
            daemon=True
        )
        thread.start()

        logger.info(f"[OBR COMPARISON] Procesamiento en thread background iniciado para {vendor_name}")

        # ===== RESPONDER INMEDIATAMENTE =====
        return OBRProcessResponse(
            message="The vendor rates request was created successfully",
            vendor_name=vendor_name,
            user=user_email,
            status="processing"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error en upload de vendor rates: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error procesando archivo: {str(e)}"
        )


@router.post("/fileObrComparisonQxtel", response_model=OBRProcessResponse)
async def file_obr_comparison_qxtel(
    background_tasks: BackgroundTasks,
    file_one: UploadFile = File(..., description="Price List file"),
    file_two: UploadFile = File(..., description="New Price file"),
    file_three: UploadFile = File(..., description="Origin Codes file"),
    vendor_name: str = Form(...),
    user_email: str = Form(...),
    current_user: TokenData = Depends(verify_user_has_obr_permission)
):
    """
    Comparación de tarifas OBR de Qxtel vs Mera (switches)
    Compatible con el endpoint del backend .NET: /api/ProcessRatesByCustomer/PostVendorQxtelOBRFileDirect

    Qxtel requiere 3 archivos Excel:
    1. file_one: Price List (lista de precios por destino)
    2. file_two: New Price (precios nuevos/actualizados)
    3. file_three: Origin Codes (códigos de origen)

    Args:
        file_one: Archivo Excel Price List
        file_two: Archivo Excel New Price
        file_three: Archivo Excel Origin Codes
        vendor_name: Nombre del vendor (debe contener "Qxtel")
        user_email: Email del usuario para recibir reporte CSV
        current_user: Usuario autenticado (inyectado)
        db: Sesión de base de datos (inyectada)

    Returns:
        OBRProcessResponse: Respuesta inmediata (fire-and-forget)
    """
    logger.info(f"[OBR COMPARISON QXTEL] Vendor: {vendor_name}, User: {user_email}")

    try:
        # Validar que todos los archivos sean Excel
        for file in [file_one, file_two, file_three]:
            if not file.filename.endswith(('.xlsx', '.xls')):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"El archivo {file.filename} debe ser un Excel (.xlsx o .xls)"
                )

        # Validar vendor Qxtel
        vendor_name_upper = vendor_name.upper()
        if "QXTEL" not in vendor_name_upper:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Vendor '{vendor_name}' no es Qxtel. Use el endpoint /fileObrComparison para otros vendors"
            )

        # ===== GUARDAR ARCHIVOS TEMPORALMENTE (COMO C#) =====
        temp_paths = []
        try:
            for upload_file in [file_one, file_two, file_three]:
                temp_fd, temp_path = tempfile.mkstemp(suffix=os.path.splitext(upload_file.filename)[1])
                with os.fdopen(temp_fd, 'wb') as tmp:
                    while chunk := await upload_file.read(1024 * 1024):
                        tmp.write(chunk)
                temp_paths.append(temp_path)
        except:
            # Limpiar si falla
            for p in temp_paths:
                if os.path.exists(p):
                    os.remove(p)
            raise

        # ===== EJECUTAR EN THREAD SEPARADO (COMO Task.Run EN C#) =====
        thread = threading.Thread(
            target=_process_qxtel_background,
            args=(temp_paths[0], temp_paths[1], temp_paths[2], file_one.filename, user_email),
            daemon=True
        )
        thread.start()

        logger.info(f"[OBR COMPARISON QXTEL] Procesamiento en thread background iniciado para {vendor_name}")

        # ===== RESPONDER INMEDIATAMENTE =====
        return OBRProcessResponse(
            message="The vendor rates request was created successfully",
            vendor_name=vendor_name,
            user=user_email,
            status="processing"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error en upload de Qxtel rates: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error procesando archivos Qxtel: {str(e)}"
        )


@router.get("/health")
async def health_check():
    """
    Health check endpoint
    Útil para monitoreo y balanceadores de carga
    """
    return {
        "status": "healthy",
        "service": "VendorRatesService",
        "version": "1.0.0"
    }
