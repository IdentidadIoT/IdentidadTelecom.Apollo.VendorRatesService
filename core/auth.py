"""
Sistema de autenticación JWT para VendorRatesService
Basado en Finance.ReportGenerator

Autor: Identidad Technologies
Fecha: 2026-01-02
"""

import jwt
import configparser
from pathlib import Path
from typing import Optional, Dict
from fastapi import Header, HTTPException, status, Depends
from pydantic import BaseModel
from core.logging import logger

# ============================================================================
# VARIABLES GLOBALES - Credenciales JWT
# ============================================================================

_client: Optional[str] = None
_password: Optional[str] = None
_secret: Optional[str] = None
_id: Optional[str] = None
_issuer: Optional[str] = None

__all__ = ['init_auth', 'generate_token', 'validate_token', 'verify_token_dependency', 'LoginRequest', 'LoginResponse']


# ============================================================================
# FUNCIÓN: Inicialización
# ============================================================================

def init_auth():
    """
    Inicializa el sistema de autenticación JWT.
    Lee credenciales desde config/config.cfg

    DEBE llamarse al inicio en main.py antes de levantar el servidor.

    Raises:
        FileNotFoundError: Si no existe config.cfg
        KeyError: Si falta alguna configuración requerida
    """
    global _client, _password, _secret, _id, _issuer

    logger.info('=' * 80)
    logger.info('[AUTH JWT] Iniciando sistema de autenticación')
    logger.info('=' * 80)

    # Construir path al archivo de configuración
    config_path = Path(__file__).parent.parent / 'config' / 'config.cfg'

    logger.info(f'[AUTH JWT] Buscando configuración en: {config_path}')

    if not config_path.exists():
        error_msg = f"Archivo de configuración JWT no encontrado: {config_path}"
        logger.error(f'[AUTH JWT] ERROR: {error_msg}')
        raise FileNotFoundError(error_msg)

    # Leer configuración
    config = configparser.ConfigParser()
    config.read(config_path)

    try:
        _client = config.get('Apollo_Auth', 'client')
        _password = config.get('Apollo_Auth', 'password')
        _secret = config.get('Apollo_Auth', 'secret')
        _id = config.get('Apollo_Auth', 'id')
        _issuer = config.get('Apollo_Auth', 'issuer')

        logger.info(f'[AUTH JWT] [OK] Cliente: {_client}')
        logger.info(f'[AUTH JWT] [OK] Issuer: {_issuer}')
        logger.info(f'[AUTH JWT] [OK] ID: {_id}')
        logger.info(f'[AUTH JWT] [OK] Secret: {"*" * len(_secret)} (oculto)')
        logger.info('[AUTH JWT] Sistema de autenticación JWT inicializado correctamente')
        logger.info('=' * 80)

    except (configparser.NoSectionError, configparser.NoOptionError) as e:
        error_msg = f"Configuración JWT incompleta en {config_path}: {e}"
        logger.error(f'[AUTH JWT] ERROR: {error_msg}')
        raise KeyError(error_msg)


# ============================================================================
# FUNCIÓN: Generar Token JWT
# ============================================================================

def generate_token(auth_data: Dict[str, str]) -> Optional[str]:
    """
    Genera un token JWT si las credenciales son válidas.

    EXACTAMENTE igual que Finance.ReportGenerator/core/auth.py

    Args:
        auth_data: dict con keys 'username' y 'password'

    Returns:
        str: Token JWT firmado con HS256
        None: Si credenciales inválidas

    Example:
        >>> token = generate_token({
        ...     "username": "apollo",
        ...     "password": "1d3nt1d@d5m5."
        ... })
        >>> print(token)
        'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...'
    """
    username = auth_data.get('username')
    password = auth_data.get('password')

    logger.info(f'[AUTH JWT] Intento de autenticación - Usuario: {username}')

    # Validar credenciales (EXACTO como Finance.ReportGenerator)
    if username == _client and password == _password:
        # Construir payload (EXACTO como Finance.ReportGenerator)
        payload_data = {
            "name": _client,
            "id": _id,
            "iss": _issuer
        }

        # Generar token con HS256
        token = jwt.encode(payload_data, _secret, algorithm="HS256")

        logger.info(f'[AUTH JWT] [OK] Token generado exitosamente para: {_client}')

        return token
    else:
        logger.warning(f'[AUTH JWT] [ERROR] Autenticación fallida - Usuario: {username}')
        return None


# ============================================================================
# FUNCIÓN: Validar Token JWT
# ============================================================================

def validate_token(token: str) -> str:
    """
    Valida un token JWT.

    EXACTAMENTE igual que Finance.ReportGenerator/core/auth.py

    Args:
        token: Token JWT (puede incluir "Bearer " o "bearer " prefix)

    Returns:
        str: "Ok" si el token es válido

    Raises:
        Exception: "Error signature has expired" si expiró
        Exception: "Error invalid token" si es inválido

    Example:
        >>> validate_token("Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...")
        'Ok'
    """
    try:
        # Limpiar token (EXACTO como Finance.ReportGenerator)
        clean_token = token.replace("bearer", "").replace('Bearer', '').strip()

        logger.debug(f'[AUTH JWT] Validando token: {clean_token[:20]}...')

        # Decodificar y validar (EXACTO como Finance.ReportGenerator)
        decoded = jwt.decode(
            clean_token,
            _secret,
            issuer=_issuer,
            algorithms=["HS256"]
        )

        logger.debug(f'[AUTH JWT] [OK] Token válido - Usuario: {decoded.get("name")}')

        return "Ok"

    except jwt.ExpiredSignatureError:
        logger.error('[AUTH JWT] [ERROR] Token expirado')
        raise Exception("Error signature has expired")

    except jwt.InvalidTokenError as e:
        logger.error(f'[AUTH JWT] [ERROR] Token inválido: {e}')
        raise Exception("Error invalid token")


# ============================================================================
# DEPENDENCIA FASTAPI: Para usar en endpoints
# ============================================================================

async def verify_token_dependency(authorization: str = Header(..., description="Bearer JWT token")) -> str:
    """
    Dependencia de FastAPI para validar tokens JWT en endpoints.

    USO EN ENDPOINTS:
        @router.post("/endpoint")
        async def mi_endpoint(auth: str = Depends(verify_token_dependency)):
            # Endpoint protegido
            return {"status": "ok"}

    Args:
        authorization: Header "Authorization: Bearer <token>"

    Returns:
        str: "Ok" si válido

    Raises:
        HTTPException 401: Si falta header o token inválido
    """
    if not authorization:
        logger.warning('[AUTH JWT] Request sin Authorization header')
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header",
            headers={"WWW-Authenticate": "Bearer"}
        )

    try:
        return validate_token(authorization)

    except Exception as e:
        logger.error(f'[AUTH JWT] Validación fallida: {e}')
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"}
        )


# ============================================================================
# MODELOS PYDANTIC: Para endpoint de login
# ============================================================================

class LoginRequest(BaseModel):
    """Request para endpoint /api/auth/login"""
    username: str
    password: str

    class Config:
        json_schema_extra = {
            "example": {
                "username": "apollo",
                "password": "1d3nt1d@d5m5."
            }
        }


class LoginResponse(BaseModel):
    """Response del endpoint /api/auth/login"""
    access_token: str
    token_type: str = "Bearer"

    class Config:
        json_schema_extra = {
            "example": {
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "token_type": "Bearer"
            }
        }
