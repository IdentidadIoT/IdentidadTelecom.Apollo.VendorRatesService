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
            azure_handler.setFormatter(formatter)
            logger.addHandler(azure_handler)
            logger.info("Application Insights logging configurado correctamente")
        except Exception as e:
            logger.warning(f"No se pudo configurar Application Insights: {e}")

    return logger


# Logger global
logger = setup_logging()
