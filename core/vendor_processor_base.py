"""
Clase base para procesadores de vendors usando Template Method Pattern.

Este módulo define el algoritmo skeleton para procesar archivos OBR de cualquier vendor,
permitiendo que las subclases sobrescriban solo los pasos específicos.
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional

from core.logging import logger


class VendorProcessorBase(ABC):
    """
    Clase base abstracta para procesamiento de vendors usando Template Method Pattern.

    Define el workflow común de 7 pasos para todos los vendors, permitiendo que
    las subclases sobrescriban solo los pasos específicos (hooks).
    """

    def __init__(self, vendor_config: Dict[str, Any], services: Dict[str, Any]):
        """
        Inicializa el procesador con configuración y servicios compartidos.

        Args:
            vendor_config: Configuración del vendor (display_name, vendor_key, etc.)
            services: Diccionario con servicios compartidos:
                - excel: ExcelService
                - email: EmailService
                - file_manager: FileManager
                - obr_cache: OBRMasterDataCache
        """
        self.vendor_config = vendor_config
        self.vendor_name = vendor_config["display_name"]

        # Servicios compartidos
        self.excel_service = services["excel"]
        self.email_service = services["email"]
        self.file_manager = services["file_manager"]
        self.obr_cache = services["obr_cache"]

    # ========================================================================
    # TEMPLATE METHOD - Define el algoritmo skeleton (NO sobrescribir)
    # ========================================================================

    async def process_file(
        self,
        file_content: bytes,
        file_name: str,
        user_email: str
    ) -> bool:
        """
        Template Method - Define el algoritmo completo de procesamiento.

        Este método NO debe ser sobrescrito. Las subclases sobrescriben
        los hooks (_read_vendor_data, _compare_data, etc.)

        Workflow de 7 pasos:
        1. Guardar archivo(s) temporal(es)
        2. Leer datos del vendor (HOOK - subclase define)
        3. Obtener OBR master data (común)
        4. Validar datos (HOOK - puede sobrescribirse)
        5. Comparar datos (HOOK - subclase define lógica)
        6. Generar CSV (común)
        7. Enviar email de éxito/fallo/error (común)
        8. Cleanup (común)

        Args:
            file_content: Contenido del archivo (o lista de archivos para Qxtel)
            file_name: Nombre del archivo (o lista de nombres para Qxtel)
            user_email: Email del usuario para notificaciones

        Returns:
            bool: True si el procesamiento fue exitoso, False en caso contrario
        """
        logger.info(f"[{self.vendor_name}] Iniciando procesamiento: {file_name}")
        temp_files = []

        try:
            # Paso 1: Guardar archivo(s) temporal(es)
            temp_files = await self._save_temp_files(file_content, file_name)
            logger.info(f"[{self.vendor_name}] Archivos temporales guardados: {len(temp_files)}")

            # Paso 2: Leer datos del vendor (HOOK - implementado por subclase)
            vendor_data = await self._read_vendor_data(temp_files)
            logger.info(f"[{self.vendor_name}] Datos leídos del vendor")

            # Paso 3: Obtener OBR master data (común para todos)
            obr_master = await self._get_obr_master_data_cached()
            logger.info(f"[{self.vendor_name}] OBR master data obtenido: {len(obr_master)} registros")

            # Paso 4: Validar datos (HOOK - puede sobrescribirse)
            if not await self._validate_data(vendor_data, obr_master):
                logger.error(f"[{self.vendor_name}] Validación de datos falló")
                await self._send_failure_email(user_email)
                return False

            # Paso 5: Comparar datos (HOOK - implementado por subclase)
            csv_data = await self._compare_data(vendor_data, obr_master)
            logger.info(f"[{self.vendor_name}] Comparación completada: {len(csv_data)} registros")

            # Paso 6: Generar CSV (común para todos)
            csv_path = self._generate_csv_file(csv_data, self.vendor_name)
            logger.info(f"[{self.vendor_name}] CSV generado: {csv_path}")

            # Paso 7: Enviar email de éxito (común para todos)
            await self._send_success_email(user_email, csv_path)

            logger.info(f"[{self.vendor_name}] Procesamiento completado exitosamente")
            return True

        except Exception as e:
            logger.error(f"[{self.vendor_name}] Error durante procesamiento: {e}", exc_info=True)
            await self._send_error_email(user_email, str(e))
            return False

        finally:
            # Paso 8: Cleanup (común para todos)
            for file_path in temp_files:
                self.file_manager.delete_temp_file(file_path)
            logger.info(f"[{self.vendor_name}] Archivos temporales eliminados")

    # ========================================================================
    # HOOKS ABSTRACTOS - DEBEN ser implementados por subclases
    # ========================================================================

    @abstractmethod
    async def _read_vendor_data(self, temp_files: List[str]) -> Dict[str, Any]:
        """
        Lee los datos específicos del vendor desde archivos Excel.

        Este método DEBE ser implementado por cada subclase según la estructura
        específica del vendor (2 hojas, 3 hojas, múltiples archivos, etc.)

        Args:
            temp_files: Lista de rutas a archivos temporales

        Returns:
            Dict con los datos leídos. La estructura depende del vendor:
            - 2 hojas: {"price_list": [...], "origin_mapping": [...]}
            - 3 hojas: {"price_list": [...], "new_price": [...], "origins": [...]}

        Raises:
            Exception: Si hay error leyendo los datos
        """
        pass

    @abstractmethod
    async def _compare_data(
        self,
        vendor_data: Dict[str, Any],
        obr_master: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Realiza la comparación entre datos del vendor y OBR master data.

        Este método DEBE ser implementado por cada subclase con la lógica
        de comparación específica del vendor.

        Args:
            vendor_data: Datos leídos del vendor (estructura depende del vendor)
            obr_master: Datos maestros OBR filtrados por vendor

        Returns:
            Lista de diccionarios con los datos para el CSV final
            Formato: [{"destinations": str, "country_code": str, "price_min": float}, ...]

        Raises:
            Exception: Si hay error en la comparación
        """
        pass

    # ========================================================================
    # HOOKS CON IMPLEMENTACIÓN DEFAULT - PUEDEN sobrescribirse si necesario
    # ========================================================================

    async def _save_temp_files(
        self,
        file_content: bytes,
        file_name: str
    ) -> List[str]:
        """
        Guarda archivo(s) temporal(es).

        Implementación default: guardar 1 archivo.
        Qxtel sobrescribe este método para guardar 3 archivos.

        Args:
            file_content: Contenido del archivo (o lista para múltiples)
            file_name: Nombre del archivo (o lista para múltiples)

        Returns:
            Lista con rutas de archivos temporales guardados
        """
        path = self.file_manager.save_temp_file(file_content, file_name)
        return [path]

    async def _validate_data(
        self,
        vendor_data: Dict[str, Any],
        obr_master: List[Dict[str, Any]]
    ) -> bool:
        """
        Valida que los datos necesarios estén presentes.

        Implementación default: verificar que vendor_data y obr_master no estén vacíos.
        Puede sobrescribirse para validaciones más específicas.

        Args:
            vendor_data: Datos del vendor
            obr_master: Datos maestros OBR

        Returns:
            bool: True si los datos son válidos, False en caso contrario
        """
        # Verificar que obr_master no esté vacío
        if not obr_master:
            logger.error(f"[{self.vendor_name}] OBR master data vacío")
            return False

        # Verificar que todas las claves de vendor_data tengan valores no vacíos
        if not vendor_data:
            logger.error(f"[{self.vendor_name}] Vendor data vacío")
            return False

        for key, value in vendor_data.items():
            if not value:
                logger.error(f"[{self.vendor_name}] Vendor data['{key}'] vacío")
                return False

        return True

    # ========================================================================
    # MÉTODOS COMUNES - Implementación compartida (NO sobrescribir)
    # ========================================================================

    async def _get_obr_master_data_cached(self) -> List[Dict[str, Any]]:
        """
        Obtiene los datos maestros OBR filtrados por vendor (con cache).

        Returns:
            Lista de diccionarios con datos maestros OBR para este vendor
        """
        vendor_name_upper = self.vendor_name.upper()
        all_master_data = await self.obr_cache.get_master_data()

        # Filtrar por vendor
        filtered_data = [
            record for record in all_master_data
            if record.get("vendor", "").upper() == vendor_name_upper
        ]

        return filtered_data

    def _generate_csv_file(
        self,
        csv_data: List[Dict[str, Any]],
        vendor_name: str
    ) -> str:
        """
        Genera archivo CSV con los datos procesados.

        Args:
            csv_data: Lista de diccionarios con datos para CSV
            vendor_name: Nombre del vendor (para el nombre del archivo)

        Returns:
            str: Ruta al archivo CSV generado
        """
        import csv
        import os
        from datetime import datetime

        # Generar nombre de archivo con timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_vendor_name = vendor_name.replace(" ", "_")
        csv_filename = f"OBR_{safe_vendor_name}_{timestamp}.csv"

        # Usar directorio temporal del file_manager
        csv_path = os.path.join(self.file_manager.temp_dir, csv_filename)

        # Escribir CSV
        if csv_data:
            with open(csv_path, 'w', newline='', encoding='utf-8') as csvfile:
                fieldnames = ["destinations", "country_code", "price_min"]
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

                writer.writeheader()
                for row in csv_data:
                    writer.writerow({
                        "destinations": row.get("destinations", ""),
                        "country_code": row.get("country_code", ""),
                        "price_min": row.get("price_min", 0.0)
                    })

        logger.info(f"[{vendor_name}] CSV generado: {csv_path} ({len(csv_data)} registros)")
        return csv_path

    async def _send_success_email(self, user_email: str, csv_path: str):
        """
        Envía email de éxito con CSV adjunto.

        Args:
            user_email: Email del destinatario
            csv_path: Ruta al archivo CSV generado
        """
        await self.email_service.send_obr_success_email(
            to_email=user_email,
            vendor_name=self.vendor_name,
            csv_file_path=csv_path
        )
        logger.info(f"[{self.vendor_name}] Email de éxito enviado a {user_email}")

    async def _send_failure_email(self, user_email: str):
        """
        Envía email de fallo (datos incompletos).

        Args:
            user_email: Email del destinatario
        """
        await self.email_service.send_obr_failure_email(
            to_email=user_email,
            vendor_name=self.vendor_name,
            error_message="Please check the master file and vendor file"
        )
        logger.info(f"[{self.vendor_name}] Email de fallo enviado a {user_email}")

    async def _send_error_email(self, user_email: str, error_details: str):
        """
        Envía email de error con detalles técnicos.

        Args:
            user_email: Email del destinatario
            error_details: Detalles del error
        """
        await self.email_service.send_obr_error_email(
            to_email=user_email,
            vendor_name=self.vendor_name,
            error_details=error_details
        )
        logger.info(f"[{self.vendor_name}] Email de error enviado a {user_email}")
