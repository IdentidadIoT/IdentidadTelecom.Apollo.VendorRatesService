"""
Rutas de autenticación JWT para VendorRatesService

Endpoints:
- POST /api/auth/login - Genera token JWT
- GET  /api/auth/health - Health check de autenticación
"""

from fastapi import APIRouter, HTTPException, status
from core.auth import generate_token, LoginRequest, LoginResponse
from core.logging import logger

router = APIRouter(
    prefix="/api/auth",
    tags=["Authentication"]
)


@router.post("/login", response_model=LoginResponse, summary="Obtener token JWT")
async def login(credentials: LoginRequest):
    """
    Genera un token JWT para autenticación.

    **Credenciales válidas:**
    - username: apollo
    - password: 1d3nt1d@d5m5.

    **Uso del token:**
    ```
    Authorization: Bearer <access_token>
    ```

    **Ejemplo de request:**
    ```json
    {
        "username": "apollo",
        "password": "1d3nt1d@d5m5."
    }
    ```

    **Ejemplo de response:**
    ```json
    {
        "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
        "token_type": "Bearer"
    }
    ```
    """
    logger.info(f"[LOGIN] Intento de login - Usuario: {credentials.username}")

    token = generate_token({
        "username": credentials.username,
        "password": credentials.password
    })

    if token is None:
        logger.warning(f"[LOGIN] Login fallido - Usuario: {credentials.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"}
        )

    logger.info(f"[LOGIN] Login exitoso - Usuario: {credentials.username}")

    return LoginResponse(
        access_token=token,
        token_type="Bearer"
    )


@router.get("/health", summary="Health check de autenticación")
async def auth_health():
    """Verifica que el sistema de autenticación esté inicializado"""
    return {
        "status": "ok",
        "service": "JWT Authentication",
        "version": "1.0.0"
    }
