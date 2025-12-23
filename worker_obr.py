"""
Rutas API para procesamiento de archivos de vendors
Endpoints para carga y gestión de tarifas de vendors (Belgacom, Qxtel, etc.)
"""
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session

from requests import OBRProcessResponse
from core.auth import verify_user_has_obr_permission, TokenData
from dependencies import get_db
from core.obr_service import OBRService
from core.vendor_registry import find_vendor_by_name, get_supported_vendors
from core.logging import logger


router = APIRouter(
    prefix="/api/vendorRates",
    tags=["Vendor Rates"]
)


@router.post("/fileObrComparison", response_model=OBRProcessResponse)
async def file_obr_comparison(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    vendor_name: str = Form(...),
    user_email: str = Form(...),
    current_user: TokenData = Depends(verify_user_has_obr_permission),
    db: Session = Depends(get_db)
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

        # Leer contenido del archivo
        file_content = await file.read()

        if not file_content:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El archivo está vacío"
            )

        # Buscar vendor en el registro usando keyword matching
        vendor_config = find_vendor_by_name(vendor_name)

        if not vendor_config:
            # Vendor no soportado - mostrar lista de vendors disponibles
            supported = ", ".join(get_supported_vendors())
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Vendor '{vendor_name}' no está soportado. Vendors disponibles: {supported}"
            )

        # Validar que no sea Qxtel (requiere endpoint especial con 3 archivos)
        if vendor_config["file_requirement"]["type"] == "multiple":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Vendor '{vendor_config['display_name']}' requiere el endpoint /fileObrComparisonQxtel (3 archivos)"
            )

        # Crear servicio OBR
        obr_service = OBRService(db)

        # Obtener método de procesamiento desde vendor_config
        # El vendor_registry especifica explícitamente qué método ejecutar
        process_method_name = vendor_config.get("process_method_name")

        if not process_method_name:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Vendor '{vendor_config['display_name']}' no tiene método de procesamiento configurado"
            )

        # Obtener el método usando getattr (reflexión)
        process_method = getattr(obr_service, process_method_name, None)

        if not process_method or not callable(process_method):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Método '{process_method_name}' no encontrado en OBRService"
            )

        # Agregar procesamiento en background (fire-and-forget)
        background_tasks.add_task(
            process_method,
            file_content=file_content,
            file_name=file.filename,
            user_email=user_email
        )

        logger.info(f"[OBR COMPARISON] Procesamiento en background iniciado para {vendor_name}")

        # Retornar respuesta inmediata
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
    current_user: TokenData = Depends(verify_user_has_obr_permission),
    db: Session = Depends(get_db)
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

        # Leer contenido de los 3 archivos
        file_one_content = await file_one.read()
        file_two_content = await file_two.read()
        file_three_content = await file_three.read()

        if not file_one_content or not file_two_content or not file_three_content:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uno o más archivos están vacíos"
            )

        # Validar vendor Qxtel
        vendor_name_upper = vendor_name.upper()
        if "QXTEL" not in vendor_name_upper:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Vendor '{vendor_name}' no es Qxtel. Use el endpoint /fileObrComparison para otros vendors"
            )

        # Crear servicio OBR
        obr_service = OBRService(db)

        # Agregar procesamiento en background (fire-and-forget)
        background_tasks.add_task(
            obr_service.process_qxtel_file,
            file_one_content=file_one_content,
            file_two_content=file_two_content,
            file_three_content=file_three_content,
            file_one_name=file_one.filename,
            user_email=user_email
        )

        logger.info(f"[OBR COMPARISON QXTEL] Procesamiento en background iniciado para {vendor_name}")

        # Retornar respuesta inmediata
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
