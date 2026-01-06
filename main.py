"""
Aplicación principal FastAPI - VendorRatesService
Microservicio para procesamiento de tarifas de vendors (Belgacom, Qxtel, etc.)
"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager

from config import get_settings
from core.logging import logger
from core.auth import init_auth
from core import auth_routes
import worker_obr


settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifecycle events - startup y shutdown
    """
    # Startup
    logger.info("=" * 60)
    logger.info("VendorRatesService - Iniciando microservicio")
    logger.info(f"Database: {settings.db_server}/{settings.db_database}")
    logger.info(f"Cache TTL: {settings.cache_ttl_seconds} segundos")
    logger.info(f"Application Insights: {'Enabled' if settings.appinsights_enabled else 'Disabled'}")
    logger.info("=" * 60)

    # Inicializar autenticación JWT
    init_auth()
    logger.info("JWT Authentication initialized")

    yield

    # Shutdown
    logger.info("VendorRatesService - Deteniendo microservicio")


# Crear aplicación FastAPI
app = FastAPI(
    title="VendorRatesService",
    description="Microservicio para procesamiento de tarifas de vendors (Belgacom, Qxtel, etc.)",
    version="1.0.0",
    lifespan=lifespan
)


# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Permite todos los orígenes (ajustar en producción)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Registrar rutas
app.include_router(auth_routes.router)
app.include_router(worker_obr.router)


# Exception handler global
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Handler global para excepciones no controladas
    """
    logger.error(f"Excepción no controlada: {exc}", exc_info=True)

    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "message": str(exc) if settings.debug else "An error occurred"
        }
    )


# Root endpoint
@app.get("/")
async def root():
    """
    Endpoint raíz - información del servicio
    """
    return {
        "service": "VendorRatesService",
        "version": "1.0.0",
        "description": "Vendor Rates Processing Service",
        "status": "running"
    }


# Endpoint de documentación
@app.get("/api/info")
async def api_info():
    """
    Información de la API
    """
    return {
        "service": "VendorRatesService",
        "version": "1.0.0",
        "supported_vendors": ["Belgacom Platinum", "Sunrise", "Qxtel", "Orange France Platinum", "Orange France Win", "Ibasis Global Inc Premium", "HGC Premium", "Oteglobe", "Arelion", "Deutsche Telecom", "Orange Telecom", "Apelby", "Phonetic Limited"],
        "vendors_in_development": [],
        "endpoints": {
            "fileObrComparison": "/api/vendorRates/fileObrComparison (1 archivo: Belgacom, Sunrise, Orange France Platinum, Orange France Win, Ibasis, HGC, Oteglobe, Arelion, Deutsche, Orange Telecom, Apelby, Phonetic)",
            "fileObrComparisonQxtel": "/api/vendorRates/fileObrComparisonQxtel (3 archivos: Qxtel)",
            "health": "/api/vendorRates/health",
            "docs": "/docs",
            "openapi": "/openapi.json"
        },
        "future_endpoints": {
            "templates": "/api/vendorRates/templates",
            "rateChanges": "/api/vendorRates/rateChanges",
            "masterData": "/api/vendorRates/masterData"
        }
    }


if __name__ == "__main__":
    import uvicorn

    # Configuración de Uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=settings.port,
        reload=False,
        log_level=settings.log_level.lower()
    )
