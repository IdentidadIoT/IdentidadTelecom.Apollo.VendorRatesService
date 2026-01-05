"""
Configuración de logging con Application Insights
"""
import logging
import sys
from pathlib import Path
from typing import Optional

from opencensus.ext.azure.log_exporter import AzureLogHandler
from config import get_settings


def setup_logging() -> logging.Logger:
    """
    Configura logging con Application Insights y archivo local
    """
    settings = get_settings()

    # Crear logger
    logger = logging.getLogger("obrms")
    logger.setLevel(getattr(logging, settings.log_level.upper()))

    # Formato de logs
    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Handler para consola
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Handler para archivo
    log_file = Path(settings.log_file_path)
    log_file.parent.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Handler para Application Insights
    if settings.appinsights_enabled and settings.appinsights_instrumentation_key:
        try:
            azure_handler = AzureLogHandler(
                connection_string=f"InstrumentationKey={settings.appinsights_instrumentation_key}"
            )
            # Verificar que el handler tenga lock inicializado (compatibilidad Python 3.13)
            if hasattr(azure_handler, 'lock') and azure_handler.lock is not None:
                azure_handler.setFormatter(formatter)
                logger.addHandler(azure_handler)
                print("[INFO] Application Insights habilitado correctamente")
            else:
                print("[WARNING] Application Insights no compatible con Python 3.13 - Deshabilitado")
        except Exception as e:
            # Si falla Application Insights, continuar sin él
            print(f"[WARNING] Application Insights falló: {e}")

    return logger


# Logger global
logger = setup_logging()
