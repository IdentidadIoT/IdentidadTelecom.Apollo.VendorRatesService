"""
Configuraciones de lectura Excel para todos los vendors soportados.

Este módulo centraliza todas las configuraciones de Excel en un formato declarativo,
eliminando la duplicación de código en excel_service.py.
"""
from core.excel_reader_base import SheetConfig, VendorExcelConfig
import re
from typing import Any


# ============================================================================
# FUNCIONES DE TRANSFORMACIÓN COMUNES
# ============================================================================

def parse_float_simple(value, row) -> float:
    """Transforma un valor a float (parsing simple)"""
    try:
        if isinstance(value, (int, float)):
            return float(value)
        if value:
            return float(value)
        return 0.0
    except (ValueError, TypeError):
        return 0.0


def parse_float_regex(value, row) -> float:
    """Transforma un valor a float usando regex (para valores con símbolos)"""
    try:
        if isinstance(value, (int, float)):
            return float(value)
        if value:
            rate_str = str(value)
            rate_match = re.match(r'[\d\.]+', rate_str)
            if rate_match:
                return float(rate_match.group())
        return 0.0
    except (ValueError, TypeError):
        return 0.0


def build_country_area(value, row) -> str:
    """Construye country_area concatenando country_code + area_code (Belgacom)"""
    country_code = str(row[4]).strip() if row[4] else ""
    area_code = str(row[5]).strip() if row[5] else ""
    return country_code + area_code


def strip_string(value, row) -> str:
    """Transforma un valor a string y hace strip"""
    return str(value).strip() if value is not None else ""


def empty_string(value, row) -> str:
    """Retorna string vacío (para campos que se llenan después)"""
    return ""


# ============================================================================
# CONFIGURACIONES POR VENDOR
# ============================================================================

