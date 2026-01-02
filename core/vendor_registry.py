"""
Registro centralizado de vendors con configuración para procesamiento OBR.

Este módulo elimina la cascada de elif en obr_routes.py y proporciona
lookup dinámico de vendors mediante el Registry Pattern.

Beneficios:
- Agregar nuevo vendor sin modificar código de routes
- Validación centralizada de vendors soportados
- Keyword matching robusto con case-insensitive
- Configuración completa en un solo lugar
"""
from typing import Dict, Optional, List, Any


# ============================================================================
# REGISTRO DE VENDORS
# ============================================================================

VENDOR_REGISTRY: Dict[str, Dict[str, Any]] = {
    # ========================================================================
    # VENDORS DE 2 HOJAS (TwoSheetVendorProcessor)
    # ========================================================================

    "belgacom": {
        "vendor_key": "belgacom",
        "display_name": "Belgacom Platinum",
        "keywords": ["BELGACOM", "BELGACOM PLATINUM"],
        "processor_type": "two_sheet",
        "comparison_strategy": "belgacom",
        "process_method_name": "process_belgacom_file",
        "decimal_format": {
            "type": "variable",  # "variable" o "fixed"
            "places": None  # Número de decimales si es fixed
        },
        "file_requirement": {
            "type": "single",
            "sheets": 2,
            "description": "1 archivo Excel con 2 hojas (PriceList + ANumber Pricing)"
        }
    },

    "sunrise": {
        "vendor_key": "sunrise",
        "display_name": "Sunrise",
        "keywords": ["SUNRISE"],
        "processor_type": "two_sheet",
        "comparison_strategy": "sunrise",
        "process_method_name": "process_sunrise_file",
        "decimal_format": {
            "type": "variable",
            "places": None
        },
        "file_requirement": {
            "type": "single",
            "sheets": 2,
            "description": "1 archivo Excel con 2 hojas (Pricing + Origin Mapping)"
        }
    },

    "orange_france_platinum": {
        "vendor_key": "orange_france_platinum",
        "display_name": "Orange France Platinum",
        "keywords": ["ORANGE FRANCE PLATINUM", "ORANGE PLATINUM"],
        "processor_type": "two_sheet",
        "comparison_strategy": "sunrise",  # Reutiliza estrategia de Sunrise
        "process_method_name": "process_orange_france_platinum_file",
        "file_requirement": {
            "type": "single",
            "sheets": 2,
            "description": "1 archivo Excel con 2 hojas (Rates + Origin Mapping)"
        }
    },

    "orange_france_win": {
        "vendor_key": "orange_france_platinum",  # Reutiliza config de Platinum
        "display_name": "Orange France Win",
        "keywords": ["ORANGE FRANCE WIN", "ORANGE FRANCE WIN AS", "ORANGE WIN"],
        "processor_type": "two_sheet",
        "comparison_strategy": "sunrise",  # Reutiliza estrategia de Sunrise
        "process_method_name": "process_orange_france_win_file",
        "file_requirement": {
            "type": "single",
            "sheets": 2,
            "description": "1 archivo Excel con 2 hojas (Rates + Origin Mapping)"
        }
    },

    "ibasis": {
        "vendor_key": "ibasis",
        "display_name": "Ibasis Global Inc Premium",
        "keywords": ["IBASIS", "IBASIS GLOBAL", "IBASIS PREMIUM"],
        "processor_type": "two_sheet",
        "comparison_strategy": "sunrise",  # Reutiliza estrategia de Sunrise
        "process_method_name": "process_ibasis_file",
        "file_requirement": {
            "type": "single",
            "sheets": 2,
            "description": "1 archivo Excel con 2 hojas (Rates + Origins)"
        }
    },

    "hgc": {
        "vendor_key": "hgc",
        "display_name": "HGC Premium",
        "keywords": ["HGC", "HGC PREMIUM"],
        "processor_type": "two_sheet",
        "comparison_strategy": "sunrise",  # Reutiliza estrategia de Sunrise
        "process_method_name": "process_hgc_file",
        "file_requirement": {
            "type": "single",
            "sheets": 2,
            "description": "1 archivo Excel con 2 hojas (Rates + Origins)"
        }
    },

    # ========================================================================
    # VENDORS DE 3 HOJAS (ThreeSheetVendorProcessor)
    # ========================================================================

    "oteglobe": {
        "vendor_key": "oteglobe",
        "display_name": "Oteglobe",
        "keywords": ["OTEGLOBE", "OTE GLOBE"],
        "processor_type": "three_sheet",
        "comparison_strategy": "oteglobe",
        "process_method_name": "process_oteglobe_file",
        "file_requirement": {
            "type": "single",
            "sheets": 3,
            "description": "1 archivo Excel con 3 hojas (Voice Rates + Origin Rates + Origin DialCodes)"
        }
    },

    "arelion": {
        "vendor_key": "arelion",
        "display_name": "Arelion",
        "keywords": ["ARELION"],
        "processor_type": "three_sheet",
        "comparison_strategy": "arelion",  # Variante de Oteglobe
        "process_method_name": "process_arelion_file",
        "file_requirement": {
            "type": "single",
            "sheets": 3,
            "description": "1 archivo Excel con 3 hojas (Price List + New Price + Origins)"
        }
    },

    "deutsche": {
        "vendor_key": "deutsche",
        "display_name": "Deutsche Telecom",
        "keywords": ["DEUTSCHE", "DEUTSCHE TELECOM", "DT"],
        "processor_type": "three_sheet",
        "comparison_strategy": "oteglobe",  # Reutiliza estrategia de Oteglobe
        "process_method_name": "process_deutsche_file",
        "decimal_format": {
            "type": "fixed",
            "places": 6  # Deutsche usa 6 decimales fijos
        },
        "file_requirement": {
            "type": "single",
            "sheets": 3,
            "description": "1 archivo Excel con 3 hojas (Price List + New Price + Origins)"
        }
    },

    "orange_telecom": {
        "vendor_key": "orange_telecom",
        "display_name": "Orange Telecom",
        "keywords": ["ORANGE TELECOM", "ORANGE TELECOMS"],
        "processor_type": "three_sheet",
        "comparison_strategy": "oteglobe",  # Reutiliza estrategia de Oteglobe
        "process_method_name": "process_orange_telecom_file",
        "file_requirement": {
            "type": "single",
            "sheets": 3,
            "description": "1 archivo Excel con 3 hojas (Price List + New Price + Origins)"
        }
    },

    "apelby": {
        "vendor_key": "apelby",
        "display_name": "Apelby",
        "keywords": ["APELBY"],
        "processor_type": "three_sheet",
        "comparison_strategy": "apelby",
        "process_method_name": "process_apelby_file",
        "file_requirement": {
            "type": "single",
            "sheets": 3,
            "description": "1 archivo Excel con 3 hojas (Price List + New Price + Origins)"
        }
    },

    "phonetic": {
        "vendor_key": "apelby",  # Reutiliza config de Apelby
        "display_name": "Phonetic Limited",
        "keywords": ["PHONETIC", "PHONETIC LIMITED"],
        "processor_type": "three_sheet",
        "comparison_strategy": "apelby",  # Reutiliza estrategia de Apelby
        "process_method_name": "process_phonetic_file",
        "file_requirement": {
            "type": "single",
            "sheets": 3,
            "description": "1 archivo Excel con 3 hojas (Price List + New Price + Origins)"
        }
    },

    # ========================================================================
    # VENDORS ESPECIALES
    # ========================================================================

    "qxtel": {
        "vendor_key": "qxtel",
        "display_name": "Qxtel",
        "keywords": ["QXTEL", "QX TEL"],
        "processor_type": "qxtel_special",
        "comparison_strategy": "oteglobe",  # Usa misma estrategia que Oteglobe
        "process_method_name": "process_qxtel_file",
        "decimal_format": {
            "type": "variable",
            "places": None
        },
        "file_requirement": {
            "type": "multiple",
            "count": 3,
            "description": "3 archivos Excel separados (Price List + New Price + Origin Codes)"
        }
    },
}


