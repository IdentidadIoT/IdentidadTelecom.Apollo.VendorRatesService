#!/bin/bash
################################################################################
# VendorRatesService - Script de Instalación para Ubuntu 22.04
# Este script instala y configura el microservicio VendorRatesService
################################################################################

set -e  # Exit on error

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Variables de configuración
APP_NAME="VendorRatesService"
APP_DIR="/opt/pythonapps/VendorRatesService"
APP_USER="idt3vapp"
PYTHON_VERSION="3.10"
PORT="63400"

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}VendorRatesService - Setup Installer${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Función para verificar si el comando necesita sudo
check_sudo() {
    if [ "$EUID" -ne 0 ]; then
        echo -e "${RED}ERROR: Este script necesita ejecutarse con sudo${NC}"
        echo "Ejecuta: sudo bash setup-linux.sh"
        exit 1
    fi
}

# Verificar permisos
check_sudo

echo -e "${YELLOW}[1/10] Actualizando paquetes del sistema...${NC}"
apt-get update

echo -e "${YELLOW}[2/10] Instalando dependencias del sistema...${NC}"
apt-get install -y \
    python3-pip \
    python3-venv \
    python3-dev \
    build-essential \
    curl \
    gnupg \
    apt-transport-https \
    ca-certificates

echo -e "${YELLOW}[3/10] Instalando ODBC Driver 17 para SQL Server...${NC}"
# Agregar repositorio de Microsoft
if ! [ -f /etc/apt/sources.list.d/mssql-release.list ]; then
    curl https://packages.microsoft.com/keys/microsoft.asc | apt-key add -
    curl https://packages.microsoft.com/config/ubuntu/22.04/prod.list > /etc/apt/sources.list.d/mssql-release.list
    apt-get update
fi

# Instalar ODBC Driver
ACCEPT_EULA=Y apt-get install -y msodbcsql17 unixodbc-dev

echo -e "${YELLOW}[4/10] Verificando instalación de ODBC Driver...${NC}"
odbcinst -q -d -n "ODBC Driver 17 for SQL Server"

echo -e "${YELLOW}[5/10] Creando directorio de la aplicación...${NC}"
mkdir -p $APP_DIR
mkdir -p $APP_DIR/logs
mkdir -p $APP_DIR/temp_vendor_files

echo -e "${YELLOW}[6/10] Copiando archivos de la aplicación...${NC}"
# Nota: Los archivos deben estar en el directorio actual
if [ ! -f "main.py" ]; then
    echo -e "${RED}ERROR: No se encontró main.py en el directorio actual${NC}"
    echo "Asegúrate de ejecutar este script desde la carpeta VendorRatesService"
    exit 1
fi

# Copiar archivos (excluyendo venv, logs, cache)
rsync -av --progress \
    --exclude 'venv' \
    --exclude 'env' \
    --exclude '__pycache__' \
    --exclude '*.pyc' \
    --exclude 'logs' \
    --exclude '*.log' \
    --exclude '.git' \
    --exclude 'routes' \
    --exclude 'templates' \
    --exclude 'nul' \
    ./ $APP_DIR/

echo -e "${YELLOW}[7/10] Creando virtual environment...${NC}"
cd $APP_DIR
python3 -m venv venv

echo -e "${YELLOW}[8/10] Instalando dependencias Python...${NC}"
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

echo -e "${YELLOW}[9/10] Configurando permisos...${NC}"
chown -R $APP_USER:$APP_USER $APP_DIR

echo -e "${YELLOW}[10/10] Verificando instalación...${NC}"
source venv/bin/activate
python -c "import fastapi; import sqlalchemy; import pyodbc; print('✓ Dependencias OK')"

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}✓ Instalación completada con éxito${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${YELLOW}Próximos pasos:${NC}"
echo "1. Configurar archivos:"
echo "   - $APP_DIR/config/config.cfg"
echo "   - $APP_DIR/config/auth_config.cfg"
echo ""
echo "2. Crear servicio systemd:"
echo "   sudo cp vendorrates.service /etc/systemd/system/"
echo "   sudo systemctl daemon-reload"
echo "   sudo systemctl enable vendorrates.service"
echo "   sudo systemctl start vendorrates.service"
echo ""
echo "3. Configurar Nginx:"
echo "   sudo cp vendorrates-nginx.conf /etc/nginx/sites-available/vendorrates"
echo "   sudo ln -s /etc/nginx/sites-available/vendorrates /etc/nginx/sites-enabled/"
echo "   sudo nginx -t"
echo "   sudo systemctl reload nginx"
echo ""
echo "4. Verificar servicio:"
echo "   sudo systemctl status vendorrates.service"
echo "   curl http://localhost:$PORT/"
echo ""
