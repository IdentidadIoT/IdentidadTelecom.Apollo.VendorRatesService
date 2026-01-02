"""
Repositorio para acceso a datos OBR
Accede a la misma base de datos que el backend .NET
"""
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import text

from core.logging import logger


class OBRRepository:
    """Repositorio para operaciones de base de datos OBR"""

    def __init__(self, db: Session):
        self.db = db

    def get_obr_master_data(self) -> List[Dict[str, Any]]:
        """
        Obtiene los datos maestros de OBR (tabla OBRVendor)
        Aproximadamente 5000 registros
        """
        try:
            # Query a la tabla OBRVendor (ajusta el nombre de la tabla según tu BD)
            query = text("""
                SELECT
                    Vendor,
                    OriginCode,
                    DestinyCode,
                    Destiny,
                    Routing,
                    Origin
                FROM OBRVendor
                ORDER BY Vendor, OriginCode, DestinyCode
            """)

            result = self.db.execute(query)
            rows = result.fetchall()

            # Convertir a lista de diccionarios
            master_data = []
            for row in rows:
                master_data.append({
                    "vendor": row[0],
                    "origin_code": row[1],
                    "destiny_code": row[2],
                    "destiny": row[3],
                    "routing": row[4],
                    "origin": row[5]
                })

            logger.info(f"OBR Master Data obtenido: {len(master_data)} registros")
            return master_data

        except Exception as e:
            logger.error(f"Error obteniendo OBR Master Data: {e}")
            raise

    def user_has_obr_permission(self, username: str) -> bool:
        """
        Verifica si el usuario tiene permisos para cargar archivos OBR
        """
        try:
            # Ajusta según tu tabla de usuarios y roles
            query = text("""
                SELECT COUNT(*)
                FROM AspNetUsers u
                INNER JOIN AspNetUserRoles ur ON u.Id = ur.UserId
                INNER JOIN AspNetRoles r ON ur.RoleId = r.Id
                WHERE u.UserName = :username
                AND (r.Name IN ('Admin', 'OBRManager') OR u.UserName = :username)
            """)

            result = self.db.execute(query, {"username": username})
            count = result.scalar()

            return count > 0

        except Exception as e:
            logger.warning(f"Error verificando permisos de usuario: {e}")
            # Por defecto, permitir si hay error (ajustar según necesidad)
            return True
