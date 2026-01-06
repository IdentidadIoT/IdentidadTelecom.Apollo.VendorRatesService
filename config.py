"""
Configuración centralizada del microservicio VendorRatesService.
Lee configuración desde archivo config/config.cfg
"""
from configparser import ConfigParser
from functools import lru_cache
from typing import Optional
from urllib.parse import quote_plus
import os


class Settings:
    """Configuración de la aplicación"""

    def __init__(self):
        # Leer config.cfg
        self._config = self._load_config()

        # Aplicación
        self.app_name = "VendorRatesService"
        self.app_version = "1.0.0"
        self.debug = False
        self.port = int(self._get_param('General', 'port', '63400'))

        # Base de datos
        self.db_driver = self._get_param('Database_SQLServer', 'DB_DRIVER', 'ODBC Driver 17 for SQL Server')
        self.db_server = self._get_param('Database_SQLServer', 'DB_SERVER')
        self.db_database = self._get_param('Database_SQLServer', 'DB_DATABASE')
        self.db_username = self._get_param('Database_SQLServer', 'DB_USERNAME')
        self.db_password = self._get_param('Database_SQLServer', 'DB_PASSWORD')
        self.db_trusted_connection = self._get_param('Database_SQLServer', 'DB_TRUSTED_CONNECTION', 'no')

        # Autenticación
        bypass_auth_str = self._get_param('Authentication', 'BYPASS_AUTH', 'false')
        self.bypass_auth = bypass_auth_str.lower() in ('true', '1', 'yes')

        # Email (SMTP)
        self.smtp_host = self._get_param('Smtp_Server', 'host_email')
        self.smtp_port = int(self._get_param('Smtp_Server', 'port', '587'))
        self.smtp_username = self._get_param('Smtp_Server', 'user')
        self.smtp_password = self._get_param('Smtp_Server', 'password')
        self.smtp_from_email = self._get_param('Smtp_Server', 'from_email')
        self.smtp_from_name = self._get_param('Smtp_Server', 'from_name', 'Apollo Vendor Rates System')

        # Archivos temporales
        self.temp_files_path = "./temp_vendor_files"

        # Cache
        self.cache_ttl_seconds = int(self._get_param('General', 'cache_ttl_seconds', '30'))
        self.cache_max_size = 10000

        # Application Insights
        insights_enabled = self._get_param('AppInsights', 'enabled', 'true')
        self.appinsights_enabled = insights_enabled.lower() in ('true', '1', 'yes')
        self.appinsights_instrumentation_key = self._get_param('AppInsights', 'instrumentation_key', None)

        # Logging
        self.log_level = self._get_param('General', 'log_level', 'INFO')
        self.log_file_path = self._get_param('General', 'log_file_path', './logs/vendor-rates-service.log')

    def _load_config(self) -> ConfigParser:
        """Carga el archivo config.cfg"""
        config = ConfigParser()

        # Buscar config.cfg en carpeta config/
        # Como config.py está en raíz, solo subimos 1 nivel
        dir_name = os.path.dirname(os.path.abspath(__file__))
        config_file = os.path.join(dir_name, 'config', 'config.cfg')

        if not os.path.exists(config_file):
            raise FileNotFoundError(
                f"Archivo de configuración no encontrado: {config_file}\n"
                f"Asegúrate de que existe el archivo config/config.cfg"
            )

        config.read(config_file)
        return config

    def _get_param(self, section: str, key: str, default: Optional[str] = None) -> Optional[str]:
        """Obtiene un parámetro del config.cfg"""
        try:
            return self._config.get(section, key)
        except Exception:
            if default is None:
                raise ValueError(f"Parámetro requerido no encontrado: [{section}] {key}")
            return default

    @property
    def database_url(self) -> str:
        """Construye la URL de conexión a SQL Server"""
        # Parámetros adicionales para Azure SQL
        azure_params = "Encrypt=yes&TrustServerCertificate=no&Connection Timeout=30"

        if self.db_trusted_connection.lower() == "yes":
            return (
                f"mssql+pyodbc://@{self.db_server}/{self.db_database}"
                f"?driver={self.db_driver}&Trusted_Connection=yes&{azure_params}"
            )

        # URL encode de usuario y contraseña para manejar caracteres especiales
        username_encoded = quote_plus(self.db_username)
        password_encoded = quote_plus(self.db_password)

        return (
            f"mssql+pyodbc://{username_encoded}:{password_encoded}"
            f"@{self.db_server}/{self.db_database}?driver={self.db_driver}&{azure_params}"
        )


@lru_cache()
def get_settings() -> Settings:
    """Singleton para configuración - se carga una sola vez"""
    return Settings()
