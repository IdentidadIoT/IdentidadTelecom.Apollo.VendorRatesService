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
        Parsea y separa códigos de marcación.
        Replica exactamente el comportamiento de ParseAndSplit en C#:
        Split por ';' y '-' como separadores simples (sin expansión de rangos).

        C# original (ProcessRatesByCustomerBusiness.cs:6061):
            char[] separators = { ';', '-' };
            string[] parts = input.Split(separators, StringSplitOptions.RemoveEmptyEntries);
        """
        import re
        parts = re.split(r'[;\-]', dial_codes_str)
        return [p.strip() for p in parts if p.strip()]

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
                vendor_name="Belgacom Platinum",
                use_variable_decimals=True
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
        user_email: str,
        max_line: int = None
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

            # C# usa upload.MaxLine para limitar filas del Excel
            # (ReadSunriseVendorRates, línea 7546: int lastRow = upload.MaxLine)
            # C# loop: for (int i = 14; i < lastRow; i++) → lee MaxLine - 14 filas
            # max_line viene del request (frontend); si no, intentar de BD como fallback
            if max_line is None:
                max_line = self.repository.get_vendor_max_line("Sunrise")
            if max_line is not None:
                expected_count = max_line - 14
                if len(price_list) > expected_count:
                    logger.info(
                        f"[Sunrise] Truncando price_list de {len(price_list)} a "
                        f"{expected_count} registros (MaxLine={max_line})"
                    )
                    price_list = price_list[:expected_count]

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
            # C# GenerateOBRSunriseFile usa header "OriginCode" (no "Routing")
            csv_file_path = self._generate_csv_file(
                csv_data=csv_data,
                vendor_name="Sunrise",
                decimal_places=4,
                use_variable_decimals=False,
                origin_column_header="OriginCode"
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

            # 6. Generar archivo CSV (con decimales variables, igual que Belgacom)
            csv_file_path = self._generate_csv_file(
                csv_data=csv_data,
                vendor_name="Qxtel",
                use_variable_decimals=True
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
            # C# GenerateOBROrangeFrancePlatinumFile usa header "Origin"
            csv_file_path = self._generate_csv_file(
                csv_data=csv_data,
                vendor_name="Orange France Platinum",
                decimal_places=6,
                origin_column_header="Origin"
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
            # C# GenerateOBROrangeFranceWinFile usa header "OriginCode"
            csv_file_path = self._generate_csv_file(
                csv_data=csv_data,
                vendor_name="Orange France Win",
                decimal_places=6,
                origin_column_header="OriginCode"
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

            # 6. Generar archivo CSV con formato específico de HGC
            csv_file_path = self._generate_csv_file_hgc(
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
        OPTIMIZADO: Usa índices en memoria para O(1) lookups
        """
        logger.info("Iniciando comparación de datos Belgacom (optimizada)")

        vendor_name_upper = "BELGACOM PLATINUM"

        # Filtrar datos maestros para Belgacom
        belgacom_master_data = [
            item for item in obr_master_data
            if item["vendor"].upper() == vendor_name_upper
        ]

        logger.info(f"Datos maestros Belgacom: {len(belgacom_master_data)} registros")

        # OPTIMIZACIÓN 1: Indexar price_list por country_code para O(1) lookup
        price_list_index = {}
        for item in price_list:
            code = item["country_code"]
            if code not in price_list_index:
                price_list_index[code] = []
            price_list_index[code].append(item)
        logger.info(f"Índice de price_list creado: {len(price_list_index)} códigos únicos")

        # OPTIMIZACIÓN 2: Indexar anumber_pricing por (origin, reference_destinations)
        anumber_index = {}
        for item in anumber_pricing:
            key = (item["origin"], item["reference_destinations"])
            anumber_index[key] = item
        logger.info(f"Índice de anumber_pricing creado: {len(anumber_index)} combinaciones")

        # OPTIMIZACIÓN 3: Pre-calcular caso especial Italy Mobile TIM
        italy_mobile_items = [
            item for item in anumber_pricing
            if (item["origin"].startswith("4") or item["origin"].startswith("3"))
            and item["reference_destinations"].lower() == "italy mobile tim"
        ]
        italy_mobile_max = max(italy_mobile_items, key=lambda x: x["price_min"]) if italy_mobile_items else None

        list_to_send_in_csv = []

        # Procesar cada configuración de vendor en datos maestros
        for vendor in belgacom_master_data:
            destiny_code = str(vendor["destiny_code"])
            origin_code = str(vendor["origin_code"])
            routing = vendor["routing"]
            destiny_upper = vendor["destiny"].upper()

            # Lookup O(1) en vez de filter O(n)
            price_list_destinations = price_list_index.get(destiny_code, [])

            # Pre-filtrar items con mismo origen (solo una vez por vendor)
            items_with_same_origin = [
                item for item in anumber_pricing
                if destiny_upper in item["reference_destinations"].upper()
                and item["origin"] == origin_code
            ]

            # Procesar cada item de price_list_destinations
            for price_item in price_list_destinations:
                destinations = price_item["destinations"]

                # Caso especial: "traffic from eu" + Italia + Andorra + "italy mobile tim"
                if (routing.lower() == "traffic from eu"
                    and destiny_code == "39"
                    and origin_code == "376"
                    and destinations.lower() == "italy mobile tim"):

                    if italy_mobile_max:
                        list_to_send_in_csv.append({
                            "destinations": destinations,
                            "country_code": price_item["country_code"],
                            "area_code": price_item["area_code"],
                            "country_area": price_item["country_area"],
                            "price_min": italy_mobile_max["price_min"],
                            "start_date": italy_mobile_max["start_date"],
                            "origin_name": routing
                        })

                else:
                    # Caso normal: Lookup O(1) en índice
                    matching_item = anumber_index.get((origin_code, destinations))

                    # Fallback: buscar en items_with_same_origin si no está en índice
                    if not matching_item:
                        matching_item = next(
                            (item for item in items_with_same_origin
                             if item["reference_destinations"] == destinations),
                            None
                        )

                    if matching_item:
                        # Usar precio de anumber_pricing
                        list_to_send_in_csv.append({
                            "destinations": destinations,
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
                            "destinations": destinations,
                            "country_code": price_item["country_code"],
                            "area_code": price_item["area_code"],
                            "country_area": price_item["country_area"],
                            "price_min": price_item["price_min"],
                            "start_date": price_item["start_date"],
                            "origin_name": routing
                        })

        # Agregar todos los items de price_list al final
        for price_item in price_list:
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
        Compara datos de Sunrise con datos maestros OBR.
        Implementa la misma lógica que el backend .NET (GenerateOBRSunriseFile, línea 3927).
        """
        logger.info("Iniciando comparación de datos Sunrise")
        logger.info(f"  price_list: {len(price_list)} items, origin_mapping: {len(origin_mapping)} items")

        vendor_name_upper = "SUNRISE"

        sunrise_master_data = [
            item for item in obr_master_data
            if item["vendor"].upper() == vendor_name_upper
        ]

        logger.info(f"Datos maestros Sunrise en OBR: {len(sunrise_master_data)} registros")
        if sunrise_master_data:
            origin_codes = [item.get("origin_code", "N/A") for item in sunrise_master_data[:10]]
            logger.info(f"  Primeros origin_codes en OBR: {origin_codes}")

        origin_mapping_index = {}
        for origin in origin_mapping:
            key = origin["dialed_digit"]
            if key not in origin_mapping_index:
                origin_mapping_index[key] = []
            origin_mapping_index[key].append(origin)

        logger.info(f"  origin_mapping_index: {len(origin_mapping_index)} unique dialed_digits")
        if origin_mapping_index:
            sample_keys = list(origin_mapping_index.keys())[:10]
            logger.info(f"  Primeros dialed_digits del Excel: {sample_keys}")

        price_list_index = {}
        for price in price_list:
            key = (price["origin_set"], price["origin"])
            if key not in price_list_index:
                price_list_index[key] = []
            price_list_index[key].append(price)

        price_list_by_destination = {}
        for price in price_list:
            dest = price["destination"]
            if dest not in price_list_by_destination:
                price_list_by_destination[dest] = []
            price_list_by_destination[dest].append(price)

        list_to_send_in_csv = []

        records_with_obr_match = 0
        records_without_obr_match = 0

        for vendor in sunrise_master_data:
            origin_code = str(vendor["origin_code"])
            routing = vendor["routing"]

            matching_origins = origin_mapping_index.get(origin_code, [])
            logger.info(f"Origin code {origin_code} ({routing}): {len(matching_origins)} matching origins en Excel")

            # C# línea 3954: HashSet se RESETEA por cada vendor del OBR master
            price_unique_codes = set()

            for origin in matching_origins:
                origin_set = origin["origin_set"]
                origin_name = origin["origin_name"]

                matching_prices = price_list_index.get((origin_set, origin_name), [])

                first_match = next(
                    (price for price in matching_prices if price["origin"] == origin_name),
                    None
                )

                is_vodafone = routing.lower() == "vodafone"

                for price_item in matching_prices:
                    # Lógica de Vodafone (C# líneas 3960-4099):
                    # - vodafone + NL: usa first_match si existe, sino biggestRate
                    # - vodafone + NO NL: siempre usa biggestRate
                    # - no vodafone: usa first_match si existe, sino biggestRate
                    use_first_match = (
                        first_match is not None
                        and (not is_vodafone or origin_set == "NL")
                    )

                    if use_first_match:
                        dial_codes = self._parse_and_split_dial_codes(price_item["dial_codes"])
                        for dial_code in dial_codes:
                            if dial_code.strip() and dial_code.strip() not in price_unique_codes:
                                list_to_send_in_csv.append({
                                    # C# usa destiny.Destination (item actual), NO priceListSunriseItem
                                    "destinations": price_item["destination"],
                                    "country_code": dial_code.strip(),
                                    "area_code": "",
                                    "country_area": dial_code.strip(),
                                    "price_min": first_match["rate"],
                                    "start_date": first_match["effective_date"],
                                    "origin_name": routing
                                })
                                price_unique_codes.add(dial_code.strip())

                    else:
                        same_dial_code_prices = [
                            p for p in matching_prices
                            if p["dial_codes"] == price_item["dial_codes"]
                        ]

                        if same_dial_code_prices:
                            max_price_item = max(same_dial_code_prices, key=lambda x: x["rate"])

                            dial_codes = self._parse_and_split_dial_codes(price_item["dial_codes"])
                            for dial_code in dial_codes:
                                if dial_code.strip() and dial_code.strip() not in price_unique_codes:
                                    list_to_send_in_csv.append({
                                        # C# usa destiny.Destination (item actual)
                                        "destinations": price_item["destination"],
                                        "country_code": dial_code.strip(),
                                        "area_code": "",
                                        "country_area": dial_code.strip(),
                                        "price_min": max_price_item["rate"],
                                        "start_date": max_price_item["effective_date"],
                                        "origin_name": routing
                                    })
                                    price_unique_codes.add(dial_code.strip())

        obr_record_count = len(list_to_send_in_csv)
        logger.info(f"Registros CON match en OBR Master Data: {obr_record_count}")

        # C# línea 4102: HashSet SEPARADO para el loop final
        price_unique_codes_final = set()
        final_loop_records = []

        for destination, prices in price_list_by_destination.items():
            max_price_item = max(prices, key=lambda x: x["rate"])

            dial_codes = self._parse_and_split_dial_codes(max_price_item["dial_codes"])
            first_dial_code = dial_codes[0] if dial_codes else ""

            if first_dial_code.strip() and first_dial_code.strip() not in price_unique_codes_final:
                final_loop_records.append({
                    "destinations": max_price_item["destination"],
                    "country_code": first_dial_code.strip(),
                    "area_code": "",
                    "country_area": first_dial_code.strip(),
                    "price_min": max_price_item["rate"],
                    "start_date": max_price_item["effective_date"],
                    "origin_name": ""
                })
                price_unique_codes_final.add(first_dial_code.strip())

        logger.info(f"Registros del loop final (sin OBR): {len(final_loop_records)}")

        # Combinar OBR + final loop
        list_to_send_in_csv.extend(final_loop_records)
        logger.info(f"Total ANTES de GroupBy deduplicación: {len(list_to_send_in_csv)}")

        # C# línea 4125: GroupBy deduplicación en (DialCodes, Rate, Origin)
        seen = set()
        deduplicated_list = []
        for item in list_to_send_in_csv:
            key = (item["country_code"], item["price_min"], item["origin_name"])
            if key not in seen:
                seen.add(key)
                deduplicated_list.append(item)

        logger.info(f"Total DESPUÉS de GroupBy deduplicación: {len(deduplicated_list)}")

        # C# línea 4130: Validación - el resultado no debe exceder el tamaño del price list
        # if (listToSendInCSV.Count <= priceListSunrise.Count) isSuccessful = true;
        if len(deduplicated_list) > len(price_list):
            logger.warning(
                f"VALIDACIÓN C#: resultado ({len(deduplicated_list)}) EXCEDE "
                f"price_list ({len(price_list)}). "
                f"En C# esto marcaría el proceso como fallido. "
                f"Descartando {obr_record_count} registros OBR y usando solo loop final."
            )
            # Deduplicar solo los registros del loop final
            seen_final = set()
            deduplicated_list = []
            for item in final_loop_records:
                key = (item["country_code"], item["price_min"], item["origin_name"])
                if key not in seen_final:
                    seen_final.add(key)
                    deduplicated_list.append(item)
            logger.info(f"Registros finales (solo loop final): {len(deduplicated_list)}")

        logger.info(f"Comparación Sunrise completada: {len(deduplicated_list)} registros para CSV")
        return deduplicated_list

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

        qxtel_master_data = [
            item for item in obr_master_data
            if item["vendor"].upper() == vendor_name_upper
        ]

        logger.info(f"Datos maestros Qxtel: {len(qxtel_master_data)} registros")

        new_price_by_group_detail = {}
        for price in new_price_list:
            key = price["origin_group_detail"]
            if key not in new_price_by_group_detail:
                new_price_by_group_detail[key] = []
            new_price_by_group_detail[key].append(price)

        new_price_by_group = {}
        for price in new_price_list:
            key = (price["origin_group"], price["origin_group_detail"])
            new_price_by_group[key] = price

        list_to_send_in_csv = []

        for vendor in qxtel_master_data:
            destiny_code = str(vendor["destiny_code"])
            origin_code = str(vendor["origin_code"])
            routing = vendor["routing"]

            price_list_destinations = [
                item for item in price_list
                if item["dial_codes"].startswith(destiny_code)
            ]

            if origin_code == "44":
                origins_filtered = [
                    origin for origin in origin_codes
                    if origin["origin_code"].startswith(origin_code)
                ]

                new_price_by_origin_list = []
                for origin in origins_filtered:
                    new_price_by_origin_list.extend(
                        new_price_by_group_detail.get(origin["origin_group_detail"], [])
                    )

                for price_item in price_list_destinations:
                    matching_new_prices = [
                        price for price in new_price_by_origin_list
                        if price["origin_group"] == price_item["origin_group"]
                        and price["origin_region"] == price_item["region"]
                    ]

                    if matching_new_prices:
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
                origins_filtered = [
                    origin for origin in origin_codes
                    if origin["origin_code"] == origin_code
                ]

                new_price_by_origin_list = []
                for origin in origins_filtered:
                    matching_new_price = new_price_by_group.get(
                        (origin["origin_group"], origin["origin_group_detail"])
                    )
                    if matching_new_price:
                        new_price_by_origin_list.append(matching_new_price)

                for price_item in price_list_destinations:
                    matching_new_price = next(
                        (price for price in new_price_by_origin_list
                         if price["origin_group"] == price_item["origin_group"]),
                        None
                    )

                    if matching_new_price:
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
                        list_to_send_in_csv.append({
                            "destinations": price_item["region"],
                            "country_code": price_item["dial_codes"],
                            "area_code": "",
                            "country_area": price_item["dial_codes"],
                            "price_min": price_item["rate"],
                            "start_date": price_item["effective_date"],
                            "origin_name": routing
                        })

        for price_item in price_list:
            list_to_send_in_csv.append({
                "destinations": price_item["region"],
                "country_code": price_item["dial_codes"],
                "area_code": "",
                "country_area": price_item["dial_codes"],
                "price_min": price_item["rate"],
                "start_date": price_item["effective_date"],
                "origin_name": ""
            })

        logger.info(f"Comparación Qxtel completada: {len(list_to_send_in_csv)} registros para CSV")
        return list_to_send_in_csv

    def _compare_orange_france_platinum_data(
        self,
        price_list: List[Dict[str, Any]],
        origin_mapping: List[Dict[str, Any]],
        obr_master_data: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Procesa datos de Orange France Platinum"""
        logger.info("Iniciando comparación de datos Orange France Platinum")

        vendor_name_upper = "ORANGE FRANCE PLATINUM"

        orange_master_data = [
            item for item in obr_master_data
            if item["vendor"].upper() == vendor_name_upper
        ]

        logger.info(f"Datos maestros Orange France Platinum: {len(orange_master_data)} registros")

        price_list_expanded = []
        for price in price_list:
            dial_codes = [code.strip() for code in price["dial_codes"].split(',')]
            for dial_code in dial_codes:
                if dial_code:
                    price_list_expanded.append({
                        "destination": price["destination"],
                        "dial_codes": dial_code,
                        "origin": price["origin"],
                        "effective_date": price["effective_date"],
                        "rate": price["rate"]
                    })

        logger.info(f"Price list expandida: {len(price_list_expanded)} registros")

        list_to_send_in_csv = []

        for vendor in orange_master_data:
            origin_code = str(vendor["origin_code"])
            destiny_code = str(vendor["destiny_code"])
            routing = vendor["routing"]

            matching_origins = [
                origin for origin in origin_mapping
                if origin["dialed_digit"] == origin_code
            ]

            prices_for_destiny = [
                price for price in price_list
                if price["dial_codes"].startswith(destiny_code)
            ]

            price_unique_codes = set()

            for price in prices_for_destiny:
                dial_codes_list = [code.strip() for code in price["dial_codes"].split(',')]

                if not price["origin"]:
                    if price["dial_codes"] not in price_unique_codes:
                        for dial_code in dial_codes_list:
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
                    if price["dial_codes"] not in price_unique_codes:
                        same_dial_codes = [
                            p for p in prices_for_destiny
                            if p["dial_codes"] == price["dial_codes"]
                        ]

                        match_found = False
                        for item in same_dial_codes:
                            origin_match = next(
                                (o for o in matching_origins if o["origin_group"] == item["origin"]),
                                None
                            )

                            if origin_match:
                                for dial_code in dial_codes_list:
                                    list_to_send_in_csv.append({
                                        "destinations": item["destination"],
                                        "country_code": dial_code,
                                        "area_code": "",
                                        "country_area": dial_code,
                                        "price_min": item["rate"],
                                        "start_date": item["effective_date"],
                                        "origin_name": routing
                                    })
                                price_unique_codes.add(price["dial_codes"])
                                match_found = True
                                break

                        if not match_found and price["dial_codes"] not in price_unique_codes:
                            biggest_rate = max(item["rate"] for item in same_dial_codes)
                            item_biggest_price = next(
                                item for item in same_dial_codes
                                if item["rate"] == biggest_rate
                            )

                            for dial_code in dial_codes_list:
                                list_to_send_in_csv.append({
                                    "destinations": item_biggest_price["destination"],
                                    "country_code": dial_code,
                                    "area_code": "",
                                    "country_area": dial_code,
                                    "price_min": biggest_rate,
                                    "start_date": item_biggest_price["effective_date"],
                                    "origin_name": routing
                                })
                            price_unique_codes.add(price["dial_codes"])

        unique_dial_codes = set()
        for price in price_list:
            dial_codes_list = [code.strip() for code in price["dial_codes"].split(',')]

            for dial_code in dial_codes_list:
                if dial_code and dial_code not in unique_dial_codes:
                    unique_dial_codes.add(dial_code)

                    matching_prices = [
                        p for p in price_list_expanded
                        if p["dial_codes"] == dial_code
                    ]

                    if matching_prices:
                        max_rate = max(p["rate"] for p in matching_prices)

                        list_to_send_in_csv.append({
                            "destinations": price["destination"],
                            "country_code": dial_code,
                            "area_code": "",
                            "country_area": dial_code,
                            "price_min": max_rate,
                            "start_date": price["effective_date"],
                            "origin_name": ""
                        })

        logger.info(f"Comparación Orange France Platinum completada: {len(list_to_send_in_csv)} registros")
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

        orange_master_data = [
            item for item in obr_master_data
            if item["vendor"].upper() == vendor_name_upper
        ]

        logger.info(f"Datos maestros Orange France Win: {len(orange_master_data)} registros")

        price_list_expanded = []
        for price in price_list:
            dial_codes = [code.strip() for code in price["dial_codes"].split(',')]
            for dial_code in dial_codes:
                if dial_code:
                    price_list_expanded.append({
                        "destination": price["destination"],
                        "dial_codes": dial_code,
                        "origin": price["origin"],
                        "effective_date": price["effective_date"],
                        "rate": price["rate"]
                    })

        logger.info(f"Price list expandida: {len(price_list_expanded)} registros (split por comas)")

        origin_mapping_index = {}
        for origin in origin_mapping:
            key = origin["dialed_digit"]
            if key not in origin_mapping_index:
                origin_mapping_index[key] = []
            origin_mapping_index[key].append(origin)

        list_to_send_in_csv = []
        unique_dial_codes = set()

        for vendor in orange_master_data:
            origin_code = str(vendor["origin_code"])
            destiny_code = str(vendor["destiny_code"])
            routing = vendor["routing"]

            matching_origins = origin_mapping_index.get(origin_code, [])

            for origin in matching_origins:
                origin_name = origin["origin_name"]

                matching_prices = [
                    price for price in price_list_expanded
                    if price["dial_codes"].startswith(destiny_code)
                ]

                prices_with_origin = [
                    price for price in matching_prices
                    if price["origin"] and price["origin"] == origin_name
                ]

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
                    "origin_name": ""
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

        ibasis_master_data = [
            item for item in obr_master_data
            if item["vendor"].upper() == vendor_name_upper
        ]

        logger.info(f"Datos maestros Ibasis: {len(ibasis_master_data)} registros")

        price_list_by_country = {}
        for price in price_list:
            code = price["country_code"]
            if code not in price_list_by_country:
                price_list_by_country[code] = []
            price_list_by_country[code].append(price)

        origin_mapping_index = {}
        for origin in origin_mapping:
            key = origin["dialed_digit"]
            if key not in origin_mapping_index:
                origin_mapping_index[key] = []
            origin_mapping_index[key].append(origin)

        list_to_send_in_csv = []

        for vendor in ibasis_master_data:
            origin_code = str(vendor["origin_code"])
            destiny_code = str(vendor["destiny_code"])
            routing = vendor["routing"]

            data_with_origin_by_destiny = price_list_by_country.get(destiny_code, [])

            if data_with_origin_by_destiny:
                origin_ibasis_by_vendor_origin = origin_mapping_index.get(origin_code, [])

                for origin in origin_ibasis_by_vendor_origin:
                    origin_based = origin["origin_based"]

                    data_with_origin_by_destiny_and_origin = [
                        price for price in data_with_origin_by_destiny
                        if price["origin"] == origin_based
                    ]

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

        hgc_master_data = [
            item for item in obr_master_data
            if item["vendor"].upper() == vendor_name_upper
        ]

        logger.info(f"Datos maestros HGC: {len(hgc_master_data)} registros")

        origin_mapping_index = {}
        for origin in origin_mapping:
            key = origin["dialed_digit"]
            if key not in origin_mapping_index:
                origin_mapping_index[key] = []
            origin_mapping_index[key].append(origin)

        price_list_by_destination_44 = {}
        for p in price_list:
            if p["dial_code"].strip().startswith("44"):
                dest_lower = p["destination"].lower()
                if dest_lower not in price_list_by_destination_44:
                    price_list_by_destination_44[dest_lower] = []
                price_list_by_destination_44[dest_lower].append(p)

        list_to_send_in_csv = []

        for vendor in hgc_master_data:
            origin_code = str(vendor["origin_code"])
            destiny_code = str(vendor["destiny_code"])
            routing = vendor["routing"]

            # HGC: unique_dial_codes se resetea para cada vendor (igual que C# línea 5835)
            unique_dial_codes = set()

            price_list_for_compare = [
                price for price in price_list
                if price["dial_code"].strip().startswith(destiny_code)
            ]

            for price in price_list_for_compare:
                dial_code = price["dial_code"]

                if (routing.lower() == "obr 1" and origin_code == "44" and dial_code.startswith("44")):
                    if not price["routing"]:
                        # Lógica especial UK: buscar precio más alto por destination
                        same_dial_codes_by_origin = price_list_by_destination_44.get(
                            price["destination"].lower(), []
                        )

                        if same_dial_codes_by_origin:
                            max_price_item = max(same_dial_codes_by_origin, key=lambda x: x["rate"])
                            # C# agrega DIRECTAMENTE sin verificar unique_dial_codes
                            list_to_send_in_csv.append({
                                "destinations": max_price_item["destination"],
                                "country_code": dial_code,
                                "area_code": "",
                                "country_area": dial_code,
                                "price_min": max_price_item["rate"],
                                "start_date": max_price_item["effective_date"],
                                "origin_name": routing
                            })
                else:
                    if not price["routing"]:
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
                        if dial_code not in unique_dial_codes:
                            same_dial_codes = [
                                p for p in price_list_for_compare
                                if p["dial_code"] == dial_code
                            ]

                            origin_hgc_data_to_compare = origin_mapping_index.get(origin_code, [])

                            # Intentar encontrar coincidencias con origins (C# líneas 5858-5875)
                            for same_dial in same_dial_codes:
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

                            # Fallback: Si no encontró coincidencias con origins, usar precio más alto (C# líneas 5877-5894)
                            if dial_code not in unique_dial_codes:
                                if same_dial_codes:
                                    max_price_item = max(same_dial_codes, key=lambda x: x["rate"])
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

        # HGC: Agrupar price_list por dial_code y agregar (replica C# líneas 5900-5917)
        # Agrupa para seleccionar el precio más alto de cada dial_code
        from collections import defaultdict

        grouped_prices = defaultdict(list)
        for price in price_list:
            grouped_prices[price["dial_code"]].append(price)

        for dial_code, prices_group in grouped_prices.items():
            # Seleccionar el price con el rate más alto
            max_price_item = max(prices_group, key=lambda x: x["rate"])

            # Filtrar registros vacíos (C# hace esto en ProcessObrCsvFileRates)
            if max_price_item["destination"] and max_price_item["effective_date"]:
                list_to_send_in_csv.append({
                    "destinations": max_price_item["destination"],
                    "country_code": max_price_item["dial_code"],
                    "area_code": "",
                    "country_area": max_price_item["dial_code"],
                    "price_min": max_price_item["rate"],
                    "start_date": max_price_item["effective_date"],
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
            obr_master_data = self._get_obr_master_data_cached()

            # Comparar datos
            csv_data = self._compare_oteglobe_data(
                price_list=price_list,
                new_price_list=new_price_list,
                origins=origins,
                obr_master_data=obr_master_data
            )

            # Generar y enviar CSV
            csv_file_path = self._generate_csv_file(csv_data, "Oteglobe")
            await self.email_service.send_obr_success_email(
                to_email=user_email,
                vendor_name="Oteglobe",
                csv_file_path=csv_file_path
            )

            # Limpiar archivo temporal
            self.file_manager.delete_temp_file(temp_file_path)
            self.file_manager.delete_temp_file(csv_file_path)

            logger.info(f"[OTEGLOBE] Procesamiento completado exitosamente")

        except Exception as e:
            logger.error(f"[OTEGLOBE] Error en procesamiento: {e}", exc_info=True)
            await self.email_service.send_obr_error_email(
                to_email=user_email,
                vendor_name="Oteglobe",
                error_details=str(e)
            )

    def _compare_oteglobe_data(
        self,
        price_list: List[Dict[str, Any]],
        new_price_list: List[Dict[str, Any]],
        origins: List[Dict[str, Any]],
        obr_master_data: List[Dict[str, Any]],
        vendor_name: str = "OTEGLOBE",
        allow_duplicates: bool = False
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

        vendor_master_data = [
            vendor for vendor in obr_master_data
            if vendor["vendor"].upper() == vendor_name.upper()
        ]

        logger.info(f"{vendor_name} Master Data filtrado: {len(vendor_master_data)} registros")

        origins_index = {}
        for origin in origins:
            key = origin["dial_code"]
            if key not in origins_index:
                origins_index[key] = []
            origins_index[key].append(origin)

        new_price_by_origin = {}
        for price in new_price_list:
            key = (price["origin"], price["dial_code"][:3] if len(price["dial_code"]) >= 3 else price["dial_code"])
            if key not in new_price_by_origin:
                new_price_by_origin[key] = []
            new_price_by_origin[key].append(price)

        for vendor in vendor_master_data:
            origin_code = str(vendor["origin_code"])
            destiny_code = str(vendor["destiny_code"])
            destiny = vendor["destiny"]
            routing = vendor["routing"]

            matching_origins = origins_index.get(origin_code, [])

            available_prices = []

            for origin in matching_origins:
                origin_name = origin["origin"]

                origin_available = [
                    price for price in new_price_list
                    if price["origin"] == origin_name and price["dial_code"].startswith(destiny_code)
                ]

                available_prices.extend(origin_available)

            # Oteglobe SÍ filtra por destiny (igual que C#: price.Destination.Contains(vendor.Destiny))
            available_prices_by_destiny = [
                price for price in available_prices
                if destiny.upper() in price["destination"].upper()
            ]

            price_list_destinations = [
                price for price in price_list
                if price["dial_code"].startswith(destiny_code)
            ]

            for item in price_list_destinations:
                dial_code = item["dial_code"]
                dial_code_clean = re.sub(r'[^0-9]', '', dial_code)

                # Oteglobe busca en available_prices_by_destiny (filtrado por destiny)
                new_price = next(
                    (price for price in available_prices_by_destiny if price["dial_code"] == dial_code_clean),
                    None
                )

                # Oteglobe: NO verifica duplicados (permite mismo dial code con diferentes routings)
                if new_price:
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
                    list_to_send_in_csv.append({
                        "destinations": item["destination"],
                        "country_code": dial_code,
                        "area_code": "",
                        "country_area": dial_code,
                        "price_min": item["rate"],
                        "start_date": item["effective_date"],
                        "origin_name": routing
                    })

        # Oteglobe: Agregar TODOS los price_list items al final sin verificar duplicados (igual que C#)
        for price_item in price_list:
            dial_code = price_item["dial_code"]
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

    def _compare_deutsche_data(
        self,
        price_list: List[Dict[str, Any]],
        new_price_list: List[Dict[str, Any]],
        origins: List[Dict[str, Any]],
        obr_master_data: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Compara datos de Deutsche Telecom - Replica exactamente la lógica de C#
        - NO verifica duplicados (permite múltiples entradas del mismo dial code)
        - NO filtra por destiny al buscar precios
        """
        import re
        list_to_send_in_csv = []

        vendor_master_data = [
            vendor for vendor in obr_master_data
            if vendor["vendor"].upper() == "DEUTSCHE TELECOM"
        ]

        logger.info(f"DEUTSCHE TELECOM Master Data filtrado: {len(vendor_master_data)} registros")

        origins_index = {}
        for origin in origins:
            key = origin["dial_code"]
            if key not in origins_index:
                origins_index[key] = []
            origins_index[key].append(origin)

        for vendor in vendor_master_data:
            origin_code = str(vendor["origin_code"])
            destiny_code = str(vendor["destiny_code"])
            routing = vendor["routing"]

            matching_origins = origins_index.get(origin_code, [])

            available_prices = []

            for origin in matching_origins:
                origin_name = origin["origin"]

                origin_available = [
                    price for price in new_price_list
                    if price["origin"] == origin_name and price["dial_code"].startswith(destiny_code)
                ]

                available_prices.extend(origin_available)

            price_list_destinations = [
                price for price in price_list
                if price["dial_code"].startswith(destiny_code)
            ]

            for item in price_list_destinations:
                dial_code = item["dial_code"]
                dial_code_clean = re.sub(r'[^0-9]', '', dial_code)

                # C# busca directamente en aviablePrices sin filtrar por destiny
                new_price = next(
                    (price for price in available_prices if price["dial_code"] == dial_code_clean),
                    None
                )

                if new_price:
                    # NO verifica duplicados - C# permite múltiples entradas
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
                    # NO verifica duplicados - C# permite múltiples entradas
                    list_to_send_in_csv.append({
                        "destinations": item["destination"],
                        "country_code": dial_code,
                        "area_code": "",
                        "country_area": dial_code,
                        "price_min": item["rate"],
                        "start_date": item["effective_date"],
                        "origin_name": routing
                    })

        # Agregar TODOS los items de price_list al final (sin verificar duplicados)
        for price_item in price_list:
            dial_code = price_item["dial_code"]
            list_to_send_in_csv.append({
                "destinations": price_item["destination"],
                "country_code": dial_code,
                "area_code": "",
                "country_area": dial_code,
                "price_min": price_item["rate"],
                "start_date": price_item["effective_date"],
                "origin_name": ""
            })

        logger.info(f"Comparación DEUTSCHE TELECOM completada: {len(list_to_send_in_csv)} registros para CSV")
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
            obr_master_data = self._get_obr_master_data_cached()

            # Comparar datos
            csv_data = self._compare_arelion_data(
                price_list=price_list,
                new_price_list=new_price_list,
                origins=origins,
                obr_master_data=obr_master_data
            )

            # Generar y enviar CSV
            csv_file_path = self._generate_csv_file(csv_data, "Arelion")
            await self.email_service.send_obr_success_email(
                to_email=user_email,
                vendor_name="Arelion",
                csv_file_path=csv_file_path
            )

            # Limpiar archivo temporal
            self.file_manager.delete_temp_file(temp_file_path)
            self.file_manager.delete_temp_file(csv_file_path)

            logger.info(f"[ARELION] Procesamiento completado exitosamente")

        except Exception as e:
            logger.error(f"[ARELION] Error en procesamiento: {e}", exc_info=True)
            await self.email_service.send_obr_error_email(
                to_email=user_email,
                vendor_name="Arelion",
                error_details=str(e)
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

        arelion_master_data = [
            vendor for vendor in obr_master_data
            if vendor["vendor"].upper() == "ARELION"
        ]

        logger.info(f"Arelion Master Data filtrado: {len(arelion_master_data)} registros")

        origins_index = {}
        for origin in origins:
            key = origin["dial_code"]
            if key not in origins_index:
                origins_index[key] = []
            origins_index[key].append(origin)

        for vendor in arelion_master_data:
            origin_code = str(vendor["origin_code"])
            destiny = vendor["destiny"]
            routing = vendor["routing"]

            matching_origins = origins_index.get(origin_code, [])

            available_prices = []

            for origin in matching_origins:
                origin_name = origin["origin"]

                origin_available = [
                    price for price in new_price_list
                    if price["origin"] == origin_name
                ]

                available_prices.extend(origin_available)

            available_prices_by_destiny = [
                price for price in available_prices
                if destiny.upper() in price["destination"].upper()
            ]

            price_list_destinations = [
                price for price in price_list
                if destiny.upper() in price["destination"].upper()
            ]

            for item in price_list_destinations:
                dial_code = item["dial_code"]
                dial_code_clean = re.sub(r'[^0-9]', '', dial_code)

                new_price = next(
                    (price for price in available_prices_by_destiny if price["dial_code"] == dial_code_clean),
                    None
                )

                if new_price:
                    if allow_duplicates or dial_code not in unique_dial_codes:
                        if not allow_duplicates:
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
                    if allow_duplicates or dial_code not in unique_dial_codes:
                        if not allow_duplicates:
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

            obr_master_data = self._get_obr_master_data_cached()
            csv_data = self._compare_deutsche_data(price_list, new_price_list, origins, obr_master_data)

            # Generar CSV con 6 decimales fijos (como C#)
            csv_file_path = self._generate_csv_file(
                csv_data=csv_data,
                vendor_name="Deutsche Telecom",
                decimal_places=6,
                use_variable_decimals=False
            )
            await self.email_service.send_obr_success_email(to_email=user_email, vendor_name="Deutsche Telecom", csv_file_path=csv_file_path)

            self.file_manager.delete_temp_file(temp_file_path)
            self.file_manager.delete_temp_file(csv_file_path)
            logger.info(f"[DEUTSCHE] Procesamiento completado")
        except Exception as e:
            logger.error(f"[DEUTSCHE] Error: {e}", exc_info=True)
            await self.email_service.send_obr_error_email(to_email=user_email, vendor_name="Deutsche Telecom", error_details=str(e))

    async def process_orange_telecom_file(self, file_content: bytes, file_name: str, user_email: str):
        """Procesa Orange Telecom"""
        try:
            logger.info(f"[ORANGE TELECOM] Iniciando: {file_name}")
            temp_file_path = self.file_manager.save_temp_file(file_content, file_name)
            price_list = self.excel_service.read_orange_telecom_price_list(temp_file_path)
            new_price_list = self.excel_service.read_orange_telecom_new_price(temp_file_path)
            origins = self.excel_service.read_orange_telecom_origins(temp_file_path)
            logger.info(f"[ORANGE TELECOM] Leído - PL:{len(price_list)}, NP:{len(new_price_list)}, OR:{len(origins)}")
            logger.info(f"[ORANGE TELECOM DEBUG] Primeros 3 price_list: {price_list[:3] if price_list else 'EMPTY'}")
            logger.info(f"[ORANGE TELECOM DEBUG] Primeros 3 new_price_list: {new_price_list[:3] if new_price_list else 'EMPTY'}")
            logger.info(f"[ORANGE TELECOM DEBUG] Primeros 3 origins: {origins[:3] if origins else 'EMPTY'}")
            obr_master_data = self._get_obr_master_data_cached()
            csv_data = self._compare_orange_telecom_data(price_list, new_price_list, origins, obr_master_data)
            logger.info(f"[ORANGE TELECOM DEBUG] Primeros 3 csv_data: {csv_data[:3] if csv_data else 'EMPTY'}")
            csv_file_path = self._generate_csv_file(csv_data, "Orange Telecom")
            await self.email_service.send_obr_success_email(user_email, "Orange Telecom", csv_file_path)
            self.file_manager.delete_temp_file(temp_file_path)
            self.file_manager.delete_temp_file(csv_file_path)
            logger.info(f"[ORANGE TELECOM] Completado")
        except Exception as e:
            logger.error(f"[ORANGE TELECOM] Error: {e}", exc_info=True)
            await self.email_service.send_obr_error_email(user_email, "Orange Telecom", str(e))

    def _compare_orange_telecom_data(self, price_list, new_price_list, origins, obr_master_data):
        """Orange Telecom: Code.StartsWith, Origin.Contains + OriginCode match

        IMPORTANTE: Replica exactamente el comportamiento del C# que:
        1. Procesa registros con lógica de comparación (líneas 2907-2948 del C#)
        2. Agrega TODOS los registros de price_list al final SIN deduplicación (líneas 2950-2961 del C#)
        """
        list_to_send_in_csv = []
        vendor_data = [v for v in obr_master_data if v["vendor"].upper() == "ORANGE TELECOM"]

        # C#: Líneas 2907-2948 - Procesamiento con lógica de comparación
        origins_by_code = {}
        for o in origins:
            key = o["origin_code"]
            if key not in origins_by_code:
                origins_by_code[key] = []
            origins_by_code[key].append(o)

        for vendor in vendor_data:
            destiny_code, destiny, origin_code, routing = str(vendor["destiny_code"]), vendor["destiny"], vendor["origin_code"], vendor["routing"]
            prices_filtered = [p for p in price_list if p["code"].startswith(destiny_code)]

            origins_filtered = [
                o for o in origins_by_code.get(origin_code, [])
                if destiny.upper() in o["origin"].upper()
            ]

            available_new_prices = []
            for origin in origins_filtered:
                available_new_prices.extend([np for np in new_price_list if np["origin_group"] == origin["origin"]])

            for item in prices_filtered:
                new_price = next((np for np in available_new_prices if np["destination"] == item["destination"]), None)
                list_to_send_in_csv.append({
                    "destinations": item["destination"],
                    "country_code": item["code"],
                    "area_code": "",
                    "country_area": item["code"],
                    "price_min": new_price["new_rate"] if new_price else item["rate"],
                    "start_date": new_price["effective_date"] if new_price else item["effective_date"],
                    "origin_name": routing
                })

        # C#: Líneas 2950-2961 - Agregar TODOS los registros de price_list con routing=""
        # SIN deduplicación (el C# no verifica duplicados, simplemente agrega todo)
        for item in price_list:
            list_to_send_in_csv.append({
                "destinations": item["destination"],
                "country_code": item["code"],
                "area_code": "",
                "country_area": item["code"],
                "price_min": item["rate"],
                "start_date": item["effective_date"],
                "origin_name": ""
            })

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
            obr_master_data = self._get_obr_master_data_cached()
            csv_data = self._compare_apelby_data(price_list, new_price_list, origins, obr_master_data)
            csv_file_path = self._generate_csv_file(csv_data, "Apelby")
            await self.email_service.send_obr_success_email(user_email, "Apelby", csv_file_path)
            self.file_manager.delete_temp_file(temp_file_path)
            self.file_manager.delete_temp_file(csv_file_path)
            logger.info(f"[APELBY] Completado")
        except Exception as e:
            logger.error(f"[APELBY] Error: {e}", exc_info=True)
            await self.email_service.send_obr_error_email(user_email, "Apelby", str(e))

    def _compare_apelby_data(self, price_list, new_price_list, origins, obr_master_data):
        """Apelby: Split Code por comas"""
        import re
        list_to_send_in_csv, unique_codes = [], set()
        vendor_data = [v for v in obr_master_data if v["vendor"].upper() == "APELBY"]

        origins_by_code = {}
        for o in origins:
            key = o["origin_code"]
            if key not in origins_by_code:
                origins_by_code[key] = []
            origins_by_code[key].append(o)

        new_price_by_dial = {}
        for p in new_price_list:
            key = p["dial_code"]
            if key not in new_price_by_dial:
                new_price_by_dial[key] = []
            new_price_by_dial[key].append(p)

        for vendor in vendor_data:
            origin_code, destiny_code, routing = vendor["origin_code"], str(vendor["destiny_code"]), vendor["routing"]
            matching_origins = origins_by_code.get(origin_code, [])

            available_prices = []
            for origin in matching_origins:
                for p in new_price_list:
                    if p["origin"] == origin["origin"] and p["dial_code"].startswith(destiny_code):
                        available_prices.append(p)

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

    def _compare_phonetic_data(self, price_list, new_price_list, origins, obr_master_data):
        """Procesa datos de Phonetic Limited"""
        list_to_send_in_csv = []

        price_list_phonetic_format = []
        for price in price_list:
            dial_codes = [code.strip() for code in price["code"].split(',')]
            for code in dial_codes:
                price_list_phonetic_format.append({
                    "destination": price["destination"],
                    "code": code,
                    "rate": price["rate"],
                    "effective_date": price["effective_date"],
                    "routing": price.get("routing", "")
                })

        vendor_data = [v for v in obr_master_data if v["vendor"].upper() == "PHONETIC LIMITED"]
        logger.info(f"Phonetic: {len(vendor_data)} vendors en OBR Master Data")
        logger.info(f"Phonetic: {len(price_list_phonetic_format)} registros después de split")

        for vendor in vendor_data:
            origin_code = str(vendor["origin_code"])
            destiny_code = str(vendor["destiny_code"])
            routing = vendor["routing"]

            origin_dial_codes = next((o for o in origins if str(o["origin_code"]) == origin_code), None)

            if origin_dial_codes:
                available_prices_by_destiny = [
                    p for p in new_price_list
                    if vendor["origin"].upper() in p["origin"].upper()
                ]

                price_list_phonetic_destinations = [
                    p for p in price_list_phonetic_format
                    if p["code"].startswith(destiny_code)
                ]

                logger.debug(f"Phonetic: origin_code={origin_code}, destiny_code={destiny_code}, destinations={len(price_list_phonetic_destinations)}")

                for item in price_list_phonetic_destinations:
                    new_price = next(
                        (p for p in available_prices_by_destiny if p["dial_code"] == item["code"]),
                        None
                    )

                    if new_price:
                        list_to_send_in_csv.append({
                            "destinations": item["destination"],
                            "country_code": item["code"],
                            "area_code": "",
                            "country_area": item["code"],
                            "price_min": new_price["rate"],
                            "start_date": new_price["effective_date"],
                            "origin_name": routing
                        })
                    else:
                        list_to_send_in_csv.append({
                            "destinations": item["destination"],
                            "country_code": item["code"],
                            "area_code": "",
                            "country_area": item["code"],
                            "price_min": item["rate"],
                            "start_date": item["effective_date"],
                            "origin_name": routing
                        })

        records_before_final = len(list_to_send_in_csv)
        for price_item in price_list_phonetic_format:
            list_to_send_in_csv.append({
                "destinations": price_item["destination"],
                "country_code": price_item["code"],
                "area_code": "",
                "country_area": price_item["code"],
                "price_min": price_item["rate"],
                "start_date": price_item["effective_date"],
                "origin_name": ""
            })

        logger.info(f"Phonetic: {len(list_to_send_in_csv) - records_before_final} registros finales con routing vacío")
        logger.info(f"Phonetic Limited: {len(list_to_send_in_csv)} registros totales")
        return list_to_send_in_csv

    async def process_phonetic_file(self, file_content: bytes, file_name: str, user_email: str):
        """Procesa archivo de Phonetic Limited"""
        try:
            logger.info(f"[PHONETIC] Iniciando: {file_name}")
            temp_file_path = self.file_manager.save_temp_file(file_content, file_name)
            price_list = self.excel_service.read_phonetic_price_list(temp_file_path)
            new_price_list = self.excel_service.read_phonetic_new_price(temp_file_path)
            origins = self.excel_service.read_phonetic_origins(temp_file_path)
            logger.info(f"[PHONETIC] Leído - PL:{len(price_list)}, NP:{len(new_price_list)}, OR:{len(origins)}")
            obr_master_data = self._get_obr_master_data_cached()
            csv_data = self._compare_phonetic_data(price_list, new_price_list, origins, obr_master_data)
            csv_file_path = self._generate_csv_file(csv_data, "Phonetic Limited")
            await self.email_service.send_obr_success_email(user_email, "Phonetic Limited", csv_file_path)
            self.file_manager.delete_temp_file(temp_file_path)
            self.file_manager.delete_temp_file(csv_file_path)
            logger.info(f"[PHONETIC] Completado")
        except Exception as e:
            logger.error(f"[PHONETIC] Error: {e}", exc_info=True)
            await self.email_service.send_obr_error_email(user_email, "Phonetic Limited", str(e))

    def _generate_csv_file(
        self,
        csv_data: List[Dict[str, Any]],
        vendor_name: str,
        decimal_places: int = 4,
        use_variable_decimals: bool = False,
        origin_column_header: str = "Routing"
    ) -> str:
        timestamp = datetime.now().strftime("%m_%d_%Y")
        file_name = f"{vendor_name}-{timestamp}.csv"
        file_path = self.file_manager.get_temp_file_path(file_name)

        try:
            sorted_csv_data = sorted(
                csv_data,
                key=lambda x: (
                    x.get("country_area", ""),
                    x.get("destinations", ""),
                    x.get("origin_name", "")
                )
            )

            with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)

                writer.writerow([
                    "CountryCode - Destination",
                    "Dial codes",
                    "Price",
                    "Effective Date",
                    origin_column_header
                ])

                for item in sorted_csv_data:
                    start_date = item["start_date"]
                    if isinstance(start_date, str) and " " in start_date:
                        start_date = start_date.split(" ")[0]

                    price = item["price_min"]
                    if isinstance(price, (int, float)):
                        if use_variable_decimals:
                            # Formatear con suficientes decimales para evitar notación científica
                            # Luego remover ceros al final (como C# ToString())
                            price_str = f"{float(price):.10f}"
                            price_str = price_str.rstrip('0').rstrip('.')
                            price = price_str
                        else:
                            price = format(float(price), f'.{decimal_places}f')

                    writer.writerow([
                        item["destinations"],
                        item["country_area"],
                        price,
                        start_date,
                        item["origin_name"]
                    ])

            logger.info(f"CSV generado exitosamente: {file_path}")
            return file_path

        except Exception as e:
            logger.error(f"Error generando CSV: {e}")
            raise

    def _generate_csv_file_hgc(
        self,
        csv_data: List[Dict[str, Any]],
        vendor_name: str
    ) -> str:
        """
        Genera archivo CSV específico para HGC Premium
        Formatea fechas como MM/dd/yyyy hh:mm:ss AM/PM para coincidir con C#
        """
        from datetime import datetime

        timestamp = datetime.now().strftime("%m_%d_%Y")
        file_name = f"{vendor_name}-{timestamp}.csv"
        file_path = self.file_manager.get_temp_file_path(file_name)

        try:
            # Ordenar datos para orden determinístico (igual que C#)
            # Ordenar por: country_code, destinations, origin_name
            sorted_csv_data = sorted(
                csv_data,
                key=lambda x: (
                    x.get("country_area", ""),
                    x.get("destinations", ""),
                    x.get("origin_name", "")
                )
            )

            with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)

                # Header
                writer.writerow([
                    "CountryCode - Destination",
                    "Dial codes",
                    "Price",
                    "Effective Date",
                    "Routing"
                ])

                # Data rows
                for item in sorted_csv_data:
                    # Formatear fecha como C# (MM/dd/yyyy hh:mm:ss AM/PM)
                    start_date = item["start_date"]
                    if isinstance(start_date, str):
                        try:
                            # Parsear fecha desde formato YYYY-MM-DD o M/d/yyyy
                            if "-" in start_date:
                                date_obj = datetime.strptime(start_date.split(" ")[0], "%Y-%m-%d")
                            elif "/" in start_date:
                                date_obj = datetime.strptime(start_date.split(" ")[0], "%m/%d/%Y")
                            else:
                                date_obj = datetime.strptime(start_date, "%Y-%m-%d")
                            # Formatear como "MM/dd/yyyy 12:00:00 AM"
                            start_date = date_obj.strftime("%Y-%m-%d") + " 12:00:00 AM"
                        except:
                            pass  # Si falla el parseo, usar fecha original

                    # Formatear precio con 5 decimales (igual que C#)
                    price = item["price_min"]
                    if isinstance(price, (int, float)):
                        price = format(float(price), '.5f')

                    writer.writerow([
                        item["destinations"],
                        item["country_area"],
                        price,
                        start_date,
                        item["origin_name"]
                    ])

            logger.info(f"CSV HGC generado exitosamente: {file_path}")
            return file_path

        except Exception as e:
            logger.error(f"Error generando CSV HGC: {e}")
            raise
