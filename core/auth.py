"""
Autenticación y autorización OAuth2 Bearer Token
Compatible con el backend .NET usando validación delegada
"""
from typing import Optional
import httpx

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from config import get_settings
from core.logging import logger
from dependencies import get_db
from core.obr_repository import OBRRepository


security = HTTPBearer()
settings = get_settings()


class TokenData:
    """Datos extraídos del token"""
    def __init__(self, username: str, user_id: Optional[str] = None, email: Optional[str] = None):
        self.username = username
        self.user_id = user_id
        self.email = email


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> TokenData:
    """
    Valida el token Bearer delegando al backend .NET
    Compatible con tokens OAuth de ASP.NET Identity

    NOTA: En modo BYPASS_AUTH=true (desarrollo/testing), se omite la validación.
    En producción, BYPASS_AUTH DEBE ser false para validar tokens contra el backend .NET.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No se pudo validar las credenciales",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # ============================================================================
    # BYPASS DE AUTENTICACIÓN - SOLO PARA DESARROLLO/TESTING
    # ============================================================================
    # IMPORTANTE: Este bypass permite testing sin el backend .NET funcionando.
    # En producción, BYPASS_AUTH debe ser FALSE en config/config.cfg
    # ============================================================================
    if settings.bypass_auth:
        logger.warning("⚠️  BYPASS_AUTH está activado - Autenticación omitida (SOLO para desarrollo)")
        logger.warning("⚠️  En producción, configurar BYPASS_AUTH=false en config/config.cfg")

        # Retornar usuario mock para testing
        return TokenData(
            username="test_user",
            user_id="test_id",
            email="test@apollo.com"
        )

    # ============================================================================
    # VALIDACIÓN DE TOKEN CONTRA BACKEND .NET - PRODUCCIÓN
    # ============================================================================
    # Esta es la validación real que debe usarse en producción.
    # El backend .NET debe implementar el endpoint /api/Account/UserInfo
    # que recibe el token Bearer y retorna la información del usuario.
    # ============================================================================
    try:
        token = credentials.credentials

        # Validar token llamando al backend .NET
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{settings.backend_url}/api/Account/UserInfo",
                headers={"Authorization": f"Bearer {token}"}
            )

            if response.status_code != 200:
                logger.warning(f"Token inválido o expirado (status {response.status_code})")
                raise credentials_exception

            user_data = response.json()

            # Extraer información del usuario
            username = user_data.get("UserName") or user_data.get("userName")
            email = user_data.get("Email") or user_data.get("email")
            user_id = user_data.get("Id") or user_data.get("id")

            if not username:
                logger.warning("Token válido pero sin username")
                raise credentials_exception

            logger.info(f"Usuario autenticado: {username}")
            return TokenData(username=username, user_id=user_id, email=email)

    except httpx.RequestError as e:
        logger.error(f"Error conectando con backend .NET: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No se pudo validar el token - backend no disponible"
        )
    except Exception as e:
        logger.error(f"Error validando token: {e}")
        raise credentials_exception


async def verify_user_has_obr_permission(
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> TokenData:
    """
    Verifica que el usuario tenga permisos para cargar archivos OBR
    """
    # Aquí puedes agregar validación de roles específicos si es necesario
    # Por ahora, si está autenticado, tiene permiso

    repository = OBRRepository(db)
    # Puedes verificar roles desde la BD si es necesario
    # has_permission = repository.user_has_obr_permission(current_user.username)

    return current_user
