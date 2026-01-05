"""
Rutas API para procesamiento de archivos de vendors
Endpoints para carga y gestión de tarifas de vendors (Belgacom, Qxtel, etc.)
"""
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session

from schemas import OBRProcessResponse, UploadFileVendorRequest, UploadFileVendorQxtelRequest
from core.auth import verify_token_dependency
from dependencies import get_db, SessionLocal
from core.obr_service import OBRService
from core.vendor_registry import find_vendor_by_name, get_supported_vendors
from core.logging import logger
import tempfile
import os
import threading
import asyncio
import base64


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
    request: UploadFileVendorRequest,
    background_tasks: BackgroundTasks,
    auth: str = Depends(verify_token_dependency)
):
    """
    Comparación de tarifas OBR del vendor vs Mera (switches)
    Compatible con el endpoint del backend .NET: /api/ProcessRatesByCustomer/PostVendorOBRFile

    Proceso:
    1. Lee archivo Excel con tarifas del vendor
    2. Compara contra OBR Master Data
    3. Compara contra configuración actual en Mera
    4. Genera CSV con diferencias (ADD/UPDATE/CLOSE)
    5. Envía reporte por email

    Soporta vendors: Belgacom Platinum, Sunrise, etc.

    Args:
        request: UploadFileVendorRequest con File (bytes), VendorName, User
        current_user: Usuario autenticado (inyectado)

    Returns:
        OBRProcessResponse: Respuesta inmediata (fire-and-forget)
    """
    vendor_name = request.vendor_name
    user_email = request.user

    logger.info(f"[OBR COMPARISON] Vendor: {vendor_name}, User: {user_email}")

    try:
        file_content = request.file_content

        if not vendor_name or not file_content:
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

        logger.info(f"[DEBUG] file_content type: {type(file_content)}, len: {len(file_content) if file_content else 0}")
        if file_content:
            logger.info(f"[DEBUG] first 50 chars: {str(file_content)[:50]}")

        temp_fd, temp_file_path = tempfile.mkstemp(suffix='.xlsx')
        try:
            with os.fdopen(temp_fd, 'wb') as tmp:
                if isinstance(file_content, str):
                    logger.info("[DEBUG] Decoding from base64 string")
                    file_bytes = base64.b64decode(file_content)
                else:
                    logger.info("[DEBUG] Using bytes directly")
                    file_bytes = file_content

                logger.info(f"[DEBUG] file_bytes len: {len(file_bytes)}, first 10 bytes: {file_bytes[:10]}")

                # Verificar magic bytes de ZIP/Excel (debe empezar con 'PK' = 0x50 0x4B)
                if len(file_bytes) >= 2:
                    magic_bytes = file_bytes[:2]
                    is_valid_zip = magic_bytes == b'PK'
                    logger.info(f"[DEBUG] Magic bytes: {magic_bytes.hex()} (Expected: 504b for ZIP/Excel) - Valid: {is_valid_zip}")
                    if not is_valid_zip:
                        logger.error(f"[DEBUG] ¡ARCHIVO NO ES ZIP! Magic bytes incorrectos. Archivo corrupto o mal codificado.")

                tmp.write(file_bytes)
        except Exception as e:
            logger.error(f"[DEBUG] Error writing file: {e}", exc_info=True)
            os.remove(temp_file_path)
            raise

        file_name = f"{vendor_name}_rates.xlsx"

        thread = threading.Thread(
            target=_process_vendor_file_background,
            args=(process_method_name, temp_file_path, file_name, user_email),
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
    request: UploadFileVendorQxtelRequest,
    background_tasks: BackgroundTasks,
    auth: str = Depends(verify_token_dependency)
):
    """
    Comparación de tarifas OBR de Qxtel vs Mera (switches)
    Compatible con el endpoint del backend .NET: /api/ProcessRatesByCustomer/PostVendorQxtelOBRFileDirect

    Qxtel requiere 3 archivos Excel enviados como JSON con base64:
    1. FileOne: Price List (lista de precios por destino)
    2. FileTwo: New Price (precios nuevos/actualizados)
    3. FileThree: Origin Codes (códigos de origen)

    Args:
        request: UploadFileVendorQxtelRequest con FileOne, FileTwo, FileThree (bytes), VendorName, User
        current_user: Usuario autenticado (inyectado)

    Returns:
        OBRProcessResponse: Respuesta inmediata (fire-and-forget)
    """
    vendor_name = request.vendor_name
    user_email = request.user

    logger.info(f"[OBR COMPARISON QXTEL] Vendor: {vendor_name}, User: {user_email}")

    try:
        # Validar vendor Qxtel
        vendor_name_upper = vendor_name.upper()
        if "QXTEL" not in vendor_name_upper:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Vendor '{vendor_name}' no es Qxtel. Use el endpoint /fileObrComparison para otros vendors"
            )

        # ===== DECODIFICAR Y GUARDAR ARCHIVOS TEMPORALMENTE =====
        temp_paths = []
        try:
            for idx, file_content in enumerate([request.file_one, request.file_two, request.file_three], 1):
                logger.info(f"[DEBUG QXTEL] File {idx} - type: {type(file_content)}, len: {len(file_content) if file_content else 0}")

                # Decodificar si es base64 string
                if isinstance(file_content, str):
                    logger.info(f"[DEBUG QXTEL] File {idx} - Decoding from base64 string")
                    file_bytes = base64.b64decode(file_content)
                else:
                    logger.info(f"[DEBUG QXTEL] File {idx} - Using bytes directly")
                    file_bytes = file_content

                logger.info(f"[DEBUG QXTEL] File {idx} - bytes len: {len(file_bytes)}, first 10 bytes: {file_bytes[:10]}")

                # Verificar magic bytes de ZIP/Excel
                if len(file_bytes) >= 2:
                    magic_bytes = file_bytes[:2]
                    is_valid_zip = magic_bytes == b'PK'
                    logger.info(f"[DEBUG QXTEL] File {idx} - Magic bytes: {magic_bytes.hex()} (Expected: 504b) - Valid: {is_valid_zip}")
                    if not is_valid_zip:
                        logger.error(f"[DEBUG QXTEL] File {idx} - ¡ARCHIVO NO ES ZIP! Magic bytes incorrectos.")

                # Guardar archivo temporal
                temp_fd, temp_path = tempfile.mkstemp(suffix='.xlsx')
                with os.fdopen(temp_fd, 'wb') as tmp:
                    tmp.write(file_bytes)
                temp_paths.append(temp_path)
                logger.info(f"[DEBUG QXTEL] File {idx} - Saved to {temp_path}")

        except Exception as e:
            # Limpiar archivos si falla
            logger.error(f"[DEBUG QXTEL] Error saving files: {e}", exc_info=True)
            for p in temp_paths:
                if os.path.exists(p):
                    os.remove(p)
            raise

        # ===== EJECUTAR EN THREAD SEPARADO (COMO Task.Run EN C#) =====
        file_one_name = request.file_name if request.file_name else "qxtel_rates.xlsx"
        thread = threading.Thread(
            target=_process_qxtel_background,
            args=(temp_paths[0], temp_paths[1], temp_paths[2], file_one_name, user_email),
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
