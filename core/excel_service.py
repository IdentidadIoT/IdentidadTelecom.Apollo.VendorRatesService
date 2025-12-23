"""
Servicio para lectura de archivos Excel de vendors.

REFACTORIZADO: Ahora usa configuración declarativa para eliminar duplicación.
Los métodos legacy se mantienen por compatibilidad pero delegan al método genérico.
"""
from typing import List, Dict, Any, Tuple
from pathlib import Path
import openpyxl
from openpyxl.worksheet.worksheet import Worksheet
import warnings

from core.logging import logger
from core.excel_reader_base import ExcelReaderBase
from core.vendor_configs import get_vendor_config


class ExcelService:
    """Servicio para procesamiento de archivos Excel"""

    # ========================================================================
    # NUEVO MÉTODO GENÉRICO - Elimina duplicación de código
    # ========================================================================

    @staticmethod
    def read_vendor_data(
        vendor_key: str,
        file_path: str,
        sheet_type: str
    ) -> List[Dict[str, Any]]:
        """
        Método genérico para leer datos de vendor basado en configuración.

        Este método reemplaza los 33 métodos read_*_*() con un solo método configurable.

        Args:
            vendor_key: Clave del vendor (e.g., "belgacom", "sunrise", "qxtel")
            file_path: Ruta al archivo Excel
            sheet_type: Tipo de hoja a leer (e.g., "price_list", "origin_mapping", "new_price", "origins")

        Returns:
            Lista de diccionarios con los datos leídos

        Raises:
            ValueError: Si el vendor o sheet_type no están configurados

        Examples:
            >>> excel_service = ExcelService()
            >>> data = excel_service.read_vendor_data("belgacom", "file.xlsx", "price_list")
            >>> origins = excel_service.read_vendor_data("sunrise", "file.xlsx", "origin_mapping")
        """
        # Obtener configuración del vendor
        config = get_vendor_config(vendor_key)
        if not config:
            raise ValueError(f"Vendor '{vendor_key}' no está configurado")

        # Validar que el sheet_type existe para este vendor
        if sheet_type not in config.sheets:
            available = ", ".join(config.sheets.keys())
            raise ValueError(
                f"Sheet type '{sheet_type}' no existe para {vendor_key}. "
                f"Disponibles: {available}"
            )

        # Leer usando el lector base genérico
        sheet_config = config.sheets[sheet_type]
        return ExcelReaderBase.read_sheet(file_path, sheet_config, config.vendor_name)

    # ========================================================================
    # MÉTODOS LEGACY - Mantenidos por compatibilidad, delegan al método genérico
    # ========================================================================

    @staticmethod
    def read_belgacom_price_list(file_path: str) -> List[Dict[str, Any]]:
        """
        Lee la hoja 'PriceList' del archivo de Belgacom
        Retorna lista de precios por destino

        DEPRECATED: Use ExcelService.read_vendor_data("belgacom", file_path, "price_list")
        """
        return ExcelService.read_vendor_data("belgacom", file_path, "price_list")

    @staticmethod
    def read_belgacom_anumber_pricing(file_path: str) -> List[Dict[str, Any]]:
        """
        Lee la hoja 'ANumber Pricing' del archivo de Belgacom
        Retorna lista de precios por origen (A-Number)

        DEPRECATED: Use ExcelService.read_vendor_data("belgacom", file_path, "anumber_pricing")
        """
        return ExcelService.read_vendor_data("belgacom", file_path, "anumber_pricing")

    @staticmethod
    def read_sunrise_price_list(file_path: str) -> List[Dict[str, Any]]:
        """
        Lee la hoja 'Pricing' del archivo de Sunrise

        DEPRECATED: Use ExcelService.read_vendor_data("sunrise", file_path, "price_list")
        """
        return ExcelService.read_vendor_data("sunrise", file_path, "price_list")

    @staticmethod
    def read_sunrise_origin_mapping(file_path: str) -> List[Dict[str, Any]]:
        """
        Lee la hoja 'Origin' del archivo de Sunrise

        DEPRECATED: Use ExcelService.read_vendor_data("sunrise", file_path, "origin_mapping")
        """
        return ExcelService.read_vendor_data("sunrise", file_path, "origin_mapping")

    @staticmethod
    def read_qxtel_price_list(file_path: str) -> List[Dict[str, Any]]:
        """
        Lee el archivo Price List de Qxtel (FileOne)

        DEPRECATED: Use ExcelService.read_vendor_data("qxtel", file_path, "price_list")
        """
        return ExcelService.read_vendor_data("qxtel", file_path, "price_list")

    @staticmethod
    def read_qxtel_new_price(file_path: str, rate_column: int = 4) -> List[Dict[str, Any]]:
        """
        Lee el archivo New Price de Qxtel (FileTwo)

        DEPRECATED: Use ExcelService.read_vendor_data("qxtel", file_path, "new_price")
        """
        return ExcelService.read_vendor_data("qxtel", file_path, "new_price")

    @staticmethod
    def read_qxtel_origin_codes(file_path: str) -> List[Dict[str, Any]]:
        """
        Lee el archivo Origin Codes de Qxtel (FileThree)

        DEPRECATED: Use ExcelService.read_vendor_data("qxtel", file_path, "origins")
        """
        return ExcelService.read_vendor_data("qxtel", file_path, "origins")

    @staticmethod
    def read_orange_france_platinum_rates(file_path: str) -> List[Dict[str, Any]]:
        """Orange France Platinum - DEPRECATED: Use read_vendor_data("orange_france_platinum", file_path, "price_list")"""
        return ExcelService.read_vendor_data("orange_france_platinum", file_path, "price_list")

    @staticmethod
    def read_orange_france_platinum_origins(file_path: str) -> List[Dict[str, Any]]:
        """Orange France Platinum - DEPRECATED: Use read_vendor_data("orange_france_platinum", file_path, "origin_mapping")"""
        return ExcelService.read_vendor_data("orange_france_platinum", file_path, "origin_mapping")

    @staticmethod
    def read_orange_france_win_rates(file_path: str) -> List[Dict[str, Any]]:
        """Orange France Win - DEPRECATED: Use read_vendor_data("orange_france_win", file_path, "price_list")"""
        return ExcelService.read_vendor_data("orange_france_win", file_path, "price_list")

    @staticmethod
    def read_orange_france_win_origins(file_path: str) -> List[Dict[str, Any]]:
        """Orange France Win - DEPRECATED: Use read_vendor_data("orange_france_win", file_path, "origin_mapping")"""
        return ExcelService.read_vendor_data("orange_france_win", file_path, "origin_mapping")

    @staticmethod
    def read_ibasis_rates(file_path: str) -> List[Dict[str, Any]]:
        """DEPRECATED: Use read_vendor_data('ibasis', file_path, 'price_list')"""
        return ExcelService.read_vendor_data('ibasis', file_path, 'price_list')

    @staticmethod
    def read_ibasis_origins(file_path: str) -> List[Dict[str, Any]]:
        """DEPRECATED: Use read_vendor_data('ibasis', file_path, 'origin_mapping')"""
        return ExcelService.read_vendor_data('ibasis', file_path, 'origin_mapping')

    @staticmethod
    def read_hgc_rates(file_path: str) -> List[Dict[str, Any]]:
        """DEPRECATED: Use read_vendor_data('hgc', file_path, 'price_list')"""
        return ExcelService.read_vendor_data('hgc', file_path, 'price_list')

    @staticmethod
    def read_hgc_origins(file_path: str) -> List[Dict[str, Any]]:
        """DEPRECATED: Use read_vendor_data('hgc', file_path, 'origin_mapping')"""
        return ExcelService.read_vendor_data('hgc', file_path, 'origin_mapping')

    @staticmethod
    def read_oteglobe_price_list(file_path: str) -> List[Dict[str, Any]]:
        """DEPRECATED: Use read_vendor_data('oteglobe', file_path, 'price_list')"""
        return ExcelService.read_vendor_data('oteglobe', file_path, 'price_list')

    @staticmethod
    def read_oteglobe_new_price(file_path: str) -> List[Dict[str, Any]]:
        """DEPRECATED: Use read_vendor_data('oteglobe', file_path, 'new_price')"""
        return ExcelService.read_vendor_data('oteglobe', file_path, 'new_price')

    @staticmethod
    def read_oteglobe_origins(file_path: str) -> List[Dict[str, Any]]:
        """DEPRECATED: Use read_vendor_data('oteglobe', file_path, 'origins')"""
        return ExcelService.read_vendor_data('oteglobe', file_path, 'origins')

    @staticmethod
    def read_arelion_price_list(file_path: str) -> List[Dict[str, Any]]:
        """DEPRECATED: Use read_vendor_data('arelion', file_path, 'price_list')"""
        return ExcelService.read_vendor_data('arelion', file_path, 'price_list')

    @staticmethod
    def read_arelion_new_price(file_path: str) -> List[Dict[str, Any]]:
        """DEPRECATED: Use read_vendor_data('arelion', file_path, 'new_price')"""
        return ExcelService.read_vendor_data('arelion', file_path, 'new_price')

    @staticmethod
    def read_arelion_origins(file_path: str) -> List[Dict[str, Any]]:
        """DEPRECATED: Use read_vendor_data('arelion', file_path, 'origins')"""
        return ExcelService.read_vendor_data('arelion', file_path, 'origins')

    @staticmethod
    def read_deutsche_price_list(file_path: str) -> List[Dict[str, Any]]:
        """DEPRECATED: Use read_vendor_data('deutsche', file_path, 'price_list')"""
        return ExcelService.read_vendor_data('deutsche', file_path, 'price_list')

    @staticmethod
    def read_deutsche_new_price(file_path: str) -> List[Dict[str, Any]]:
        """DEPRECATED: Use read_vendor_data('deutsche', file_path, 'new_price')"""
        return ExcelService.read_vendor_data('deutsche', file_path, 'new_price')

    @staticmethod
    def read_deutsche_origins(file_path: str) -> List[Dict[str, Any]]:
        """DEPRECATED: Use read_vendor_data('deutsche', file_path, 'origins')"""
        return ExcelService.read_vendor_data('deutsche', file_path, 'origins')

    @staticmethod
    def read_orange_telecom_price_list(file_path: str) -> List[Dict[str, Any]]:
        """DEPRECATED: Use read_vendor_data('orange_telecom', file_path, 'price_list')"""
        return ExcelService.read_vendor_data('orange_telecom', file_path, 'price_list')

    @staticmethod
    def read_orange_telecom_new_price(file_path: str) -> List[Dict[str, Any]]:
        """DEPRECATED: Use read_vendor_data('orange_telecom', file_path, 'new_price')"""
        return ExcelService.read_vendor_data('orange_telecom', file_path, 'new_price')

    @staticmethod
    def read_orange_telecom_origins(file_path: str) -> List[Dict[str, Any]]:
        """DEPRECATED: Use read_vendor_data('orange_telecom', file_path, 'origins')"""
        return ExcelService.read_vendor_data('orange_telecom', file_path, 'origins')

    @staticmethod
    def read_apelby_price_list(file_path: str) -> List[Dict[str, Any]]:
        """DEPRECATED: Use read_vendor_data('apelby', file_path, 'price_list')"""
        return ExcelService.read_vendor_data('apelby', file_path, 'price_list')

    @staticmethod
    def read_apelby_new_price(file_path: str) -> List[Dict[str, Any]]:
        """DEPRECATED: Use read_vendor_data('apelby', file_path, 'new_price')"""
        return ExcelService.read_vendor_data('apelby', file_path, 'new_price')

    @staticmethod
    def read_apelby_origins(file_path: str) -> List[Dict[str, Any]]:
        """DEPRECATED: Use read_vendor_data('apelby', file_path, 'origins')"""
        return ExcelService.read_vendor_data('apelby', file_path, 'origins')

    @staticmethod
    def read_phonetic_price_list(file_path: str) -> List[Dict[str, Any]]:
        """DEPRECATED: Use read_vendor_data('phonetic', file_path, 'price_list')"""
        return ExcelService.read_vendor_data('phonetic', file_path, 'price_list')

    @staticmethod
    def read_phonetic_new_price(file_path: str) -> List[Dict[str, Any]]:
        """DEPRECATED: Use read_vendor_data('phonetic', file_path, 'new_price')"""
        return ExcelService.read_vendor_data('phonetic', file_path, 'new_price')

    @staticmethod
    def read_phonetic_origins(file_path: str) -> List[Dict[str, Any]]:
        """DEPRECATED: Use read_vendor_data('phonetic', file_path, 'origins')"""
        return ExcelService.read_vendor_data('phonetic', file_path, 'origins')

    