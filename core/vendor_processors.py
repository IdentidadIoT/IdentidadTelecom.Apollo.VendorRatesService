"""
Procesadores concretos de vendors que heredan de VendorProcessorBase.

Este módulo contiene las implementaciones específicas para diferentes tipos de vendors:
- TwoSheetVendorProcessor: Vendors con 2 hojas (price_list + origin_mapping)
- ThreeSheetVendorProcessor: Vendors con 3 hojas (price_list + new_price + origins)
- QxtelVendorProcessor: Vendor especial con 3 archivos separados
"""
from typing import List, Dict, Any

from core.vendor_processor_base import VendorProcessorBase
from core.comparison_strategies import get_comparison_strategy
from core.logging import logger


class TwoSheetVendorProcessor(VendorProcessorBase):
    """
    Procesador para vendors con estructura de 2 hojas Excel.

    Estructura:
    - Hoja 1: price_list (tarifas por destino)
    - Hoja 2: origin_mapping (mapeo de orígenes)

    Vendors que usan este procesador:
    - Belgacom Platinum
    - Orange France Platinum
    - Orange France Win
    - Ibasis Global Inc Premium
    - HGC Premium

    NOTA: Sunrise NO usa este procesador. Tiene su propia lógica
    dedicada en obr_service.py:process_sunrise_file().
    """

    async def _read_vendor_data(self, temp_files: List[str]) -> Dict[str, Any]:
        """
        Lee datos de vendor con estructura de 2 hojas.

        Args:
            temp_files: Lista con 1 ruta de archivo temporal

        Returns:
            Dict con:
                - price_list: Lista de tarifas por destino
                - origin_mapping: Lista de mapeos de origen

        Raises:
            Exception: Si hay error leyendo los datos
        """
        vendor_key = self.vendor_config["vendor_key"]
        file_path = temp_files[0]

        logger.info(f"[{self.vendor_name}] Leyendo datos de 2 hojas")

        # Leer ambas hojas usando el ExcelService genérico
        price_list = self.excel_service.read_vendor_data(
            vendor_key, file_path, "price_list"
        )

        origin_mapping = self.excel_service.read_vendor_data(
            vendor_key, file_path, "origin_mapping"
        )

        return {
            "price_list": price_list,
            "origin_mapping": origin_mapping
        }

    async def _compare_data(
        self,
        vendor_data: Dict[str, Any],
        obr_master: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Compara datos usando la estrategia específica del vendor.

        Args:
            vendor_data: Dict con price_list y origin_mapping
            obr_master: Datos maestros OBR

        Returns:
            Lista de diccionarios para el CSV final
        """
        # Obtener estrategia de comparación del vendor config
        strategy_name = self.vendor_config.get("comparison_strategy", "default")

        logger.info(f"[{self.vendor_name}] Usando estrategia: {strategy_name}")

        # Obtener y ejecutar la estrategia
        strategy = get_comparison_strategy(strategy_name)
        return strategy.compare(vendor_data, obr_master, self.vendor_config)


class ThreeSheetVendorProcessor(VendorProcessorBase):
    """
    Procesador para vendors con estructura de 3 hojas Excel.

    Estructura:
    - Hoja 1: price_list (tarifas base por destino)
    - Hoja 2: new_price (tarifas nuevas/actualizadas por origen)
    - Hoja 3: origins (mapeo de orígenes a dial codes)

    Vendors que usan este procesador:
    - Oteglobe
    - Arelion
    - Deutsche Telecom
    - Orange Telecom
    - Apelby
    - Phonetic Limited
    """

    async def _read_vendor_data(self, temp_files: List[str]) -> Dict[str, Any]:
        """
        Lee datos de vendor con estructura de 3 hojas.

        Args:
            temp_files: Lista con 1 ruta de archivo temporal

        Returns:
            Dict con:
                - price_list: Lista de tarifas base
                - new_price: Lista de tarifas nuevas por origen
                - origins: Lista de orígenes y dial codes

        Raises:
            Exception: Si hay error leyendo los datos
        """
        vendor_key = self.vendor_config["vendor_key"]
        file_path = temp_files[0]

        logger.info(f"[{self.vendor_name}] Leyendo datos de 3 hojas")

        # Leer las 3 hojas usando el ExcelService genérico
        price_list = self.excel_service.read_vendor_data(
            vendor_key, file_path, "price_list"
        )

        new_price = self.excel_service.read_vendor_data(
            vendor_key, file_path, "new_price"
        )

        origins = self.excel_service.read_vendor_data(
            vendor_key, file_path, "origins"
        )

        return {
            "price_list": price_list,
            "new_price": new_price,
            "origins": origins
        }

    async def _compare_data(
        self,
        vendor_data: Dict[str, Any],
        obr_master: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Compara datos usando la estrategia específica del vendor.

        Args:
            vendor_data: Dict con price_list, new_price y origins
            obr_master: Datos maestros OBR

        Returns:
            Lista de diccionarios para el CSV final
        """
        strategy_name = self.vendor_config.get("comparison_strategy", "oteglobe")

        logger.info(f"[{self.vendor_name}] Usando estrategia: {strategy_name}")

        # Obtener y ejecutar la estrategia
        strategy = get_comparison_strategy(strategy_name)
        return strategy.compare(vendor_data, obr_master, self.vendor_config)


class QxtelVendorProcessor(VendorProcessorBase):
    """
    Procesador especial para Qxtel que usa 3 archivos separados.

    Estructura:
    - Archivo 1: Price List (tarifas base)
    - Archivo 2: New Price (tarifas nuevas por región/origen)
    - Archivo 3: Origin Codes (mapeo de orígenes a códigos)

    Este vendor es único porque recibe 3 archivos Excel separados en lugar de
    1 archivo con múltiples hojas.
    """

    async def _save_temp_files(
        self,
        file_content: Any,
        file_name: Any
    ) -> List[str]:
        """
        Sobrescribe el método para guardar 3 archivos en lugar de 1.

        Args:
            file_content: Lista de 3 bytes objects
            file_name: Lista de 3 nombres de archivo

        Returns:
            Lista con 3 rutas de archivos temporales

        Raises:
            ValueError: Si no se proporcionan exactamente 3 archivos
        """
        if not isinstance(file_content, list) or len(file_content) != 3:
            raise ValueError(f"Qxtel requiere exactamente 3 archivos, recibidos: {len(file_content) if isinstance(file_content, list) else 1}")

        logger.info(f"[{self.vendor_name}] Guardando 3 archivos temporales")

        paths = []
        for content, name in zip(file_content, file_name):
            path = self.file_manager.save_temp_file(content, name)
            paths.append(path)

        return paths

    async def _read_vendor_data(self, temp_files: List[str]) -> Dict[str, Any]:
        """
        Lee datos de los 3 archivos separados de Qxtel.

        Args:
            temp_files: Lista con 3 rutas de archivos temporales
                [0]: Price List
                [1]: New Price
                [2]: Origin Codes

        Returns:
            Dict con:
                - price_list: Lista de tarifas base
                - new_price: Lista de tarifas nuevas
                - origins: Lista de códigos de origen

        Raises:
            Exception: Si hay error leyendo los datos
        """
        if len(temp_files) != 3:
            raise ValueError(f"Qxtel requiere 3 archivos, recibidos: {len(temp_files)}")

        vendor_key = "qxtel"

        logger.info(f"[{self.vendor_name}] Leyendo datos de 3 archivos separados")

        # Leer los 3 archivos usando el ExcelService genérico
        price_list = self.excel_service.read_vendor_data(
            vendor_key, temp_files[0], "price_list"
        )

        new_price = self.excel_service.read_vendor_data(
            vendor_key, temp_files[1], "new_price"
        )

        origins = self.excel_service.read_vendor_data(
            vendor_key, temp_files[2], "origins"
        )

        return {
            "price_list": price_list,
            "new_price": new_price,
            "origins": origins
        }

    async def _compare_data(
        self,
        vendor_data: Dict[str, Any],
        obr_master: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Compara datos de Qxtel usando su estrategia específica.

        Args:
            vendor_data: Dict con price_list, new_price y origins
            obr_master: Datos maestros OBR

        Returns:
            Lista de diccionarios para el CSV final
        """
        strategy_name = self.vendor_config.get("comparison_strategy", "qxtel")

        logger.info(f"[{self.vendor_name}] Usando estrategia: {strategy_name}")

        # Obtener y ejecutar la estrategia
        strategy = get_comparison_strategy(strategy_name)
        return strategy.compare(vendor_data, obr_master, self.vendor_config)
