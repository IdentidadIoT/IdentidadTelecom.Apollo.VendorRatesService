"""
Estrategias de comparación para diferentes vendors usando Strategy Pattern.

Este módulo contiene todas las estrategias de comparación extraídas del obr_service.py,
permitiendo reutilización y mantenibilidad. Cada estrategia implementa la lógica
específica de comparación entre datos del vendor y OBR master data.

Nota: Las estrategias se extraerán completamente del obr_service.py en la implementación final.
Por ahora, se proporciona la estructura y algunas implementaciones de ejemplo.
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any
from core.logging import logger


# ============================================================================
# ESTRATEGIA BASE
# ============================================================================

class ComparisonStrategy(ABC):
    """
    Interfaz base para estrategias de comparación.

    Todas las estrategias deben implementar el método compare() que toma
    los datos del vendor y el OBR master data, y retorna los datos procesados
    para el CSV final.
    """

    @abstractmethod
    def compare(
        self,
        vendor_data: Dict[str, Any],
        obr_master: List[Dict[str, Any]],
        config: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Compara datos del vendor con OBR master data.

        Args:
            vendor_data: Dict con datos leídos del vendor
                         (estructura varía según vendor)
            obr_master: Lista de registros OBR master filtrados por vendor
            config: Configuración del vendor (vendor_key, display_name, etc.)

        Returns:
            Lista de diccionarios con formato CSV:
            [{"destinations": str, "country_code": str, "price_min": float}, ...]

        Raises:
            Exception: Si hay error en la comparación
        """
        pass


# ============================================================================
# ESTRATEGIAS PARA VENDORS DE 2 HOJAS
# ============================================================================

class BelgacomComparisonStrategy(ComparisonStrategy):
    """
    Estrategia de comparación para Belgacom Platinum.

    Lógica:
    - Para cada registro OBR master, filtrar price_list por destiny_code
    - Filtrar anumber_pricing por origin_code y destiny
    - Buscar coincidencia por reference_destinations
    - Caso especial: "traffic from eu" + Italia (39) + Andorra (376) + "italy mobile tim"
    - Al final, agregar todos los items de price_list (excepto código 88237)
    """

    def compare(self, vendor_data, obr_master, config):
        price_list = vendor_data["price_list"]
        anumber_pricing = vendor_data["anumber_pricing"]
        vendor_name = config["display_name"]

        logger.info(f"[{vendor_name}] Comparación Belgacom: {len(obr_master)} registros OBR")

        list_to_send_in_csv = []

        # Procesar cada configuración de vendor en datos maestros
        for vendor in obr_master:
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
            # Saltar código especial 88237
            if price_item.get("country_area") == "88237":
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

        logger.info(f"[{vendor_name}] Comparación completada: {len(list_to_send_in_csv)} registros")
        return list_to_send_in_csv


class TwoSheetGenericComparisonStrategy(ComparisonStrategy):
    """
    Estrategia GENÉRICA para vendors con 2 hojas (Price List + Origin Mapping)

    VENDORS QUE USAN ESTA ESTRATEGIA:
    - Orange France Platinum
    - Orange France Win
    - Ibasis Global Inc Premium
    - HGC Premium

    NOTA: Sunrise tiene su propia estrategia específica que hereda de esta.

    Lógica:
    - Para cada registro OBR master, filtrar price_list por origin
    - Filtrar origin_mapping por dialed_digit (startswith destiny_code)
    - Buscar coincidencia entre price_list y origin_mapping
    - Generar registros únicos evitando duplicados
    """

    def compare(self, vendor_data, obr_master, config):
        price_list = vendor_data["price_list"]
        origin_mapping = vendor_data["origin_mapping"]
        vendor_name = config["display_name"]

        logger.info(f"[{vendor_name}] Comparación TwoSheet: {len(obr_master)} registros OBR")

        list_to_send_in_csv = []
        unique_codes = set()

        for vendor in obr_master:
            destiny_code = str(vendor["destiny_code"])
            origin_name = vendor["origin"]

            # Filtrar price_list por origin
            prices_filtered = [
                item for item in price_list
                if item["origin"] == origin_name
            ]

            # Filtrar origin_mapping por dialed_digit (startswith destiny_code)
            origins_filtered = [
                item for item in origin_mapping
                if item["dialed_digit"].startswith(destiny_code)
            ]

            # Para cada precio, buscar coincidencia en origin_mapping
            for price_item in prices_filtered:
                matching_origins = [
                    origin for origin in origins_filtered
                    if origin["origin_name"] == price_item["origin"]
                ]

                for origin in matching_origins:
                    code = origin["dialed_digit"]
                    if code not in unique_codes:
                        unique_codes.add(code)
                        list_to_send_in_csv.append({
                            "destinations": price_item["destination"],
                            "country_code": code,
                            "price_min": price_item["rate"]
                        })

        logger.info(f"[{vendor_name}] Comparación completada: {len(list_to_send_in_csv)} registros")
        return list_to_send_in_csv


    # NOTA: Sunrise NO usa el patrón Strategy de este módulo.
    # Su lógica de comparación está implementada directamente en
    # obr_service.py:_compare_sunrise_data() porque tiene lógica especial
    # (routing "vodafone" + OriginSet "NL", formato 4 decimales, etc.)
    # que no encaja en TwoSheetGenericComparisonStrategy.


