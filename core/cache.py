"""
Cache manager para datos maestros OBR
Implementación en memoria con TTL, igual que el backend .NET
"""
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from threading import Lock

from config import get_settings
from core.logging import logger


class CacheManager:
    """
    Gestor de caché en memoria con Time-To-Live (TTL)
    Thread-safe para múltiples peticiones concurrentes
    """

    def __init__(self):
        self._cache: Dict[str, Any] = {}
        self._cache_expiry: Dict[str, datetime] = {}
        self._lock = Lock()
        self._settings = get_settings()

    def get(self, key: str) -> Optional[Any]:
        """
        Obtiene un valor del cache si existe y no ha expirado
        """
        with self._lock:
            if key not in self._cache:
                return None

            # Verificar si expiró
            if key in self._cache_expiry:
                if datetime.now() > self._cache_expiry[key]:
                    logger.info(f"Cache expirado para key: {key}")
                    del self._cache[key]
                    del self._cache_expiry[key]
                    return None

            logger.info(f"Cache hit para key: {key}")
            return self._cache[key]

    def set(self, key: str, value: Any, ttl_seconds: Optional[int] = None) -> None:
        """
        Guarda un valor en cache con TTL
        """
        if ttl_seconds is None:
            ttl_seconds = self._settings.cache_ttl_seconds

        with self._lock:
            self._cache[key] = value
            self._cache_expiry[key] = datetime.now() + timedelta(seconds=ttl_seconds)
            logger.info(f"Cache set para key: {key}, TTL: {ttl_seconds}s")

    def clear(self, key: Optional[str] = None) -> None:
        """
        Limpia el cache. Si key es None, limpia todo el cache
        """
        with self._lock:
            if key is None:
                self._cache.clear()
                self._cache_expiry.clear()
                logger.info("Cache completamente limpiado")
            elif key in self._cache:
                del self._cache[key]
                if key in self._cache_expiry:
                    del self._cache_expiry[key]
                logger.info(f"Cache limpiado para key: {key}")

    def get_stats(self) -> Dict[str, Any]:
        """
        Retorna estadísticas del cache
        """
        with self._lock:
            return {
                "total_keys": len(self._cache),
                "keys": list(self._cache.keys()),
                "max_size": self._settings.cache_max_size,
                "ttl_seconds": self._settings.cache_ttl_seconds
            }


# Singleton del cache manager
cache_manager = CacheManager()
