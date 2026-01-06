#!/bin/bash
################################################################################
# VendorRatesService - Instalación MANUAL sin sudo
# Para usuario: idt3vapp
# Ejecutar desde: ~/pythonapps/VendorRatesService/
################################################################################

set -e

# Colores
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Variables
APP_NAME="VendorRatesService"
APP_DIR="$(pwd)"  # Directorio actual (debe ser ~/pythonapps/VendorRatesService)
PYTHON_VERSION="3.10"
PORT="63400"

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}VendorRatesService - Instalación Manual${NC}"
echo -e "${GREEN}Usuario: $(whoami)${NC}"
echo -e "${GREEN}Directorio: $APP_DIR${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Verificar que estamos en el directorio correcto
if [ ! -f "main.py" ]; then
    echo -e "${RED}ERROR: Este script debe ejecutarse desde ~/pythonapps/VendorRatesService/${NC}"
    echo "Directorio actual: $(pwd)"
    echo ""
    echo "Por favor:"
    echo "  cd ~/pythonapps/VendorRatesService"
    echo "  bash setup-manual.sh"
    exit 1
fi

echo -e "${YELLOW}[1/8] Verificando Python...${NC}"
python3 --version
if [ $? -ne 0 ]; then
    echo -e "${RED}ERROR: Python 3 no está instalado${NC}"
    exit 1
fi

echo -e "${YELLOW}[2/8] Verificando pip...${NC}"
pip3 --version
if [ $? -ne 0 ]; then
    echo -e "${RED}ERROR: pip3 no está instalado${NC}"
    exit 1
fi

echo -e "${YELLOW}[3/8] Verificando ODBC Driver para SQL Server...${NC}"
if odbcinst -q -d -n "ODBC Driver 17 for SQL Server" > /dev/null 2>&1; then
    echo -e "${GREEN}✓ ODBC Driver 17 ya está instalado${NC}"
elif odbcinst -q -d -n "ODBC Driver 18 for SQL Server" > /dev/null 2>&1; then
    echo -e "${GREEN}✓ ODBC Driver 18 encontrado${NC}"
    echo -e "${YELLOW}⚠ Necesitarás actualizar config.cfg para usar 'ODBC Driver 18 for SQL Server'${NC}"
else
    echo -e "${RED}⚠ ADVERTENCIA: No se encontró ODBC Driver para SQL Server${NC}"
    echo -e "${YELLOW}La aplicación NO podrá conectarse a Azure SQL${NC}"
    echo -e "${YELLOW}Necesitarás que un admin ejecute: sudo apt-get install -y msodbcsql17${NC}"
    read -p "¿Continuar de todas formas? (s/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Ss]$ ]]; then
        exit 1
    fi
fi

echo -e "${YELLOW}[4/8] Creando directorios necesarios...${NC}"
mkdir -p logs
mkdir -p temp_vendor_files

echo -e "${YELLOW}[5/8] Limpiando archivos innecesarios...${NC}"
# Limpiar archivos temporales y carpetas vacías
rm -rf __pycache__
rm -rf routes/
rm -rf templates/
rm -f nul
rm -f server.log
rm -f logs/*.log 2>/dev/null || true

echo -e "${GREEN}✓ Archivos listos${NC}"

echo -e "${YELLOW}[6/8] Creando virtual environment...${NC}"
cd "$APP_DIR"
python3 -m venv venv

echo -e "${YELLOW}[7/8] Instalando dependencias Python...${NC}"
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

echo -e "${YELLOW}[8/8] Verificando instalación...${NC}"
python -c "import fastapi; print('✓ FastAPI')"
python -c "import sqlalchemy; print('✓ SQLAlchemy')"
python -c "import pydantic; print('✓ Pydantic')"
python -c "import jwt; print('✓ PyJWT')"

# Verificar pyodbc (puede fallar si no hay ODBC driver)
if python -c "import pyodbc; print('✓ pyodbc')" 2>/dev/null; then
    echo -e "${GREEN}✓ pyodbc instalado correctamente${NC}"
else
    echo -e "${YELLOW}⚠ pyodbc no pudo cargarse (necesitas ODBC Driver)${NC}"
fi

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}✓ Instalación completada${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${YELLOW}Ubicación: $APP_DIR${NC}"
echo ""
echo -e "${YELLOW}Próximos pasos:${NC}"
echo ""
echo "1. Verificar configuración:"
echo "   nano config/config.cfg"
echo "   nano config/auth_config.cfg"
echo ""
echo "2. Probar la aplicación:"
echo "   source venv/bin/activate"
echo "   python main.py"
echo ""
echo "3. En otra terminal, probar:"
echo "   curl http://localhost:63400/"
echo ""
echo "4. Para ejecutar en background (con screen):"
echo "   screen -S vendorrates"
echo "   source venv/bin/activate"
echo "   python main.py"
echo "   # Presiona Ctrl+A, luego D para detach"
echo ""
echo "5. Para reconectar al screen:"
echo "   screen -r vendorrates"
echo ""
echo "6. IMPORTANTE: Pide a un admin que configure Nginx:"
echo "   cd $APP_DIR"
echo "   sudo cp vendorrates-nginx.conf /etc/nginx/sites-available/vendorrates"
echo "   sudo ln -s /etc/nginx/sites-available/vendorrates /etc/nginx/sites-enabled/"
echo "   sudo nginx -t"
echo "   sudo systemctl reload nginx"
echo ""
echo "7. Más información: cat INSTALACION_MANUAL.md"
echo ""