# ============================================================================
# ESTRATEGIAS PARA VENDORS DE 3 HOJAS
# ============================================================================

class OteglobeComparisonStrategy(ComparisonStrategy):
    """
    Estrategia de comparación para Oteglobe (también usada por Deutsche Telecom).

    Lógica:
    - Para cada registro OBR master, filtrar price_list por dial_code (startswith)
    - Filtrar origins por dial_code (startswith destiny_code)
    - Filtrar new_price por origin y destination
    - Usar new_price si existe, sino price_list
    - Generar registros únicos
    """

    def compare(self, vendor_data, obr_master, config):
        price_list = vendor_data["price_list"]
        new_price_list = vendor_data["new_price"]
        origins = vendor_data["origins"]
        vendor_name = config["display_name"]

        logger.info(f"[{vendor_name}] Comparación Oteglobe: {len(obr_master)} registros OBR")

        list_to_send_in_csv = []
        unique_codes = set()

        for vendor in obr_master:
            destiny_code = str(vendor["destiny_code"])
            destiny = vendor["destiny"]
            origin_code = vendor["origin_code"]

            # Filtrar price_list por dial_code (startswith destiny_code)
            prices_filtered = [
                item for item in price_list
                if item["dial_code"].startswith(destiny_code)
            ]

            # Filtrar origins por dial_code (startswith destiny_code)
            origins_filtered = [
                item for item in origins
                if destiny.upper() in item["origin"].upper()
                and item["dial_code"] == origin_code
            ]

            # Buscar new_prices disponibles
            available_new_prices = []
            for origin in origins_filtered:
                available_new_prices.extend([
                    np for np in new_price_list
                    if np["origin"] == origin["origin"]
                ])

            # Para cada precio, buscar new_price o usar precio base
            for item in prices_filtered:
                new_price = next(
                    (np for np in available_new_prices
                     if np["destination"] == item["destination"]),
                    None
                )

                code = item["dial_code"]
                if code not in unique_codes:
                    unique_codes.add(code)
                    list_to_send_in_csv.append({
                        "destinations": item["destination"],
                        "country_code": code,
                        "price_min": new_price["rate"] if new_price else item["rate"]
                    })

        logger.info(f"[{vendor_name}] Comparación completada: {len(list_to_send_in_csv)} registros")
        return list_to_send_in_csv


class ArelionComparisonStrategy(ComparisonStrategy):
    """
    Estrategia de comparación para Arelion (variante de Oteglobe).

    Diferencia clave: usa Destination.Contains en lugar de startswith
    """

    def compare(self, vendor_data, obr_master, config):
        price_list = vendor_data["price_list"]
        new_price_list = vendor_data["new_price"]
        origins = vendor_data["origins"]
        vendor_name = config["display_name"]

        logger.info(f"[{vendor_name}] Comparación Arelion: {len(obr_master)} registros OBR")

        list_to_send_in_csv = []
        unique_codes = set()

        for vendor in obr_master:
            destiny_code = str(vendor["destiny_code"])
            destiny = vendor["destiny"]
            origin_code = vendor["origin_code"]

            # Filtrar price_list por dial_code (startswith)
            prices_filtered = [
                item for item in price_list
                if item["dial_code"].startswith(destiny_code)
            ]

            # Filtrar origins - usa Contains en vez de match exacto
            origins_filtered = [
                item for item in origins
                if destiny.upper() in item["origin"].upper()
                and item["dial_code"] == origin_code
            ]

            # Buscar new_prices disponibles
            available_new_prices = []
            for origin in origins_filtered:
                available_new_prices.extend([
                    np for np in new_price_list
                    if np["origin"] == origin["origin"]
                ])

            # Para cada precio, buscar new_price o usar precio base
            for item in prices_filtered:
                new_price = next(
                    (np for np in available_new_prices
                     if np["destination"] == item["destination"]),
                    None
                )

                code = item["dial_code"]
                if code not in unique_codes:
                    unique_codes.add(code)
                    list_to_send_in_csv.append({
                        "destinations": item["destination"],
                        "country_code": code,
                        "price_min": new_price["rate"] if new_price else item["rate"]
                    })

        logger.info(f"[{vendor_name}] Comparación completada: {len(list_to_send_in_csv)} registros")
        return list_to_send_in_csv