# ============================================================================
# FUNCIONES DE LOOKUP
# ============================================================================

def find_vendor_by_name(vendor_name: str) -> Optional[Dict[str, Any]]:
    """
    Busca vendor por nombre usando keyword matching (case-insensitive).

    Args:
        vendor_name: Nombre del vendor a buscar (puede ser aproximado)

    Returns:
        Dict con configuración del vendor, o None si no se encuentra

    Examples:
        >>> find_vendor_by_name("Belgacom Platinum")
        {'vendor_key': 'belgacom', 'display_name': 'Belgacom Platinum', ...}

        >>> find_vendor_by_name("sunrise")
        {'vendor_key': 'sunrise', 'display_name': 'Sunrise', ...}

        >>> find_vendor_by_name("orange france win as")
        {'vendor_key': 'orange_france_platinum', 'display_name': 'Orange France Win', ...}
    """
    if not vendor_name:
        return None

    vendor_upper = vendor_name.upper().strip()

    # Buscar coincidencia exacta por display_name primero
    for vendor_key, config in VENDOR_REGISTRY.items():
        if config["display_name"].upper() == vendor_upper:
            return config.copy()

    # Buscar por keywords (substring matching)
    for vendor_key, config in VENDOR_REGISTRY.items():
        for keyword in config["keywords"]:
            if keyword in vendor_upper:
                return config.copy()

    return None


