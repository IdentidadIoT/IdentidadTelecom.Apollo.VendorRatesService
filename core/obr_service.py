"""
Servicio principal de procesamiento OBR
Contiene la lógica de negocio para Belgacom
"""
from typing import List, Dict, Any, Tuple
from pathlib import Path
from datetime import datetime
import csv

from sqlalchemy.orm import Session

from core.logging import logger
from core.cache import cache_manager
from config import get_settings
from core.obr_repository import OBRRepository
from core.excel_service import ExcelService
from core.email_service import EmailService
from core.file_utils import FileManager


class OBRService:
    """Servicio principal para procesamiento de archivos OBR"""

    def __init__(self, db: Session):
        self.db = db
        self.repository = OBRRepository(db)
        self.excel_service = ExcelService()
        self.email_service = EmailService()
        self.file_manager = FileManager()
        self.settings = get_settings()

    @staticmethod
    def _parse_and_split_dial_codes(dial_codes_str: str) -> List[str]:
        """
        Parsea y separa códigos de marcación que pueden contener:
        - Múltiples códigos separados por ';' (ej: "31;32;33")
        - Rangos con '-' (ej: "31-35" se expande a ["31", "32", "33", "34", "35"])
        - Combinaciones (ej: "31;33-35" se expande a ["31", "33", "34", "35"])
        """
        result = []

        # Dividir por punto y coma
        parts = dial_codes_str.split(';')

        for part in parts:
            part = part.strip()
            if '-' in part:
                # Es un rango, expandirlo
                range_parts = part.split('-')
                if len(range_parts) == 2:
                    try:
                        start = int(range_parts[0].strip())
                        end = int(range_parts[1].strip())
                        for i in range(start, end + 1):
                            result.append(str(i))
                    except ValueError:
                        # Si no son números, agregar tal cual
                        result.append(part)
            else:
                # Código simple
                result.append(part)

        return result

    async def process_belgacom_file(
        self,
        file_content: bytes,
        file_name: str,
        user_email: str
    ) -> bool:
        """
        Procesa archivo OBR de Belgacom
        Este método se ejecuta en background

        Returns:
            bool: True si el procesamiento fue exitoso
        """
        logger.info(f"[OBR START] Belgacom Platinum, User: {user_email}")
        file_path = None

        try:
            # 1. Guardar archivo temporalmente
            file_path = self.file_manager.save_temp_file(file_content, file_name)
            logger.info(f"Archivo temporal guardado: {file_path}")

            # 2. Leer datos del archivo Excel
            price_list = self.excel_service.read_belgacom_price_list(file_path)
            anumber_pricing = self.excel_service.read_belgacom_anumber_pricing(file_path)

            # 3. Obtener datos maestros OBR (con cache)
            obr_master_data = self._get_obr_master_data_cached()

            # 4. Validar que tenemos todos los datos necesarios
            if not price_list or not anumber_pricing or not obr_master_data:
                logger.error("Faltan datos necesarios para procesamiento")
                await self.email_service.send_obr_failure_email(
                    to_email=user_email,
                    vendor_name="Belgacom Platinum",
                    error_message="Please check the master file and vendor file"
                )
                return False

            # 5. Comparar y generar datos para CSV
            csv_data = self._compare_belgacom_data(
                price_list=price_list,
                anumber_pricing=anumber_pricing,
                obr_master_data=obr_master_data
            )

            # 6. Generar archivo CSV
            csv_file_path = self._generate_csv_file(
                csv_data=csv_data,
                vendor_name="Belgacom Platinum"
            )

            # 7. Enviar email de éxito con CSV adjunto
            await self.email_service.send_obr_success_email(
                to_email=user_email,
                vendor_name="Belgacom Platinum",
                csv_file_path=csv_file_path
            )

            logger.info(f"[OBR END] Belgacom Platinum, Success: True")
            return True

        except Exception as e:
            logger.error(f"Error procesando Belgacom: {e}", exc_info=True)

            # Enviar email de error con detalles técnicos
            await self.email_service.send_obr_error_email(
                to_email=user_email,
                vendor_name="Belgacom Platinum",
                error_details=str(e)
            )

            return False

        finally:
            # Limpiar archivo temporal
            if file_path:
                self.file_manager.delete_temp_file(file_path)

    async def process_sunrise_file(
        self,
        file_content: bytes,
        file_name: str,
        user_email: str
    ) -> bool:
        """
        Procesa archivo OBR de Sunrise
        Este método se ejecuta en background

        Returns:
            bool: True si el procesamiento fue exitoso
        """
        logger.info(f"[OBR START] Sunrise, User: {user_email}")
        file_path = None

        try:
            # 1. Guardar archivo temporalmente
            file_path = self.file_manager.save_temp_file(file_content, file_name)
            logger.info(f"Archivo temporal guardado: {file_path}")

            # 2. Leer datos del archivo Excel (2 hojas: Pricing y Origin)
            price_list = self.excel_service.read_sunrise_price_list(file_path)
            origin_mapping = self.excel_service.read_sunrise_origin_mapping(file_path)

            # 3. Obtener datos maestros OBR (con cache)
            obr_master_data = self._get_obr_master_data_cached()

            # 4. Validar que tenemos todos los datos necesarios
            if not price_list or not origin_mapping or not obr_master_data:
                logger.error("Faltan datos necesarios para procesamiento Sunrise")
                await self.email_service.send_obr_failure_email(
                    to_email=user_email,
                    vendor_name="Sunrise",
                    error_message="Please check the master file and vendor file"
                )
                return False

            # 5. Comparar y generar datos para CSV
            csv_data = self._compare_sunrise_data(
                price_list=price_list,
                origin_mapping=origin_mapping,
                obr_master_data=obr_master_data
            )

            # 6. Generar archivo CSV
            csv_file_path = self._generate_csv_file(
                csv_data=csv_data,
                vendor_name="Sunrise"
            )

            # 7. Enviar email de éxito con CSV adjunto
            await self.email_service.send_obr_success_email(
                to_email=user_email,
                vendor_name="Sunrise",
                csv_file_path=csv_file_path
            )

            logger.info(f"[OBR END] Sunrise, Success: True")
            return True

        except Exception as e:
            logger.error(f"Error procesando Sunrise: {e}", exc_info=True)

            # Enviar email de error con detalles técnicos
            await self.email_service.send_obr_error_email(
                to_email=user_email,
                vendor_name="Sunrise",
                error_details=str(e)
            )

            return False

        finally:
            # Limpiar archivo temporal
            if file_path:
                self.file_manager.delete_temp_file(file_path)

    async def process_qxtel_file(
        self,
        file_one_content: bytes,
        file_two_content: bytes,
        file_three_content: bytes,
        file_one_name: str,
        user_email: str
    ) -> bool:
        """
        Procesa archivos OBR de Qxtel (3 archivos)
        Este método se ejecuta en background

        Args:
            file_one_content: Price List file
            file_two_content: New Price file
            file_three_content: Origin Codes file
            file_one_name: Nombre del primer archivo (para timestamp)
            user_email: Email del usuario

        Returns:
            bool: True si el procesamiento fue exitoso
        """
        logger.info(f"[OBR START] Qxtel, User: {user_email}")
        file_path_one = None
        file_path_two = None
        file_path_three = None

        try:
            # 1. Guardar archivos temporalmente
            file_path_one = self.file_manager.save_temp_file(file_one_content, f"qxtel_one_{file_one_name}")
            file_path_two = self.file_manager.save_temp_file(file_two_content, f"qxtel_two_{file_one_name}")
            file_path_three = self.file_manager.save_temp_file(file_three_content, f"qxtel_three_{file_one_name}")
            logger.info(f"Archivos temporales guardados: {file_path_one}, {file_path_two}, {file_path_three}")

            # 2. Leer datos de los 3 archivos Excel
            price_list = self.excel_service.read_qxtel_price_list(file_path_one)
            new_price_list = self.excel_service.read_qxtel_new_price(file_path_two)
            origin_codes = self.excel_service.read_qxtel_origin_codes(file_path_three)

            # 3. Obtener datos maestros OBR (con cache)
            obr_master_data = self._get_obr_master_data_cached()

            # 4. Validar que tenemos todos los datos necesarios
            if not price_list or not new_price_list or not origin_codes or not obr_master_data:
                logger.error("Faltan datos necesarios para procesamiento Qxtel")
                await self.email_service.send_obr_failure_email(
                    to_email=user_email,
                    vendor_name="Qxtel",
                    error_message="Please check the master file and vendor files"
                )
                return False

            # 5. Comparar y generar datos para CSV
            csv_data = self._compare_qxtel_data(
                price_list=price_list,
                new_price_list=new_price_list,
                origin_codes=origin_codes,
                obr_master_data=obr_master_data
            )

            # 6. Generar archivo CSV
            csv_file_path = self._generate_csv_file(
                csv_data=csv_data,
                vendor_name="Qxtel"
            )

            # 7. Enviar email de éxito con CSV adjunto
            await self.email_service.send_obr_success_email(
                to_email=user_email,
                vendor_name="Qxtel",
                csv_file_path=csv_file_path
            )

            logger.info(f"[OBR END] Qxtel, Success: True")
            return True

        except Exception as e:
            logger.error(f"Error procesando Qxtel: {e}", exc_info=True)

            # Enviar email de error con detalles técnicos
            await self.email_service.send_obr_error_email(
                to_email=user_email,
                vendor_name="Qxtel",
                error_details=str(e)
            )

            return False

        finally:
            # Limpiar archivos temporales
            for file_path in [file_path_one, file_path_two, file_path_three]:
                if file_path:
                    self.file_manager.delete_temp_file(file_path)

    async def process_orange_france_platinum_file(
        self,
        file_content: bytes,
        file_name: str,
        user_email: str
    ) -> bool:
        """
        Procesa archivo OBR de Orange France Platinum
        Este método se ejecuta en background

        Returns:
            bool: True si el procesamiento fue exitoso
        """
        logger.info(f"[OBR START] Orange France Platinum, User: {user_email}")
        file_path = None

        try:
            # 1. Guardar archivo temporalmente
            file_path = self.file_manager.save_temp_file(file_content, file_name)
            logger.info(f"Archivo temporal guardado: {file_path}")

            # 2. Leer datos del archivo Excel (2 hojas: Rates y Origin Mapping)
            price_list = self.excel_service.read_orange_france_platinum_rates(file_path)
            origin_mapping = self.excel_service.read_orange_france_platinum_origins(file_path)

            # 3. Obtener datos maestros OBR (con cache)
            obr_master_data = self._get_obr_master_data_cached()

            # 4. Validar que tenemos todos los datos necesarios
            if not price_list or not origin_mapping or not obr_master_data:
                logger.error("Faltan datos necesarios para procesamiento Orange France Platinum")
                await self.email_service.send_obr_failure_email(
                    to_email=user_email,
                    vendor_name="Orange France Platinum",
                    error_message="Please check the master file and vendor file"
                )
                return False

            # 5. Comparar y generar datos para CSV
            csv_data = self._compare_orange_france_platinum_data(
                price_list=price_list,
                origin_mapping=origin_mapping,
                obr_master_data=obr_master_data
            )

            # 6. Generar archivo CSV
            csv_file_path = self._generate_csv_file(
                csv_data=csv_data,
                vendor_name="Orange France Platinum"
            )

            # 7. Enviar email de éxito con CSV adjunto
            await self.email_service.send_obr_success_email(
                to_email=user_email,
                vendor_name="Orange France Platinum",
                csv_file_path=csv_file_path
            )

            logger.info(f"[OBR END] Orange France Platinum, Success: True")
            return True

        except Exception as e:
            logger.error(f"Error procesando Orange France Platinum: {e}", exc_info=True)

            # Enviar email de error con detalles técnicos
            await self.email_service.send_obr_error_email(
                to_email=user_email,
                vendor_name="Orange France Platinum",
                error_details=str(e)
            )

            return False

        finally:
            # Limpiar archivo temporal
            if file_path:
                self.file_manager.delete_temp_file(file_path)

    async def process_orange_france_win_file(
        self,
        file_content: bytes,
        file_name: str,
        user_email: str
    ) -> bool:
        """
        Procesa archivo OBR de Orange France Win
        Este método se ejecuta en background
        IDÉNTICO a Orange France Platinum

        Returns:
            bool: True si el procesamiento fue exitoso
        """
        logger.info(f"[OBR START] Orange France Win, User: {user_email}")
        file_path = None

        try:
            # 1. Guardar archivo temporalmente
            file_path = self.file_manager.save_temp_file(file_content, file_name)
            logger.info(f"Archivo temporal guardado: {file_path}")

            # 2. Leer datos del archivo Excel (2 hojas: Rates y Origin Mapping)
            price_list = self.excel_service.read_orange_france_win_rates(file_path)
            origin_mapping = self.excel_service.read_orange_france_win_origins(file_path)

            # 3. Obtener datos maestros OBR (con cache)
            obr_master_data = self._get_obr_master_data_cached()

            # 4. Validar que tenemos todos los datos necesarios
            if not price_list or not origin_mapping or not obr_master_data:
                logger.error("Faltan datos necesarios para procesamiento Orange France Win")
                await self.email_service.send_obr_failure_email(
                    to_email=user_email,
                    vendor_name="Orange France Win",
                    error_message="Please check the master file and vendor file"
                )
                return False

            # 5. Comparar y generar datos para CSV
            csv_data = self._compare_orange_france_win_data(
                price_list=price_list,
                origin_mapping=origin_mapping,
                obr_master_data=obr_master_data
            )

            # 6. Generar archivo CSV
            csv_file_path = self._generate_csv_file(
                csv_data=csv_data,
                vendor_name="Orange France Win"
            )

            # 7. Enviar email de éxito con CSV adjunto
            await self.email_service.send_obr_success_email(
                to_email=user_email,
                vendor_name="Orange France Win",
                csv_file_path=csv_file_path
            )

            logger.info(f"[OBR END] Orange France Win, Success: True")
            return True

        except Exception as e:
            logger.error(f"Error procesando Orange France Win: {e}", exc_info=True)

            # Enviar email de error con detalles técnicos
            await self.email_service.send_obr_error_email(
                to_email=user_email,
                vendor_name="Orange France Win",
                error_details=str(e)
            )

            return False

        finally:
            # Limpiar archivo temporal
            if file_path:
                self.file_manager.delete_temp_file(file_path)

    async def process_ibasis_file(
        self,
        file_content: bytes,
        file_name: str,
        user_email: str
    ) -> bool:
        """
        Procesa archivo OBR de Ibasis Global Inc Premium
        Este método se ejecuta en background

        Returns:
            bool: True si el procesamiento fue exitoso
        """
        logger.info(f"[OBR START] Ibasis Global Inc Premium, User: {user_email}")
        file_path = None

        try:
            # 1. Guardar archivo temporalmente
            file_path = self.file_manager.save_temp_file(file_content, file_name)
            logger.info(f"Archivo temporal guardado: {file_path}")

            # 2. Leer datos del archivo Excel (2 hojas: Pricelist y Origin List)
            price_list = self.excel_service.read_ibasis_rates(file_path)
            origin_mapping = self.excel_service.read_ibasis_origins(file_path)

            # 3. Obtener datos maestros OBR (con cache)
            obr_master_data = self._get_obr_master_data_cached()

            # 4. Validar que tenemos todos los datos necesarios
            if not price_list or not origin_mapping or not obr_master_data:
                logger.error("Faltan datos necesarios para procesamiento Ibasis")
                await self.email_service.send_obr_failure_email(
                    to_email=user_email,
                    vendor_name="Ibasis Global Inc Premium",
                    error_message="Please check the master file and vendor file"
                )
                return False

            # 5. Comparar y generar datos para CSV
            csv_data = self._compare_ibasis_data(
                price_list=price_list,
                origin_mapping=origin_mapping,
                obr_master_data=obr_master_data
            )

            # 6. Generar archivo CSV
            csv_file_path = self._generate_csv_file(
                csv_data=csv_data,
                vendor_name="Ibasis Global Inc Premium"
            )

            # 7. Enviar email de éxito con CSV adjunto
            await self.email_service.send_obr_success_email(
                to_email=user_email,
                vendor_name="Ibasis Global Inc Premium",
                csv_file_path=csv_file_path
            )

            logger.info(f"[OBR END] Ibasis, Success: True")
            return True

        except Exception as e:
            logger.error(f"Error procesando Ibasis: {e}", exc_info=True)

            # Enviar email de error con detalles técnicos
            await self.email_service.send_obr_error_email(
                to_email=user_email,
                vendor_name="Ibasis Global Inc Premium",
                error_details=str(e)
            )

            return False

        finally:
            # Limpiar archivo temporal
            if file_path:
                self.file_manager.delete_temp_file(file_path)

    async def process_hgc_file(
        self,
        file_content: bytes,
        file_name: str,
        user_email: str
    ) -> bool:
        """
        Procesa archivo OBR de HGC Premium
        Este vendor tiene lógica especial para origin_code "44" (UK)

        Returns:
            bool: True si el procesamiento fue exitoso
        """
        logger.info(f"[OBR START] HGC Premium, User: {user_email}")
        file_path = None

        try:
            # 1. Guardar archivo temporalmente
            file_path = self.file_manager.save_temp_file(file_content, file_name)
            logger.info(f"Archivo temporal guardado: {file_path}")

            # 2. Leer datos del archivo Excel (2 hojas: Rates y Origin Mapping)
            price_list = self.excel_service.read_hgc_rates(file_path)
            origin_mapping = self.excel_service.read_hgc_origins(file_path)

            # 3. Obtener datos maestros OBR (con cache)
            obr_master_data = self._get_obr_master_data_cached()

            # 4. Validar que tenemos todos los datos necesarios
            if not price_list or not origin_mapping or not obr_master_data:
                logger.error("Faltan datos necesarios para procesamiento HGC")
                await self.email_service.send_obr_failure_email(
                    to_email=user_email,
                    vendor_name="HGC Premium",
                    error_message="Please check the master file and vendor file"
                )
                return False

            # 5. Comparar y generar datos para CSV (con lógica especial "44")
            csv_data = self._compare_hgc_data(
                price_list=price_list,
                origin_mapping=origin_mapping,
                obr_master_data=obr_master_data
            )

            # 6. Generar archivo CSV
            csv_file_path = self._generate_csv_file(
                csv_data=csv_data,
                vendor_name="HGC Premium"
            )

            # 7. Enviar email de éxito con CSV adjunto
            await self.email_service.send_obr_success_email(
                to_email=user_email,
                vendor_name="HGC Premium",
                csv_file_path=csv_file_path
            )

            logger.info(f"[OBR END] HGC Premium, Success: True")
            return True

        except Exception as e:
            logger.error(f"Error procesando HGC Premium: {e}", exc_info=True)

            # Enviar email de error con detalles técnicos
            await self.email_service.send_obr_error_email(
                to_email=user_email,
                vendor_name="HGC Premium",
                error_details=str(e)
            )

            return False

        finally:
            # Limpiar archivo temporal
            if file_path:
                self.file_manager.delete_temp_file(file_path)

    def _get_obr_master_data_cached(self) -> List[Dict[str, Any]]:
        """
        Obtiene datos maestros OBR con cache
        TTL configurable (default: 30 segundos)
        """
        cache_key = "obr_master_data"

        # Intentar obtener del cache
        cached_data = cache_manager.get(cache_key)
        if cached_data is not None:
            return cached_data

        # Si no está en cache, leer de BD
        logger.info("Cache miss - Leyendo OBR Master Data de BD")
        master_data = self.repository.get_obr_master_data()

        # Guardar en cache
        cache_manager.set(cache_key, master_data, ttl_seconds=self.settings.cache_ttl_seconds)

        return master_data

    def _compare_belgacom_data(
        self,
        price_list: List[Dict[str, Any]],
        anumber_pricing: List[Dict[str, Any]],
        obr_master_data: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Compara datos de Belgacom con datos maestros OBR
        Implementa la misma lógica que el backend .NET
        """
        logger.info("Iniciando comparación de datos Belgacom")

        vendor_name_upper = "BELGACOM PLATINUM"

        # Filtrar datos maestros para Belgacom
        belgacom_master_data = [
            item for item in obr_master_data
            if item["vendor"].upper() == vendor_name_upper
        ]

        logger.info(f"Datos maestros Belgacom: {len(belgacom_master_data)} registros")

        list_to_send_in_csv = []

        # Procesar cada configuración de vendor en datos maestros
        for vendor in belgacom_master_data:
            destiny_code = str(vendor["destiny_code"])
            origin_code = str(vendor["origin_code"])
            routing = vendor["routing"]

            # Filtrar price_list por destiny_code
            price_list_destinations = [
                item for item in price_list
                if item["country_code"] == destiny_code
            ]

            # Filtrar anumber_pricing por origin y destiny
            items_with_same_origin = [
                item for item in anumber_pricing
                if vendor["destiny"].upper() in item["reference_destinations"].upper()
                and item["origin"] == origin_code
            ]

            # Procesar cada item de price_list_destinations
            for price_item in price_list_destinations:
                # Caso especial: "traffic from eu" + Italia + Andorra + "italy mobile tim"
                if (routing.lower() == "traffic from eu"
                    and destiny_code == "39"
                    and origin_code == "376"
                    and price_item["destinations"].lower() == "italy mobile tim"):

                    # Buscar precio máximo de orígenes que empiecen con 4 o 3
                    matching_items = [
                        item for item in anumber_pricing
                        if (item["origin"].startswith("4") or item["origin"].startswith("3"))
                        and item["reference_destinations"].lower() == "italy mobile tim"
                    ]

                    if matching_items:
                        # Obtener el de precio máximo
                        max_price_item = max(matching_items, key=lambda x: x["price_min"])

                        list_to_send_in_csv.append({
                            "destinations": price_item["destinations"],
                            "country_code": price_item["country_code"],
                            "area_code": price_item["area_code"],
                            "country_area": price_item["country_area"],
                            "price_min": max_price_item["price_min"],
                            "start_date": max_price_item["start_date"],
                            "origin_name": routing
                        })

                else:
                    # Caso normal: buscar coincidencia por reference_destinations
                    matching_item = next(
                        (item for item in items_with_same_origin
                         if item["reference_destinations"] == price_item["destinations"]
                         and item["origin"] == origin_code),
                        None
                    )

                    if matching_item:
                        # Usar precio de anumber_pricing
                        list_to_send_in_csv.append({
                            "destinations": price_item["destinations"],
                            "country_code": price_item["country_code"],
                            "area_code": price_item["area_code"],
                            "country_area": price_item["country_area"],
                            "price_min": matching_item["price_min"],
                            "start_date": matching_item["start_date"],
                            "origin_name": routing
                        })
                    else:
                        # Usar precio original de price_list
                        list_to_send_in_csv.append({
                            "destinations": price_item["destinations"],
                            "country_code": price_item["country_code"],
                            "area_code": price_item["area_code"],
                            "country_area": price_item["country_area"],
                            "price_min": price_item["price_min"],
                            "start_date": price_item["start_date"],
                            "origin_name": routing
                        })

        # Agregar todos los items de price_list al final
        for price_item in price_list:
            # Saltar código especial 88237 (caso extraño del backend)
            if price_item["country_area"] == "88237":
                continue

            list_to_send_in_csv.append({
                "destinations": price_item["destinations"],
                "country_code": price_item["country_code"],
                "area_code": price_item["area_code"],
                "country_area": price_item["country_area"],
                "price_min": price_item["price_min"],
                "start_date": price_item["start_date"],
                "origin_name": ""
            })

        logger.info(f"Comparación completada: {len(list_to_send_in_csv)} registros para CSV")
        return list_to_send_in_csv

    def _compare_sunrise_data(
        self,
        price_list: List[Dict[str, Any]],
        origin_mapping: List[Dict[str, Any]],
        obr_master_data: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Compara datos de Sunrise con datos maestros OBR
        Implementa la misma lógica que el backend .NET (GenerateOBRSunriseFileDirect)
        """
        logger.info("Iniciando comparación de datos Sunrise")

        vendor_name_upper = "SUNRISE"

        # Filtrar datos maestros para Sunrise
        sunrise_master_data = [
            item for item in obr_master_data
            if item["vendor"].upper() == vendor_name_upper
        ]

        logger.info(f"Datos maestros Sunrise: {len(sunrise_master_data)} registros")

        list_to_send_in_csv = []
        unique_dial_codes = set()  # Para evitar duplicados

        # Procesar cada configuración de vendor en datos maestros
        for vendor in sunrise_master_data:
            origin_code = str(vendor["origin_code"])
            routing = vendor["routing"]

            # Encontrar orígenes que coincidan con este origin_code
            # dialed_digit debe coincidir con origin_code
            matching_origins = [
                origin for origin in origin_mapping
                if origin["dialed_digit"] == origin_code
            ]

            # Para cada origen que coincide
            for origin in matching_origins:
                origin_set = origin["origin_set"]
                origin_name = origin["origin_name"]

                # Encontrar entradas de price_list que coincidan con OriginSet y Origin
                matching_prices = [
                    price for price in price_list
                    if price["origin_set"] == origin_set and price["origin"] == origin_name
                ]

                # Obtener el primer item que coincida (o None)
                first_match = next(
                    (price for price in matching_prices if price["origin"] == origin_name),
                    None
                )

                # Procesar cada entrada de precio que coincida
                for price_item in matching_prices:
                    if first_match is not None:
                        # Usar el precio del primer match
                        dial_codes = self._parse_and_split_dial_codes(price_item["dial_codes"])
                        first_dial_code = dial_codes[0] if dial_codes else ""

                        if first_dial_code.strip() and first_dial_code.strip() not in unique_dial_codes:
                            list_to_send_in_csv.append({
                                "destinations": first_match["destination"],
                                "country_code": first_dial_code.strip(),
                                "area_code": "",
                                "country_area": first_dial_code.strip(),
                                "price_min": first_match["rate"],
                                "start_date": first_match["effective_date"],
                                "origin_name": routing
                            })
                            unique_dial_codes.add(first_dial_code.strip())

                    else:
                        # Si no hay match exacto, usar el precio más alto
                        same_dial_code_prices = [
                            p for p in matching_prices
                            if p["dial_codes"] == price_item["dial_codes"]
                        ]

                        if same_dial_code_prices:
                            max_price_item = max(same_dial_code_prices, key=lambda x: x["rate"])

                            dial_codes = self._parse_and_split_dial_codes(price_item["dial_codes"])
                            first_dial_code = dial_codes[0] if dial_codes else ""

                            if first_dial_code.strip() and first_dial_code.strip() not in unique_dial_codes:
                                list_to_send_in_csv.append({
                                    "destinations": max_price_item["destination"],
                                    "country_code": first_dial_code.strip(),
                                    "area_code": "",
                                    "country_area": first_dial_code.strip(),
                                    "price_min": max_price_item["rate"],
                                    "start_date": max_price_item["effective_date"],
                                    "origin_name": routing
                                })
                                unique_dial_codes.add(first_dial_code.strip())

        # Agregar todos los destinos únicos de price_list sin routing
        # (para destinos sin origen específico)
        unique_destinations_final = set()

        for price_item in price_list:
            destination = price_item["destination"]

            # Evitar procesar el mismo destino múltiples veces
            if destination in unique_destinations_final:
                continue

            # Obtener todas las entradas para este destino
            same_destination_prices = [
                p for p in price_list
                if p["destination"] == destination
            ]

            # Obtener el de precio más alto
            max_price_item = max(same_destination_prices, key=lambda x: x["rate"])

            # Parsear dial codes y tomar el primero
            dial_codes = self._parse_and_split_dial_codes(max_price_item["dial_codes"])
            first_dial_code = dial_codes[0] if dial_codes else ""

            if first_dial_code.strip() and first_dial_code.strip() not in unique_dial_codes:
                list_to_send_in_csv.append({
                    "destinations": max_price_item["destination"],
                    "country_code": first_dial_code.strip(),
                    "area_code": "",
                    "country_area": first_dial_code.strip(),
                    "price_min": max_price_item["rate"],
                    "start_date": max_price_item["effective_date"],
                    "origin_name": ""  # Sin routing para destinos genéricos
                })
                unique_dial_codes.add(first_dial_code.strip())

            unique_destinations_final.add(destination)

        logger.info(f"Comparación Sunrise completada: {len(list_to_send_in_csv)} registros para CSV")
        return list_to_send_in_csv

    def _compare_qxtel_data(
        self,
        price_list: List[Dict[str, Any]],
        new_price_list: List[Dict[str, Any]],
        origin_codes: List[Dict[str, Any]],
        obr_master_data: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Compara datos de Qxtel con datos maestros OBR
        Implementa la misma lógica que el backend .NET (VendorQxtelDataSendForCompareToMeraDirect)

        Qxtel es más complejo porque:
        1. Usa 3 archivos (Price List, New Price, Origin Codes)
        2. Tiene lógica especial para origin_code "44"
        3. Busca el precio máximo de múltiples new prices
        """
        logger.info("Iniciando comparación de datos Qxtel")

        vendor_name_upper = "QXTEL"

        # Filtrar datos maestros para Qxtel
        qxtel_master_data = [
            item for item in obr_master_data
            if item["vendor"].upper() == vendor_name_upper
        ]

        logger.info(f"Datos maestros Qxtel: {len(qxtel_master_data)} registros")

        list_to_send_in_csv = []

        # Procesar cada configuración de vendor en datos maestros
        for vendor in qxtel_master_data:
            destiny_code = str(vendor["destiny_code"])
            origin_code = str(vendor["origin_code"])
            routing = vendor["routing"]

            # Filtrar price_list por destiny_code (StartsWith)
            price_list_destinations = [
                item for item in price_list
                if item["dial_codes"].startswith(destiny_code)
            ]

            # Caso especial: origin_code == "44" (UK)
            if origin_code == "44":
                # Filtrar origin codes por origin_code (StartsWith)
                origins_filtered = [
                    origin for origin in origin_codes
                    if origin["origin_code"].startswith(origin_code)
                ]

                # Para cada origen filtrado, buscar new prices por OriginGroupDetail
                new_price_by_origin_list = []
                for origin in origins_filtered:
                    matching_new_prices = [
                        price for price in new_price_list
                        if price["origin_group_detail"] == origin["origin_group_detail"]
                    ]
                    new_price_by_origin_list.extend(matching_new_prices)

                # Para cada destino en price_list_destinations
                for price_item in price_list_destinations:
                    # Buscar new prices que coincidan con OriginGroup y OriginRegion
                    matching_new_prices = [
                        price for price in new_price_by_origin_list
                        if price["origin_group"] == price_item["origin_group"]
                        and price["origin_region"] == price_item["region"]
                    ]

                    if matching_new_prices:
                        # Obtener el de precio máximo
                        max_price_item = max(matching_new_prices, key=lambda x: x["rate"])

                        list_to_send_in_csv.append({
                            "destinations": price_item["region"],
                            "country_code": price_item["dial_codes"],
                            "area_code": "",
                            "country_area": price_item["dial_codes"],
                            "price_min": max_price_item["rate"],
                            "start_date": price_item["effective_date"] if price_item["effective_date"] else max_price_item["effective_date"],
                            "origin_name": routing
                        })

            else:
                # Caso normal: origin_code != "44"
                # Filtrar origin codes por origin_code (Equal)
                origins_filtered = [
                    origin for origin in origin_codes
                    if origin["origin_code"] == origin_code
                ]

                # Para cada origen filtrado, buscar new price por OriginGroup y OriginGroupDetail
                new_price_by_origin_list = []
                for origin in origins_filtered:
                    matching_new_price = next(
                        (price for price in new_price_list
                         if price["origin_group"] == origin["origin_group"]
                         and price["origin_group_detail"] == origin["origin_group_detail"]),
                        None
                    )
                    if matching_new_price:
                        new_price_by_origin_list.append(matching_new_price)

                # Para cada destino en price_list_destinations
                for price_item in price_list_destinations:
                    # Buscar new price que coincida con OriginGroup
                    matching_new_price = next(
                        (price for price in new_price_by_origin_list
                         if price["origin_group"] == price_item["origin_group"]),
                        None
                    )

                    if matching_new_price:
                        # Usar precio de new_price
                        list_to_send_in_csv.append({
                            "destinations": price_item["region"],
                            "country_code": price_item["dial_codes"],
                            "area_code": "",
                            "country_area": price_item["dial_codes"],
                            "price_min": matching_new_price["rate"],
                            "start_date": matching_new_price["effective_date"],
                            "origin_name": routing
                        })
                    else:
                        # Usar precio original de price_list
                        list_to_send_in_csv.append({
                            "destinations": price_item["region"],
                            "country_code": price_item["dial_codes"],
                            "area_code": "",
                            "country_area": price_item["dial_codes"],
                            "price_min": price_item["rate"],
                            "start_date": price_item["effective_date"],
                            "origin_name": routing
                        })

        # Agregar todos los items de price_list sin routing
        for price_item in price_list:
            list_to_send_in_csv.append({
                "destinations": price_item["region"],
                "country_code": price_item["dial_codes"],
                "area_code": "",
                "country_area": price_item["dial_codes"],
                "price_min": price_item["rate"],
                "start_date": price_item["effective_date"],
                "origin_name": ""  # Sin routing para destinos genéricos
            })

        logger.info(f"Comparación Qxtel completada: {len(list_to_send_in_csv)} registros para CSV")
        return list_to_send_in_csv

    def _compare_orange_france_platinum_data(
        self,
        price_list: List[Dict[str, Any]],
        origin_mapping: List[Dict[str, Any]],
        obr_master_data: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Compara datos de Orange France Platinum con datos maestros OBR
        Implementa la misma lógica que el backend .NET (GenerateOBROrangeFrancePlatinumFileDirect)

        Orange France Platinum:
        - 1 archivo con 2 hojas: "Rates" y "Origin Mapping"
        - DialCodes puede contener múltiples códigos separados por comas
        - Se debe hacer split y procesar cada dial code por separado
        """
        logger.info("Iniciando comparación de datos Orange France Platinum")

        vendor_name_upper = "ORANGE FRANCE PLATINUM"

        # Filtrar datos maestros para Orange France Platinum
        orange_master_data = [
            item for item in obr_master_data
            if item["vendor"].upper() == vendor_name_upper
        ]

        logger.info(f"Datos maestros Orange France Platinum: {len(orange_master_data)} registros")

        # Expandir price_list: split DialCodes por comas
        price_list_expanded = []
        for price in price_list:
            dial_codes = [code.strip() for code in price["dial_codes"].split(',')]
            for dial_code in dial_codes:
                if dial_code:  # Solo si no está vacío
                    price_list_expanded.append({
                        "destination": price["destination"],
                        "dial_codes": dial_code,
                        "origin": price["origin"],
                        "effective_date": price["effective_date"],
                        "rate": price["rate"]
                    })

        logger.info(f"Price list expandida: {len(price_list_expanded)} registros (split por comas)")

        list_to_send_in_csv = []
        unique_dial_codes = set()  # Para evitar duplicados

        # Procesar cada configuración de vendor en datos maestros
        for vendor in orange_master_data:
            origin_code = str(vendor["origin_code"])
            destiny_code = str(vendor["destiny_code"])
            routing = vendor["routing"]

            # Encontrar orígenes que coincidan con este origin_code (DialedDigit == origin_code)
            matching_origins = [
                origin for origin in origin_mapping
                if origin["dialed_digit"] == origin_code
            ]

            # Para cada origen que coincide
            for origin in matching_origins:
                origin_name = origin["origin_name"]

                # Encontrar entradas de price_list que coincidan:
                # - DialCodes.StartsWith(destiny_code)
                # - Origin == origin_name (si Origin no está vacío)
                matching_prices = [
                    price for price in price_list_expanded
                    if price["dial_codes"].startswith(destiny_code)
                ]

                # Filtrar por origin si no está vacío
                prices_with_origin = [
                    price for price in matching_prices
                    if price["origin"] and price["origin"] == origin_name
                ]

                # Si hay precios con origin, procesarlos
                if prices_with_origin:
                    for price_item in prices_with_origin:
                        dial_code = price_item["dial_codes"]

                        if dial_code and dial_code not in unique_dial_codes:
                            list_to_send_in_csv.append({
                                "destinations": price_item["destination"],
                                "country_code": dial_code,
                                "area_code": "",
                                "country_area": dial_code,
                                "price_min": price_item["rate"],
                                "start_date": price_item["effective_date"],
                                "origin_name": routing
                            })
                            unique_dial_codes.add(dial_code)
                else:
                    # Si no hay precios con origin, buscar precios sin origin
                    prices_without_origin = [
                        price for price in matching_prices
                        if not price["origin"]
                    ]

                    for price_item in prices_without_origin:
                        dial_code = price_item["dial_codes"]

                        if dial_code and dial_code not in unique_dial_codes:
                            list_to_send_in_csv.append({
                                "destinations": price_item["destination"],
                                "country_code": dial_code,
                                "area_code": "",
                                "country_area": dial_code,
                                "price_min": price_item["rate"],
                                "start_date": price_item["effective_date"],
                                "origin_name": routing
                            })
                            unique_dial_codes.add(dial_code)

        # Agregar todos los precios únicos de price_list sin routing
        # (para destinos sin origen específico)
        for price_item in price_list_expanded:
            dial_code = price_item["dial_codes"]

            if dial_code and dial_code not in unique_dial_codes:
                list_to_send_in_csv.append({
                    "destinations": price_item["destination"],
                    "country_code": dial_code,
                    "area_code": "",
                    "country_area": dial_code,
                    "price_min": price_item["rate"],
                    "start_date": price_item["effective_date"],
                    "origin_name": ""  # Sin routing para destinos genéricos
                })
                unique_dial_codes.add(dial_code)

        logger.info(f"Comparación Orange France Platinum completada: {len(list_to_send_in_csv)} registros para CSV")
        return list_to_send_in_csv

    def _compare_orange_france_win_data(
        self,
        price_list: List[Dict[str, Any]],
        origin_mapping: List[Dict[str, Any]],
        obr_master_data: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Compara datos de Orange France Win con datos maestros OBR
        IDÉNTICO a Orange France Platinum - misma lógica
        """
        logger.info("Iniciando comparación de datos Orange France Win")

        vendor_name_upper = "ORANGE FRANCE WIN AS"

        # Filtrar datos maestros para Orange France Win
        orange_master_data = [
            item for item in obr_master_data
            if item["vendor"].upper() == vendor_name_upper
        ]

        logger.info(f"Datos maestros Orange France Win: {len(orange_master_data)} registros")

        # Expandir price_list: split DialCodes por comas
        price_list_expanded = []
        for price in price_list:
            dial_codes = [code.strip() for code in price["dial_codes"].split(',')]
            for dial_code in dial_codes:
                if dial_code:  # Solo si no está vacío
                    price_list_expanded.append({
                        "destination": price["destination"],
                        "dial_codes": dial_code,
                        "origin": price["origin"],
                        "effective_date": price["effective_date"],
                        "rate": price["rate"]
                    })

        logger.info(f"Price list expandida: {len(price_list_expanded)} registros (split por comas)")

        list_to_send_in_csv = []
        unique_dial_codes = set()  # Para evitar duplicados

        # Procesar cada configuración de vendor en datos maestros
        for vendor in orange_master_data:
            origin_code = str(vendor["origin_code"])
            destiny_code = str(vendor["destiny_code"])
            routing = vendor["routing"]

            # Encontrar orígenes que coincidan con este origin_code (DialedDigit == origin_code)
            matching_origins = [
                origin for origin in origin_mapping
                if origin["dialed_digit"] == origin_code
            ]

            # Para cada origen que coincide
            for origin in matching_origins:
                origin_name = origin["origin_name"]

                # Encontrar entradas de price_list que coincidan
                matching_prices = [
                    price for price in price_list_expanded
                    if price["dial_codes"].startswith(destiny_code)
                ]

                # Filtrar por origin si no está vacío
                prices_with_origin = [
                    price for price in matching_prices
                    if price["origin"] and price["origin"] == origin_name
                ]

                # Si hay precios con origin, procesarlos
                if prices_with_origin:
                    for price_item in prices_with_origin:
                        dial_code = price_item["dial_codes"]

                        if dial_code and dial_code not in unique_dial_codes:
                            list_to_send_in_csv.append({
                                "destinations": price_item["destination"],
                                "country_code": dial_code,
                                "area_code": "",
                                "country_area": dial_code,
                                "price_min": price_item["rate"],
                                "start_date": price_item["effective_date"],
                                "origin_name": routing
                            })
                            unique_dial_codes.add(dial_code)
                else:
                    # Si no hay precios con origin, buscar precios sin origin
                    prices_without_origin = [
                        price for price in matching_prices
                        if not price["origin"]
                    ]

                    for price_item in prices_without_origin:
                        dial_code = price_item["dial_codes"]

                        if dial_code and dial_code not in unique_dial_codes:
                            list_to_send_in_csv.append({
                                "destinations": price_item["destination"],
                                "country_code": dial_code,
                                "area_code": "",
                                "country_area": dial_code,
                                "price_min": price_item["rate"],
                                "start_date": price_item["effective_date"],
                                "origin_name": routing
                            })
                            unique_dial_codes.add(dial_code)

        # Agregar todos los precios únicos de price_list sin routing
        for price_item in price_list_expanded:
            dial_code = price_item["dial_codes"]

            if dial_code and dial_code not in unique_dial_codes:
                list_to_send_in_csv.append({
                    "destinations": price_item["destination"],
                    "country_code": dial_code,
                    "area_code": "",
                    "country_area": dial_code,
                    "price_min": price_item["rate"],
                    "start_date": price_item["effective_date"],
                    "origin_name": ""  # Sin routing para destinos genéricos
                })
                unique_dial_codes.add(dial_code)

        logger.info(f"Comparación Orange France Win completada: {len(list_to_send_in_csv)} registros para CSV")
        return list_to_send_in_csv

    def _compare_ibasis_data(
        self,
        price_list: List[Dict[str, Any]],
        origin_mapping: List[Dict[str, Any]],
        obr_master_data: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Compara datos de Ibasis con datos maestros OBR
        Implementa la misma lógica que el backend .NET (GenerateOBRIbasisFile)

        Ibasis:
        - Matching por CountryCode == destiny_code
        - Matching por DialedDigit == origin_code
        - Matching por Origin == OriginBased
        """
        logger.info("Iniciando comparación de datos Ibasis")

        vendor_name_upper = "IBASIS GLOBAL INC PREMIUM"

        # Filtrar datos maestros para Ibasis
        ibasis_master_data = [
            item for item in obr_master_data
            if item["vendor"].upper() == vendor_name_upper
        ]

        logger.info(f"Datos maestros Ibasis: {len(ibasis_master_data)} registros")

        list_to_send_in_csv = []

        # Procesar cada configuración de vendor en datos maestros
        for vendor in ibasis_master_data:
            origin_code = str(vendor["origin_code"])
            destiny_code = str(vendor["destiny_code"])
            routing = vendor["routing"]

            # Encontrar precios que coincidan con destiny_code (CountryCode == destiny_code)
            data_with_origin_by_destiny = [
                price for price in price_list
                if price["country_code"] == destiny_code
            ]

            if data_with_origin_by_destiny:
                # Encontrar orígenes que coincidan con origin_code (DialedDigit == origin_code)
                origin_ibasis_by_vendor_origin = [
                    origin for origin in origin_mapping
                    if origin["dialed_digit"] == origin_code
                ]

                # Para cada origen encontrado
                for origin in origin_ibasis_by_vendor_origin:
                    origin_based = origin["origin_based"]

                    # Encontrar precios que coincidan con Origin == OriginBased
                    data_with_origin_by_destiny_and_origin = [
                        price for price in data_with_origin_by_destiny
                        if price["origin"] == origin_based
                    ]

                    # Añadir precios encontrados al CSV
                    for price in data_with_origin_by_destiny_and_origin:
                        list_to_send_in_csv.append({
                            "destinations": price["destination"],
                            "country_code": price["dial_codes"],
                            "area_code": "",
                            "country_area": price["dial_codes"],
                            "price_min": price["rate"],
                            "start_date": price["effective_date"],
                            "origin_name": routing
                        })

        # Agregar todos los precios sin routing
        for price in price_list:
            list_to_send_in_csv.append({
                "destinations": price["destination"],
                "country_code": price["dial_codes"],
                "area_code": "",
                "country_area": price["dial_codes"],
                "price_min": price["rate"],
                "start_date": price["effective_date"],
                "origin_name": ""
            })

        logger.info(f"Comparación Ibasis completada: {len(list_to_send_in_csv)} registros para CSV")
        return list_to_send_in_csv

    def _compare_hgc_data(
        self,
        price_list: List[Dict[str, Any]],
        origin_mapping: List[Dict[str, Any]],
        obr_master_data: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Compara datos de HGC con datos maestros OBR
        LÓGICA ESPECIAL: Si routing == "obr 1" Y origin_code == "44" Y dial_code.startswith("44"):
        - Buscar max rate de todos los items con mismo destination que empiecen con "44"
        """
        logger.info("Iniciando comparación de datos HGC Premium")

        vendor_name_upper = "HGC PREMIUM"

        # Filtrar datos maestros para HGC
        hgc_master_data = [
            item for item in obr_master_data
            if item["vendor"].upper() == vendor_name_upper
        ]

        logger.info(f"Datos maestros HGC: {len(hgc_master_data)} registros")

        list_to_send_in_csv = []
        unique_dial_codes = set()

        # Procesar cada configuración de vendor en datos maestros
        for vendor in hgc_master_data:
            origin_code = str(vendor["origin_code"])
            destiny_code = str(vendor["destiny_code"])
            routing = vendor["routing"]

            # Encontrar precios que coincidan con destiny_code (DialCode.StartsWith)
            price_list_for_compare = [
                price for price in price_list
                if price["dial_code"].strip().startswith(destiny_code)
            ]

            for price in price_list_for_compare:
                dial_code = price["dial_code"]

                # CASO ESPECIAL: routing == "obr 1" Y origin_code == "44" Y dial_code.startswith("44")
                if (routing.lower() == "obr 1" and origin_code == "44" and dial_code.startswith("44")):
                    # Solo procesar si routing está vacío
                    if not price["routing"]:
                        # Buscar todos los items con mismo destination que empiecen con "44"
                        same_dial_codes_by_origin = [
                            p for p in price_list
                            if p["dial_code"].strip().startswith("44")
                            and p["destination"].lower() == price["destination"].lower()
                        ]

                        if same_dial_codes_by_origin:
                            # Encontrar el de mayor rate
                            max_price_item = max(same_dial_codes_by_origin, key=lambda x: x["rate"])

                            if dial_code not in unique_dial_codes:
                                list_to_send_in_csv.append({
                                    "destinations": max_price_item["destination"],
                                    "country_code": dial_code,
                                    "area_code": "",
                                    "country_area": dial_code,
                                    "price_min": max_price_item["rate"],
                                    "start_date": max_price_item["effective_date"],
                                    "origin_name": routing
                                })
                                unique_dial_codes.add(dial_code)
                else:
                    # CASO NORMAL: sin lógica especial "44"
                    if not price["routing"]:
                        # Routing vacío - añadir con routing del vendor
                        list_to_send_in_csv.append({
                            "destinations": price["destination"],
                            "country_code": dial_code,
                            "area_code": "",
                            "country_area": dial_code,
                            "price_min": price["rate"],
                            "start_date": price["effective_date"],
                            "origin_name": routing
                        })
                    else:
                        # Tiene routing - matching con origin_mapping
                        if dial_code not in unique_dial_codes:
                            # Buscar prices con mismo dial_code
                            same_dial_codes = [
                                p for p in price_list_for_compare
                                if p["dial_code"] == dial_code
                            ]

                            # Buscar origins que coincidan
                            origin_hgc_data_to_compare = [
                                origin for origin in origin_mapping
                                if origin["dialed_digit"] == origin_code
                            ]

                            for same_dial in same_dial_codes:
                                # Verificar si existe origin que coincida con routing
                                origin_exist = next(
                                    (origin for origin in origin_hgc_data_to_compare
                                     if same_dial["routing"] == origin["origin_name"]),
                                    None
                                )

                                if origin_exist:
                                    list_to_send_in_csv.append({
                                        "destinations": same_dial["destination"],
                                        "country_code": dial_code,
                                        "area_code": "",
                                        "country_area": dial_code,
                                        "price_min": same_dial["rate"],
                                        "start_date": same_dial["effective_date"],
                                        "origin_name": routing
                                    })

                            unique_dial_codes.add(dial_code)

        # Agregar todos los precios sin routing
        for price in price_list:
            list_to_send_in_csv.append({
                "destinations": price["destination"],
                "country_code": price["dial_code"],
                "area_code": "",
                "country_area": price["dial_code"],
                "price_min": price["rate"],
                "start_date": price["effective_date"],
                "origin_name": ""
            })

        logger.info(f"Comparación HGC completada: {len(list_to_send_in_csv)} registros para CSV")
        return list_to_send_in_csv

    async def process_oteglobe_file(
        self,
        file_content: bytes,
        file_name: str,
        user_email: str
    ):
        """
        Procesa archivo de Oteglobe con 3 hojas:
        - OTEGLOBE Voice Rates (PriceList)
        - Origin Rates (NewPrice)
        - Origin DialCodes (Origins)

        Lógica de comparación:
        1. Match origins por DialCode == origin_code
        2. Match new_prices por Origin == origin.Origin AND DialCode.StartsWith(destiny_code)
        3. Match price_list por DialCode.StartsWith(destiny_code)
        4. Preferir precio de NewPrice si existe, sino usar PriceList
        """
        try:
            logger.info(f"[OTEGLOBE] Iniciando procesamiento: {file_name}")

            # Guardar archivo temporal
            temp_file_path = self.file_manager.save_temp_file(file_content, file_name)

            # Leer las 3 hojas del archivo
            price_list = self.excel_service.read_oteglobe_price_list(temp_file_path)
            new_price_list = self.excel_service.read_oteglobe_new_price(temp_file_path)
            origins = self.excel_service.read_oteglobe_origins(temp_file_path)

            logger.info(f"[OTEGLOBE] Datos leídos - PriceList: {len(price_list)}, NewPrice: {len(new_price_list)}, Origins: {len(origins)}")

            # Obtener OBR Master Data (con cache)
            obr_master_data = await self._get_obr_master_data_cached()

            # Comparar datos
            csv_data = self._compare_oteglobe_data(
                price_list=price_list,
                new_price_list=new_price_list,
                origins=origins,
                obr_master_data=obr_master_data
            )

            # Generar y enviar CSV
            csv_file_path = self._generate_csv_file(csv_data, "Oteglobe")
            await self.email_service.send_obr_email(
                to_email=user_email,
                vendor_name="Oteglobe",
                csv_file_path=csv_file_path,
                success=True
            )

            # Limpiar archivo temporal
            self.file_manager.cleanup_temp_file(temp_file_path)
            self.file_manager.cleanup_temp_file(csv_file_path)

            logger.info(f"[OTEGLOBE] Procesamiento completado exitosamente")

        except Exception as e:
            logger.error(f"[OTEGLOBE] Error en procesamiento: {e}", exc_info=True)
            await self.email_service.send_obr_email(
                to_email=user_email,
                vendor_name="Oteglobe",
                csv_file_path=None,
                success=False,
                error_message=str(e)
            )

    def _compare_oteglobe_data(
        self,
        price_list: List[Dict[str, Any]],
        new_price_list: List[Dict[str, Any]],
        origins: List[Dict[str, Any]],
        obr_master_data: List[Dict[str, Any]],
        vendor_name: str = "OTEGLOBE"
    ) -> List[Dict[str, Any]]:
        """
        Compara datos de Oteglobe/Deutsche con OBR Master Data

        Lógica:
        1. Filtrar OBR Master Data para vendor especificado
        2. Para cada vendor en OBR:
           a. Buscar origins que coincidan con origin_code
           b. Para cada origin, buscar new_prices con Origin == origin.Origin AND DialCode.StartsWith(destiny_code)
           c. Filtrar new_prices por Destination.Contains(destiny)
           d. Buscar price_list items con DialCode.StartsWith(destiny_code)
           e. Para cada price_list item:
              - Si existe new_price con mismo DialCode, usar ese rate
              - Sino, usar rate del price_list
        3. Añadir todos los price_list items sin routing al final
        """
        import re
        list_to_send_in_csv = []
        unique_dial_codes = set()

        # Filtrar OBR Master Data para el vendor especificado
        vendor_master_data = [
            vendor for vendor in obr_master_data
            if vendor["vendor"].upper() == vendor_name.upper()
        ]

        logger.info(f"{vendor_name} Master Data filtrado: {len(vendor_master_data)} registros")

        for vendor in vendor_master_data:
            origin_code = str(vendor["origin_code"])
            destiny_code = str(vendor["destiny_code"])
            destiny = vendor["destiny"]
            routing = vendor["routing"]

            # Buscar origins que coincidan con origin_code
            matching_origins = [
                origin for origin in origins
                if origin["dial_code"] == origin_code
            ]

            available_prices = []

            # Para cada origin, buscar new_prices
            for origin in matching_origins:
                origin_name = origin["origin"]

                # Buscar new_prices con Origin == origin_name AND DialCode.StartsWith(destiny_code)
                origin_available = [
                    price for price in new_price_list
                    if price["origin"] == origin_name and price["dial_code"].startswith(destiny_code)
                ]

                available_prices.extend(origin_available)

            # Filtrar available_prices por Destination.Contains(destiny)
            available_prices_by_destiny = [
                price for price in available_prices
                if destiny.upper() in price["destination"].upper()
            ]

            # Buscar price_list items con DialCode.StartsWith(destiny_code)
            price_list_destinations = [
                price for price in price_list
                if price["dial_code"].startswith(destiny_code)
            ]

            # Para cada price_list item
            for item in price_list_destinations:
                dial_code = item["dial_code"]
                # Limpiar dial_code de caracteres no numéricos
                dial_code_clean = re.sub(r'[^0-9]', '', dial_code)

                # Buscar new_price con mismo dial_code
                new_price = next(
                    (price for price in available_prices_by_destiny if price["dial_code"] == dial_code_clean),
                    None
                )

                if new_price:
                    # Usar precio de NewPrice
                    if dial_code not in unique_dial_codes:
                        unique_dial_codes.add(dial_code)
                        list_to_send_in_csv.append({
                            "destinations": item["destination"],
                            "country_code": dial_code,
                            "area_code": "",
                            "country_area": dial_code,
                            "price_min": new_price["rate"],
                            "start_date": new_price["effective_date"],
                            "origin_name": routing
                        })
                else:
                    # Usar precio de PriceList
                    if dial_code not in unique_dial_codes:
                        unique_dial_codes.add(dial_code)
                        list_to_send_in_csv.append({
                            "destinations": item["destination"],
                            "country_code": dial_code,
                            "area_code": "",
                            "country_area": dial_code,
                            "price_min": item["rate"],
                            "start_date": item["effective_date"],
                            "origin_name": routing
                        })

        # Añadir todos los price_list items sin routing
        for price_item in price_list:
            dial_code = price_item["dial_code"]

            if dial_code not in unique_dial_codes:
                unique_dial_codes.add(dial_code)
                list_to_send_in_csv.append({
                    "destinations": price_item["destination"],
                    "country_code": dial_code,
                    "area_code": "",
                    "country_area": dial_code,
                    "price_min": price_item["rate"],
                    "start_date": price_item["effective_date"],
                    "origin_name": ""
                })

        logger.info(f"Comparación {vendor_name} completada: {len(list_to_send_in_csv)} registros para CSV")
        return list_to_send_in_csv

    async def process_arelion_file(
        self,
        file_content: bytes,
        file_name: str,
        user_email: str
    ):
        """
        Procesa archivo de Arelion con 3 hojas:
        - Rates (PriceList)
        - Origin Rates (NewPrice)
        - Origin Definitions (Origins)

        DIFERENCIA CON OTEGLOBE:
        - Usa Destination.Contains() en lugar de DialCode.StartsWith() para matching de price_list
        - NO filtra new_prices por DialCode.StartsWith() al buscar por origin
        """
        try:
            logger.info(f"[ARELION] Iniciando procesamiento: {file_name}")

            # Guardar archivo temporal
            temp_file_path = self.file_manager.save_temp_file(file_content, file_name)

            # Leer las 3 hojas del archivo
            price_list = self.excel_service.read_arelion_price_list(temp_file_path)
            new_price_list = self.excel_service.read_arelion_new_price(temp_file_path)
            origins = self.excel_service.read_arelion_origins(temp_file_path)

            logger.info(f"[ARELION] Datos leídos - PriceList: {len(price_list)}, NewPrice: {len(new_price_list)}, Origins: {len(origins)}")

            # Obtener OBR Master Data (con cache)
            obr_master_data = await self._get_obr_master_data_cached()

            # Comparar datos
            csv_data = self._compare_arelion_data(
                price_list=price_list,
                new_price_list=new_price_list,
                origins=origins,
                obr_master_data=obr_master_data
            )

            # Generar y enviar CSV
            csv_file_path = self._generate_csv_file(csv_data, "Arelion")
            await self.email_service.send_obr_email(
                to_email=user_email,
                vendor_name="Arelion",
                csv_file_path=csv_file_path,
                success=True
            )

            # Limpiar archivo temporal
            self.file_manager.cleanup_temp_file(temp_file_path)
            self.file_manager.cleanup_temp_file(csv_file_path)

            logger.info(f"[ARELION] Procesamiento completado exitosamente")

        except Exception as e:
            logger.error(f"[ARELION] Error en procesamiento: {e}", exc_info=True)
            await self.email_service.send_obr_email(
                to_email=user_email,
                vendor_name="Arelion",
                csv_file_path=None,
                success=False,
                error_message=str(e)
            )

    def _compare_arelion_data(
        self,
        price_list: List[Dict[str, Any]],
        new_price_list: List[Dict[str, Any]],
        origins: List[Dict[str, Any]],
        obr_master_data: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Compara datos de Arelion con OBR Master Data

        DIFERENCIAS CON OTEGLOBE:
        1. NO filtra new_prices por DialCode.StartsWith() cuando busca por origin
        2. Usa Destination.Contains() en lugar de DialCode.StartsWith() para matching de price_list

        Lógica:
        1. Filtrar OBR Master Data para vendor "ARELION"
        2. Para cada vendor en OBR:
           a. Buscar origins que coincidan con origin_code
           b. Para cada origin, buscar new_prices con Origin == origin.Origin (SIN filtrar por DialCode)
           c. Filtrar new_prices por Destination.Contains(destiny)
           d. Buscar price_list items con Destination.Contains(destiny) (NO DialCode.StartsWith!)
           e. Para cada price_list item:
              - Si existe new_price con mismo DialCode, usar ese rate
              - Sino, usar rate del price_list
        3. Añadir todos los price_list items sin routing al final
        """
        import re
        list_to_send_in_csv = []
        unique_dial_codes = set()

        # Filtrar OBR Master Data para Arelion
        arelion_master_data = [
            vendor for vendor in obr_master_data
            if vendor["vendor"].upper() == "ARELION"
        ]

        logger.info(f"Arelion Master Data filtrado: {len(arelion_master_data)} registros")

        for vendor in arelion_master_data:
            origin_code = str(vendor["origin_code"])
            destiny = vendor["destiny"]
            routing = vendor["routing"]

            # Buscar origins que coincidan con origin_code
            matching_origins = [
                origin for origin in origins
                if origin["dial_code"] == origin_code
            ]

            available_prices = []

            # Para cada origin, buscar new_prices
            for origin in matching_origins:
                origin_name = origin["origin"]

                # DIFERENCIA CON OTEGLOBE: NO filtramos por DialCode.StartsWith()
                origin_available = [
                    price for price in new_price_list
                    if price["origin"] == origin_name
                ]

                available_prices.extend(origin_available)

            # Filtrar available_prices por Destination.Contains(destiny)
            available_prices_by_destiny = [
                price for price in available_prices
                if destiny.upper() in price["destination"].upper()
            ]

            # DIFERENCIA CON OTEGLOBE: Buscar price_list items con Destination.Contains()
            price_list_destinations = [
                price for price in price_list
                if destiny.upper() in price["destination"].upper()
            ]

            # Para cada price_list item
            for item in price_list_destinations:
                dial_code = item["dial_code"]
                # Limpiar dial_code de caracteres no numéricos
                dial_code_clean = re.sub(r'[^0-9]', '', dial_code)

                # Buscar new_price con mismo dial_code
                new_price = next(
                    (price for price in available_prices_by_destiny if price["dial_code"] == dial_code_clean),
                    None
                )

                if new_price:
                    # Usar precio de NewPrice
                    if dial_code not in unique_dial_codes:
                        unique_dial_codes.add(dial_code)
                        list_to_send_in_csv.append({
                            "destinations": item["destination"],
                            "country_code": dial_code,
                            "area_code": "",
                            "country_area": dial_code,
                            "price_min": new_price["rate"],
                            "start_date": new_price["effective_date"],
                            "origin_name": routing
                        })
                else:
                    # Usar precio de PriceList
                    if dial_code not in unique_dial_codes:
                        unique_dial_codes.add(dial_code)
                        list_to_send_in_csv.append({
                            "destinations": item["destination"],
                            "country_code": dial_code,
                            "area_code": "",
                            "country_area": dial_code,
                            "price_min": item["rate"],
                            "start_date": item["effective_date"],
                            "origin_name": routing
                        })

        # Añadir todos los price_list items sin routing
        for price_item in price_list:
            dial_code = price_item["dial_code"]

            if dial_code not in unique_dial_codes:
                unique_dial_codes.add(dial_code)
                list_to_send_in_csv.append({
                    "destinations": price_item["destination"],
                    "country_code": dial_code,
                    "area_code": "",
                    "country_area": dial_code,
                    "price_min": price_item["rate"],
                    "start_date": price_item["effective_date"],
                    "origin_name": ""
                })

        logger.info(f"Comparación Arelion completada: {len(list_to_send_in_csv)} registros para CSV")
        return list_to_send_in_csv

    async def process_deutsche_file(self, file_content: bytes, file_name: str, user_email: str):
        """Procesa Deutsche Telecom - lógica idéntica a Oteglobe"""
        try:
            logger.info(f"[DEUTSCHE] Iniciando procesamiento: {file_name}")
            temp_file_path = self.file_manager.save_temp_file(file_content, file_name)

            price_list = self.excel_service.read_deutsche_price_list(temp_file_path)
            new_price_list = self.excel_service.read_deutsche_new_price(temp_file_path)
            origins = self.excel_service.read_deutsche_origins(temp_file_path)
            logger.info(f"[DEUTSCHE] Datos leídos - PriceList: {len(price_list)}, NewPrice: {len(new_price_list)}, Origins: {len(origins)}")

            obr_master_data = await self._get_obr_master_data_cached()
            csv_data = self._compare_oteglobe_data(price_list, new_price_list, origins, obr_master_data, vendor_name="DEUTSCHE TELECOM")

            csv_file_path = self._generate_csv_file(csv_data, "Deutsche Telecom")
            await self.email_service.send_obr_email(to_email=user_email, vendor_name="Deutsche Telecom", csv_file_path=csv_file_path, success=True)

            self.file_manager.cleanup_temp_file(temp_file_path)
            self.file_manager.cleanup_temp_file(csv_file_path)
            logger.info(f"[DEUTSCHE] Procesamiento completado")
        except Exception as e:
            logger.error(f"[DEUTSCHE] Error: {e}", exc_info=True)
            await self.email_service.send_obr_email(to_email=user_email, vendor_name="Deutsche Telecom", csv_file_path=None, success=False, error_message=str(e))

    async def process_orange_telecom_file(self, file_content: bytes, file_name: str, user_email: str):
        """Procesa Orange Telecom"""
        try:
            logger.info(f"[ORANGE TELECOM] Iniciando: {file_name}")
            temp_file_path = self.file_manager.save_temp_file(file_content, file_name)
            price_list = self.excel_service.read_orange_telecom_price_list(temp_file_path)
            new_price_list = self.excel_service.read_orange_telecom_new_price(temp_file_path)
            origins = self.excel_service.read_orange_telecom_origins(temp_file_path)
            logger.info(f"[ORANGE TELECOM] Leído - PL:{len(price_list)}, NP:{len(new_price_list)}, OR:{len(origins)}")
            obr_master_data = await self._get_obr_master_data_cached()
            csv_data = self._compare_orange_telecom_data(price_list, new_price_list, origins, obr_master_data)
            csv_file_path = self._generate_csv_file(csv_data, "Orange Telecom")
            await self.email_service.send_obr_email(user_email, "Orange Telecom", csv_file_path, True)
            self.file_manager.cleanup_temp_file(temp_file_path)
            self.file_manager.cleanup_temp_file(csv_file_path)
            logger.info(f"[ORANGE TELECOM] Completado")
        except Exception as e:
            logger.error(f"[ORANGE TELECOM] Error: {e}", exc_info=True)
            await self.email_service.send_obr_email(user_email, "Orange Telecom", None, False, str(e))

    def _compare_orange_telecom_data(self, price_list, new_price_list, origins, obr_master_data):
        """Orange Telecom: Code.StartsWith, Origin.Contains + OriginCode match"""
        list_to_send_in_csv, unique_codes = [], set()
        vendor_data = [v for v in obr_master_data if v["vendor"].upper() == "ORANGE TELECOM"]
        for vendor in vendor_data:
            destiny_code, destiny, origin_code, routing = str(vendor["destiny_code"]), vendor["destiny"], vendor["origin_code"], vendor["routing"]
            prices_filtered = [p for p in price_list if p["code"].startswith(destiny_code)]
            origins_filtered = [o for o in origins if destiny.upper() in o["origin"].upper() and o["origin_code"] == origin_code]
            available_new_prices = []
            for origin in origins_filtered:
                available_new_prices.extend([np for np in new_price_list if np["origin_group"] == origin["origin"]])
            for item in prices_filtered:
                new_price = next((np for np in available_new_prices if np["destination"] == item["destination"]), None)
                code = item["code"]
                if code not in unique_codes:
                    unique_codes.add(code)
                    list_to_send_in_csv.append({"destinations": item["destination"], "country_code": code, "area_code": "", "country_area": code, "price_min": new_price["new_rate"] if new_price else item["rate"], "start_date": new_price["effective_date"] if new_price else item["effective_date"], "origin_name": routing})
        for item in price_list:
            if item["code"] not in unique_codes:
                unique_codes.add(item["code"])
                list_to_send_in_csv.append({"destinations": item["destination"], "country_code": item["code"], "area_code": "", "country_area": item["code"], "price_min": item["rate"], "start_date": item["effective_date"], "origin_name": ""})
        logger.info(f"Orange Telecom: {len(list_to_send_in_csv)} registros")
        return list_to_send_in_csv

    async def process_apelby_file(self, file_content: bytes, file_name: str, user_email: str):
        """Procesa Apelby"""
        try:
            logger.info(f"[APELBY] Iniciando: {file_name}")
            temp_file_path = self.file_manager.save_temp_file(file_content, file_name)
            price_list = self.excel_service.read_apelby_price_list(temp_file_path)
            new_price_list = self.excel_service.read_apelby_new_price(temp_file_path)
            origins = self.excel_service.read_apelby_origins(temp_file_path)
            logger.info(f"[APELBY] Leído - PL:{len(price_list)}, NP:{len(new_price_list)}, OR:{len(origins)}")
            obr_master_data = await self._get_obr_master_data_cached()
            csv_data = self._compare_apelby_data(price_list, new_price_list, origins, obr_master_data)
            csv_file_path = self._generate_csv_file(csv_data, "Apelby")
            await self.email_service.send_obr_email(user_email, "Apelby", csv_file_path, True)
            self.file_manager.cleanup_temp_file(temp_file_path)
            self.file_manager.cleanup_temp_file(csv_file_path)
            logger.info(f"[APELBY] Completado")
        except Exception as e:
            logger.error(f"[APELBY] Error: {e}", exc_info=True)
            await self.email_service.send_obr_email(user_email, "Apelby", None, False, str(e))

    def _compare_apelby_data(self, price_list, new_price_list, origins, obr_master_data):
        """Apelby: Split Code por comas"""
        import re
        list_to_send_in_csv, unique_codes = [], set()
        vendor_data = [v for v in obr_master_data if v["vendor"].upper() == "APELBY"]
        for vendor in vendor_data:
            origin_code, destiny_code, routing = vendor["origin_code"], str(vendor["destiny_code"]), vendor["routing"]
            matching_origins = [o for o in origins if o["origin_code"] == origin_code]
            available_prices = []
            for origin in matching_origins:
                available_prices.extend([p for p in new_price_list if p["origin"] == origin["origin"] and p["dial_code"].startswith(destiny_code)])
            price_list_destinations = [p for p in price_list if any(code.strip().startswith(destiny_code) for code in p["code"].split(','))]
            for item in price_list_destinations:
                codes = [c.strip() for c in item["code"].split(',')]
                for code in codes:
                    code_clean = re.sub(r'[^0-9]', '', code)
                    new_price = next((p for p in available_prices if p["dial_code"] == code_clean), None)
                    if code not in unique_codes:
                        unique_codes.add(code)
                        list_to_send_in_csv.append({"destinations": item["destination"], "country_code": code, "area_code": "", "country_area": code, "price_min": new_price["rate"] if new_price else item["rate"], "start_date": new_price["effective_date"] if new_price else item["effective_date"], "origin_name": routing})
        for item in price_list:
            for code in [c.strip() for c in item["code"].split(',')]:
                if code not in unique_codes:
                    unique_codes.add(code)
                    list_to_send_in_csv.append({"destinations": item["destination"], "country_code": code, "area_code": "", "country_area": code, "price_min": item["rate"], "start_date": item["effective_date"], "origin_name": ""})
        logger.info(f"Apelby: {len(list_to_send_in_csv)} registros")
        return list_to_send_in_csv

    async def process_phonetic_file(self, file_content: bytes, file_name: str, user_email: str):
        """Procesa Phonetic Limited (idéntico a Apelby)"""
        try:
            logger.info(f"[PHONETIC] Iniciando: {file_name}")
            temp_file_path = self.file_manager.save_temp_file(file_content, file_name)
            price_list = self.excel_service.read_phonetic_price_list(temp_file_path)
            new_price_list = self.excel_service.read_phonetic_new_price(temp_file_path)
            origins = self.excel_service.read_phonetic_origins(temp_file_path)
            logger.info(f"[PHONETIC] Leído - PL:{len(price_list)}, NP:{len(new_price_list)}, OR:{len(origins)}")
            obr_master_data = await self._get_obr_master_data_cached()
            csv_data = self._compare_apelby_data(price_list, new_price_list, origins, obr_master_data)
            csv_file_path = self._generate_csv_file(csv_data, "Phonetic Limited")
            await self.email_service.send_obr_email(user_email, "Phonetic Limited", csv_file_path, True)
            self.file_manager.cleanup_temp_file(temp_file_path)
            self.file_manager.cleanup_temp_file(csv_file_path)
            logger.info(f"[PHONETIC] Completado")
        except Exception as e:
            logger.error(f"[PHONETIC] Error: {e}", exc_info=True)
            await self.email_service.send_obr_email(user_email, "Phonetic Limited", None, False, str(e))

    def _generate_csv_file(
        self,
        csv_data: List[Dict[str, Any]],
        vendor_name: str
    ) -> str:
        """
        Genera archivo CSV con los resultados
        """
        timestamp = datetime.now().strftime("%m_%d_%Y")
        file_name = f"{vendor_name}-{timestamp}.csv"
        file_path = self.file_manager.get_temp_file_path(file_name)

        try:
            with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)

                # Header
                writer.writerow([
                    "CountryCode - Destination",
                    "Country Code",
                    "Area Code",
                    "Country Area",
                    "Price",
                    "Effective Date",
                    "Routing"
                ])

                # Data rows
                for item in csv_data:
                    writer.writerow([
                        item["destinations"],
                        item["country_code"],
                        item["area_code"],
                        item["country_area"],
                        item["price_min"],
                        item["start_date"],
                        item["origin_name"]
                    ])

            logger.info(f"CSV generado exitosamente: {file_path}")
            return file_path

        except Exception as e:
            logger.error(f"Error generando CSV: {e}")
            raise