class ApelbyComparisonStrategy(ComparisonStrategy):
    """
    Estrategia de comparación para Apelby (también usada por Phonetic Limited).

    Lógica especial:
    - El campo "code" en price_list puede contener múltiples códigos separados por comas
    - Para cada código, genera un registro separado
    - Similar a Oteglobe pero con split de códigos
    """

    def compare(self, vendor_data, obr_master, config):
        price_list = vendor_data["price_list"]
        new_price_list = vendor_data["new_price"]
        origins = vendor_data["origins"]
        vendor_name = config["display_name"]

        logger.info(f"[{vendor_name}] Comparación Apelby: {len(obr_master)} registros OBR")

        list_to_send_in_csv = []
        unique_codes = set()

        for vendor in obr_master:
            destiny_code = str(vendor["destiny_code"])
            destiny = vendor["destiny"]
            origin_code = vendor["origin_code"]

            # Filtrar price_list - el code puede tener múltiples valores separados por coma
            prices_filtered = []
            for item in price_list:
                codes = [c.strip() for c in item["code"].split(",")]
                for code in codes:
                    if code.startswith(destiny_code):
                        prices_filtered.append({
                            **item,
                            "code": code  # Usar código individual
                        })

            # Filtrar origins
            origins_filtered = [
                item for item in origins
                if destiny.upper() in item["origin"].upper()
                and item["origin_code"] == origin_code
            ]

            # Buscar new_prices disponibles
            available_new_prices = []
            for origin in origins_filtered:
                available_new_prices.extend([
                    np for np in new_price_list
                    if np["origin"] == origin["origin"]
                ])

            # Para cada precio, buscar new_price o usar precio base
            for item in prices_filtered:
                new_price = next(
                    (np for np in available_new_prices
                     if np["destination"] == item["destination"]
                     and np["dial_code"] == item["code"]),
                    None
                )

                code = item["code"]
                if code not in unique_codes:
                    unique_codes.add(code)
                    list_to_send_in_csv.append({
                        "destinations": item["destination"],
                        "country_code": code,
                        "price_min": new_price["rate"] if new_price else item["rate"]
                    })

        logger.info(f"[{vendor_name}] Comparación completada: {len(list_to_send_in_csv)} registros")
        return list_to_send_in_csv


# ============================================================================
# REGISTRO DE ESTRATEGIAS
# ============================================================================

COMPARISON_STRATEGIES = {
    # Vendors de 2 hojas
    "belgacom": BelgacomComparisonStrategy(),
    # NOTA: Sunrise no está aquí. Usa obr_service.py:_compare_sunrise_data() directamente
    "orange_france": TwoSheetGenericComparisonStrategy(),  # Estrategia genérica 2 hojas
    "ibasis": TwoSheetGenericComparisonStrategy(),  # Estrategia genérica 2 hojas
    "hgc": TwoSheetGenericComparisonStrategy(),  # Estrategia genérica 2 hojas

    # Vendors de 3 hojas
    "oteglobe": OteglobeComparisonStrategy(),
    "deutsche": OteglobeComparisonStrategy(),  # Usa misma estrategia que Oteglobe
    "arelion": ArelionComparisonStrategy(),
    "orange_telecom": OteglobeComparisonStrategy(),  # TODO: Verificar si necesita estrategia específica
    "apelby": ApelbyComparisonStrategy(),
    "phonetic": ApelbyComparisonStrategy(),  # Usa misma estrategia que Apelby

    # Qxtel (3 archivos)
    "qxtel": OteglobeComparisonStrategy(),  # TODO: Implementar estrategia específica Qxtel
}


def get_comparison_strategy(strategy_name: str) -> ComparisonStrategy:
    """
    Obtiene la estrategia de comparación por nombre.

    Args:
        strategy_name: Nombre de la estrategia (e.g., "belgacom", "sunrise")

    Returns:
        ComparisonStrategy: Instancia de la estrategia

    Raises:
        ValueError: Si la estrategia no existe
    """
    strategy = COMPARISON_STRATEGIES.get(strategy_name)
    if not strategy:
        raise ValueError(f"Estrategia de comparación '{strategy_name}' no encontrada")
    return strategy