def get_vendor_by_key(vendor_key: str) -> Optional[Dict[str, Any]]:
    """
    Obtiene vendor por su clave interna.

    Args:
        vendor_key: Clave del vendor (e.g., "belgacom", "sunrise")

    Returns:
        Dict con configuración del vendor, o None si no existe
    """
    config = VENDOR_REGISTRY.get(vendor_key)
    return config.copy() if config else None


def get_supported_vendors() -> List[str]:
    """
    Obtiene lista de nombres de vendors soportados.

    Returns:
        Lista de display_name de todos los vendors registrados

    Example:
        >>> get_supported_vendors()
        ['Belgacom Platinum', 'Sunrise', 'Orange France Platinum', ...]
    """
    return [config["display_name"] for config in VENDOR_REGISTRY.values()]


def get_vendors_by_processor_type(processor_type: str) -> List[Dict[str, Any]]:
    """
    Obtiene vendors por tipo de procesador.

    Args:
        processor_type: Tipo de procesador ("two_sheet", "three_sheet", "qxtel_special")

    Returns:
        Lista de configuraciones de vendors que usan ese procesador
    """
    return [
        config.copy()
        for config in VENDOR_REGISTRY.values()
        if config["processor_type"] == processor_type
    ]


def get_vendors_by_comparison_strategy(strategy_name: str) -> List[Dict[str, Any]]:
    """
    Obtiene vendors que usan una estrategia de comparación específica.

    Args:
        strategy_name: Nombre de la estrategia (e.g., "belgacom", "sunrise", "oteglobe")

    Returns:
        Lista de configuraciones de vendors que usan esa estrategia
    """
    return [
        config.copy()
        for config in VENDOR_REGISTRY.values()
        if config["comparison_strategy"] == strategy_name
    ]


def validate_vendor_file_requirement(
    vendor_key: str,
    file_count: int
) -> bool:
    """
    Valida que el número de archivos cumpla con el requerimiento del vendor.

    Args:
        vendor_key: Clave del vendor
        file_count: Número de archivos recibidos

    Returns:
        True si el número de archivos es correcto, False en caso contrario
    """
    config = VENDOR_REGISTRY.get(vendor_key)
    if not config:
        return False

    requirement = config["file_requirement"]

    if requirement["type"] == "single":
        return file_count == 1
    elif requirement["type"] == "multiple":
        return file_count == requirement.get("count", 1)

    return False
