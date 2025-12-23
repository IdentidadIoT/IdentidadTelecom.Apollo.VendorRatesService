"""
Utilidades para manejo de archivos temporales
Centraliza operaciones de archivos para reutilización
"""
from pathlib import Path
from typing import Optional
import tempfile
import os

from core.logging import logger
from config import get_settings


class FileManager:
    """Manager para operaciones de archivos temporales"""

    def __init__(self):
        self.settings = get_settings()
        self.temp_dir = Path(tempfile.gettempdir()) / "obrms"
        self._ensure_temp_dir_exists()

    def _ensure_temp_dir_exists(self):
        """Asegura que el directorio temporal exista"""
        try:
            self.temp_dir.mkdir(parents=True, exist_ok=True)
            logger.debug(f"Directorio temporal: {self.temp_dir}")
        except Exception as e:
            logger.error(f"Error creando directorio temporal: {e}")
            raise

    def save_temp_file(self, content: bytes, file_name: str) -> str:
        """
        Guarda contenido en archivo temporal

        Args:
            content: Contenido binario del archivo
            file_name: Nombre del archivo

        Returns:
            str: Path completo del archivo guardado
        """
        try:
            file_path = self.temp_dir / file_name

            with open(file_path, 'wb') as f:
                f.write(content)

            logger.info(f"Archivo temporal guardado: {file_path}")
            return str(file_path)

        except Exception as e:
            logger.error(f"Error guardando archivo temporal: {e}")
            raise

    def delete_temp_file(self, file_path: str) -> bool:
        """
        Elimina archivo temporal

        Args:
            file_path: Path del archivo a eliminar

        Returns:
            bool: True si se eliminó correctamente
        """
        try:
            path = Path(file_path)

            if path.exists():
                path.unlink()
                logger.info(f"Archivo temporal eliminado: {file_path}")
                return True
            else:
                logger.warning(f"Archivo no existe: {file_path}")
                return False

        except Exception as e:
            logger.error(f"Error eliminando archivo temporal: {e}")
            return False

    def get_temp_file_path(self, file_name: str) -> str:
        """
        Obtiene el path completo para un archivo temporal

        Args:
            file_name: Nombre del archivo

        Returns:
            str: Path completo
        """
        return str(self.temp_dir / file_name)

    def cleanup_old_files(self, max_age_hours: int = 24):
        """
        Limpia archivos temporales antiguos

        Args:
            max_age_hours: Edad máxima en horas (default 24)
        """
        try:
            import time
            current_time = time.time()
            max_age_seconds = max_age_hours * 3600

            deleted_count = 0

            for file_path in self.temp_dir.iterdir():
                if file_path.is_file():
                    file_age = current_time - file_path.stat().st_mtime

                    if file_age > max_age_seconds:
                        try:
                            file_path.unlink()
                            deleted_count += 1
                        except Exception as e:
                            logger.warning(f"No se pudo eliminar {file_path}: {e}")

            if deleted_count > 0:
                logger.info(f"Limpieza completada: {deleted_count} archivos eliminados")

        except Exception as e:
            logger.error(f"Error en limpieza de archivos: {e}")