VENDOR_EXCEL_CONFIGS = {
    # ------------------------------------------------------------------------
    # BELGACOM PLATINUM (2 hojas)
    # ------------------------------------------------------------------------
    "belgacom": VendorExcelConfig(
        vendor_name="Belgacom Platinum",
        sheets={
            "price_list": SheetConfig(
                name="Price List",
                start_row=9,
                column_mapping={
                    "destinations": 1,
                    "country_code": 4,
                    "area_code": 5,
                    "price_min": 6,
                    "start_date": 14,
                    "country_area": -1  # Se calcula en transformación
                },
                transformations={
                    "destinations": strip_string,
                    "country_code": strip_string,
                    "area_code": strip_string,
                    "price_min": parse_float_simple,
                    "start_date": strip_string,
                    "country_area": build_country_area
                },
                fallback_sheet="FIRST"
            ),
            "anumber_pricing": SheetConfig(
                name="A-number pricing",
                start_row=2,
                column_mapping={
                    "origin": 11,
                    "reference_destinations": 1,
                    "price_min": 6,
                    "start_date": 8
                },
                transformations={
                    "origin": strip_string,
                    "reference_destinations": strip_string,
                    "price_min": parse_float_simple,
                    "start_date": strip_string
                }
            )
        }
    ),

    # ------------------------------------------------------------------------
    # SUNRISE (2 hojas)
    # ------------------------------------------------------------------------
    "sunrise": VendorExcelConfig(
        vendor_name="Sunrise",
        sheets={
            "price_list": SheetConfig(
                name="Pricing",
                start_row=15,
                column_mapping={
                    "destination": 0,
                    "origin_set": 1,
                    "origin": 2,
                    "dial_codes": 3,
                    "rate": 5,
                    "effective_date": 7
                },
                transformations={
                    "destination": strip_string,
                    "origin_set": strip_string,
                    "origin": strip_string,
                    "dial_codes": strip_string,
                    "rate": parse_float_simple,
                    "effective_date": strip_string
                }
            ),
            "origin_mapping": SheetConfig(
                name="Origin",
                start_row=2,
                column_mapping={
                    "origin_set": 0,
                    "origin_name": 1,
                    "dialed_digit": 2
                },
                transformations={
                    "origin_set": strip_string,
                    "origin_name": strip_string,
                    "dialed_digit": strip_string
                }
            )
        }
    ),

    # ------------------------------------------------------------------------
    # QXTEL (3 archivos separados)
    # ------------------------------------------------------------------------
    "qxtel": VendorExcelConfig(
        vendor_name="Qxtel",
        sheets={
            "price_list": SheetConfig(
                name="FIRST",  # Primera hoja del archivo
                start_row=2,
                column_mapping={
                    "region": 0,
                    "dial_codes": 1,
                    "rate": 3,
                    "effective_date": 8,
                    "origin_group": 9
                },
                transformations={
                    "region": strip_string,
                    "dial_codes": strip_string,
                    "rate": parse_float_simple,
                    "effective_date": strip_string,
                    "origin_group": strip_string
                },
                fallback_sheet="FIRST"
            ),
            "new_price": SheetConfig(
                name="FIRST",
                start_row=5,
                column_mapping={
                    "region": 0,
                    "origin_region": 1,
                    "origin_group": 2,
                    "origin_group_detail": 3,
                    "rate": 4,
                    "effective_date": 10
                },
                transformations={
                    "region": strip_string,
                    "origin_region": strip_string,
                    "origin_group": strip_string,
                    "origin_group_detail": strip_string,
                    "rate": parse_float_simple,
                    "effective_date": strip_string
                },
                fallback_sheet="FIRST"
            ),
            "origins": SheetConfig(
                name="FIRST",
                start_row=5,
                column_mapping={
                    "origin_group": 0,
                    "origin_group_detail": 1,
                    "origin_region": 2,
                    "origin_code": 3
                },
                transformations={
                    "origin_group": strip_string,
                    "origin_group_detail": strip_string,
                    "origin_region": strip_string,
                    "origin_code": strip_string
                },
                fallback_sheet="FIRST"
            )
        }
    ),

    # ------------------------------------------------------------------------
    # ORANGE FRANCE PLATINUM (2 hojas)
    # ------------------------------------------------------------------------
    "orange_france_platinum": VendorExcelConfig(
        vendor_name="Orange France Platinum",
        sheets={
            "price_list": SheetConfig(
                name="Rates",
                start_row=14,
                column_mapping={
                    "destination": 0,
                    "dial_codes": 1,
                    "origin": 2,
                    "effective_date": 3,
                    "rate": 5
                },
                transformations={
                    "destination": strip_string,
                    "dial_codes": strip_string,
                    "origin": strip_string,
                    "effective_date": strip_string,
                    "rate": parse_float_simple
                }
            ),
            "origin_mapping": SheetConfig(
                name="Origin Mapping",
                start_row=2,
                column_mapping={
                    "origin_group": 0,
                    "origin_name": 1,
                    "dialed_digit": 2
                },
                transformations={
                    "origin_group": strip_string,
                    "origin_name": strip_string,
                    "dialed_digit": strip_string
                }
            )
        }
    ),

    # ------------------------------------------------------------------------
    # ORANGE FRANCE WIN (Alias a Orange France Platinum - configuración idéntica)
    # ------------------------------------------------------------------------
    "orange_france_win": None,  # Se resuelve mediante get_vendor_config()

    # ------------------------------------------------------------------------
    # IBASIS GLOBAL INC PREMIUM (2 hojas)
    # ------------------------------------------------------------------------
    "ibasis": VendorExcelConfig(
        vendor_name="Ibasis Global Inc Premium",
        sheets={
            "price_list": SheetConfig(
                name="Pricelist",
                start_row=11,
                column_mapping={
                    "destination": 0,
                    "origin": 1,
                    "country_code": 2,
                    "dial_codes": 3,
                    "effective_date": 4,
                    "rate": 5
                },
                transformations={
                    "destination": strip_string,
                    "origin": strip_string,
                    "country_code": strip_string,
                    "dial_codes": strip_string,
                    "effective_date": strip_string,
                    "rate": parse_float_simple
                }
            ),
            "origin_mapping": SheetConfig(
                name="Origin List",
                start_row=14,
                column_mapping={
                    "origin_based": 0,
                    "origin_country": 2,
                    "dialed_digit": 3
                },
                transformations={
                    "origin_based": strip_string,
                    "origin_country": strip_string,
                    "dialed_digit": strip_string
                }
            )
        }
    ),

    # ------------------------------------------------------------------------
    # HGC PREMIUM (2 hojas)
    # ------------------------------------------------------------------------
    "hgc": VendorExcelConfig(
        vendor_name="HGC Premium",
        sheets={
            "price_list": SheetConfig(
                name="Rates",
                start_row=33,
                column_mapping={
                    "destination": 0,
                    "dial_code": 1,
                    "routing": 2,
                    "effective_date": 3,
                    "rate": 5
                },
                transformations={
                    "destination": strip_string,
                    "dial_code": strip_string,
                    "routing": strip_string,
                    "effective_date": strip_string,
                    "rate": parse_float_simple
                }
            ),
            "origin_mapping": SheetConfig(
                name="Origin Mapping",
                start_row=2,
                column_mapping={
                    "origin_group": 0,
                    "origin_name": 1,
                    "dialed_digit": 2
                },
                transformations={
                    "origin_group": strip_string,
                    "origin_name": strip_string,
                    "dialed_digit": strip_string
                }
            )
        }
    ),

    # ------------------------------------------------------------------------
    # OTEGLOBE (3 hojas)
    # ------------------------------------------------------------------------
    "oteglobe": VendorExcelConfig(
        vendor_name="Oteglobe",
        sheets={
            "price_list": SheetConfig(
                name="OTEGLOBE Voice Rates",
                start_row=16,
                column_mapping={
                    "destination": 0,
                    "dial_code": 1,
                    "rate": 2,
                    "effective_date": 5,
                    "routing": -1  # No existe, se llena con empty_string
                },
                transformations={
                    "destination": strip_string,
                    "dial_code": strip_string,
                    "rate": parse_float_regex,
                    "effective_date": strip_string,
                    "routing": empty_string
                }
            ),
            "new_price": SheetConfig(
                name="Origin Rates",
                start_row=16,
                column_mapping={
                    "destination": 0,
                    "dial_code": 1,
                    "origin": 2,
                    "rate": 3,
                    "effective_date": 5
                },
                transformations={
                    "destination": strip_string,
                    "dial_code": strip_string,
                    "origin": strip_string,
                    "rate": parse_float_regex,
                    "effective_date": strip_string
                }
            ),
            "origins": SheetConfig(
                name="Origin Dialcodes",
                start_row=16,
                column_mapping={
                    "origin": 0,
                    "dial_code": 1
                },
                transformations={
                    "origin": strip_string,
                    "dial_code": strip_string
                }
            )
        }
    ),

    # ------------------------------------------------------------------------
    # ARELION (3 hojas)
    # ------------------------------------------------------------------------
    "arelion": VendorExcelConfig(
        vendor_name="Arelion",
        sheets={
            "price_list": SheetConfig(
                name="Rates",
                start_row=28,
                column_mapping={
                    "destination": 0,
                    "dial_code": 1,
                    "rate": 2,
                    "effective_date": 3,
                    "routing": -1
                },
                transformations={
                    "destination": strip_string,
                    "dial_code": strip_string,
                    "rate": parse_float_simple,
                    "effective_date": strip_string,
                    "routing": empty_string
                }
            ),
            "new_price": SheetConfig(
                name="Origin Rates",
                start_row=7,
                column_mapping={
                    "destination": 0,
                    "dial_code": 1,
                    "origin": 2,
                    "rate": 3,
                    "effective_date": 4
                },
                transformations={
                    "destination": strip_string,
                    "dial_code": strip_string,
                    "origin": strip_string,
                    "rate": parse_float_simple,
                    "effective_date": strip_string
                }
            ),
            "origins": SheetConfig(
                name="Origin Definitions",
                start_row=7,
                column_mapping={
                    "origin": 0,
                    "dial_code": 1
                },
                transformations={
                    "origin": strip_string,
                    "dial_code": strip_string
                }
            )
        }
    ),

    # ------------------------------------------------------------------------
    # DEUTSCHE TELECOM (3 hojas)
    # ------------------------------------------------------------------------
    "deutsche": VendorExcelConfig(
        vendor_name="Deutsche Telecom",
        sheets={
            "price_list": SheetConfig(
                name="DTGC Hubbing Rates",
                start_row=22,
                column_mapping={
                    "destination": 0,
                    "dial_code": 1,
                    "rate": 2,
                    "effective_date": 3,
                    "routing": -1
                },
                transformations={
                    "destination": strip_string,
                    "dial_code": strip_string,
                    "rate": parse_float_simple,
                    "effective_date": strip_string,
                    "routing": empty_string
                }
            ),
            "new_price": SheetConfig(
                name="Origin Rates",
                start_row=15,
                column_mapping={
                    "destination": 0,
                    "dial_code": 1,
                    "origin": 2,
                    "rate": 3,
                    "effective_date": 4
                },
                transformations={
                    "destination": strip_string,
                    "dial_code": strip_string,
                    "origin": strip_string,
                    "rate": parse_float_simple,
                    "effective_date": strip_string
                }
            ),
            "origins": SheetConfig(
                name="Origin Dialcodes",
                start_row=15,
                column_mapping={
                    "origin": 0,
                    "dial_code": 1
                },
                transformations={
                    "origin": strip_string,
                    "dial_code": strip_string
                }
            )
        }
    ),

    # ------------------------------------------------------------------------
    # ORANGE TELECOM (3 hojas - 2da y 3ra en misma hoja 'SURCHARGED RATES')
    # ------------------------------------------------------------------------
    "orange_telecom": VendorExcelConfig(
        vendor_name="Orange Telecom",
        sheets={
            "price_list": SheetConfig(
                name="ORANGE RATES",
                start_row=20,
                column_mapping={
                    "code": 0,
                    "destination": 1,
                    "rate": 2,
                    "effective_date": 4,
                    "routing": -1
                },
                transformations={
                    "code": strip_string,
                    "destination": strip_string,
                    "rate": parse_float_simple,
                    "effective_date": strip_string,
                    "routing": empty_string
                }
            ),
            "new_price": SheetConfig(
                name="SURCHARGED RATES",
                start_row=11,
                column_mapping={
                    "destination": 0,
                    "origin_group": 1,
                    "new_rate": 2,
                    "effective_date": 4
                },
                transformations={
                    "destination": strip_string,
                    "origin_group": strip_string,
                    "new_rate": parse_float_simple,
                    "effective_date": strip_string
                }
            ),
            "origins": SheetConfig(
                name="SURCHARGED RATES",
                start_row=11,
                column_mapping={
                    "origin": 8,
                    "origin_code": 9
                },
                transformations={
                    "origin": strip_string,
                    "origin_code": strip_string
                }
            )
        }
    ),

    # ------------------------------------------------------------------------
    # APELBY (3 hojas)
    # ------------------------------------------------------------------------
    "apelby": VendorExcelConfig(
        vendor_name="Apelby",
        sheets={
            "price_list": SheetConfig(
                name="PriceList",
                start_row=16,
                column_mapping={
                    "destination": 0,
                    "code": 1,
                    "rate": 2,
                    "effective_date": 3,
                    "routing": -1
                },
                transformations={
                    "destination": strip_string,
                    "code": strip_string,
                    "rate": parse_float_regex,
                    "effective_date": strip_string,
                    "routing": empty_string
                }
            ),
            "new_price": SheetConfig(
                name="NewPrice",
                start_row=16,
                column_mapping={
                    "origin": 0,
                    "destination": 1,
                    "dial_code": 2,
                    "rate": 3,
                    "effective_date": 4
                },
                transformations={
                    "origin": strip_string,
                    "destination": strip_string,
                    "dial_code": strip_string,
                    "rate": parse_float_simple,
                    "effective_date": strip_string
                }
            ),
            "origins": SheetConfig(
                name="Origins",
                start_row=16,
                column_mapping={
                    "origin": 0,
                    "origin_code": 1
                },
                transformations={
                    "origin": strip_string,
                    "origin_code": strip_string
                }
            )
        }
    ),

    # ------------------------------------------------------------------------
    # PHONETIC LIMITED
    # ------------------------------------------------------------------------
    "phonetic": VendorExcelConfig(
        vendor_name="Phonetic Limited",
        sheets={
            "price_list": SheetConfig(
                name="Rates",
                start_row=44,
                column_mapping={
                    "destination": 0,
                    "code": 1,
                    "rate": 2,
                    "effective_date": 3,
                    "routing": -1
                },
                transformations={
                    "destination": strip_string,
                    "code": strip_string,
                    "rate": parse_float_simple,
                    "effective_date": strip_string,
                    "routing": empty_string
                }
            ),
            "new_price": SheetConfig(
                name="Origin Rates",
                start_row=8,
                column_mapping={
                    "origin": 0,
                    "destination": 1,
                    "dial_code": 2,
                    "rate": 3,
                    "effective_date": 4
                },
                transformations={
                    "origin": strip_string,
                    "destination": strip_string,
                    "dial_code": strip_string,
                    "rate": parse_float_simple,
                    "effective_date": strip_string
                }
            ),
            "origins": SheetConfig(
                name="Origin zones",
                start_row=1,
                column_mapping={
                    "origin": 0,
                    "origin_code": 1
                },
                transformations={
                    "origin": strip_string,
                    "origin_code": strip_string
                }
            )
        }
    ),
}


# ============================================================================
# FUNCIONES HELPER
# ============================================================================

def get_vendor_config(vendor_key: str) -> VendorExcelConfig:
    """
    Obtiene la configuración de un vendor con resolución de aliases.

    Args:
        vendor_key: Clave del vendor (e.g., "belgacom", "sunrise")

    Returns:
        VendorExcelConfig correspondiente o None si no existe

    Examples:
        >>> config = get_vendor_config("belgacom")
        >>> config = get_vendor_config("orange_france_win")  # Devuelve config de platinum
    """
    config = VENDOR_EXCEL_CONFIGS.get(vendor_key)

    # Si es None, resolver alias
    if config is None:
        # Orange France Win usa misma config que Platinum
        if vendor_key == "orange_france_win":
            return VENDOR_EXCEL_CONFIGS["orange_france_platinum"]

    return config


def get_all_vendor_keys() -> list:
    """
    Retorna lista de todas las claves de vendors configurados.

    Returns:
        Lista de strings con las claves de vendors
    """
    return [key for key in VENDOR_EXCEL_CONFIGS.keys() if VENDOR_EXCEL_CONFIGS[key] is not None]
