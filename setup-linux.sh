#!/bin/bash
################################################################################
# VendorRatesService - Instalación Segura para Ubuntu 22.04
# Este script configura el microservicio VendorRatesService
#
# IMPORTANTE:
# - Ejecuta este script DESDE el directorio donde ya tienes los archivos
# - NO copia archivos, trabaja en el directorio actual
# - Verifica PRIMERO si algo ya está instalado
# - SOLO instala lo que realmente falta
# - NO toca repositorios innecesariamente
################################################################################

# NO usar set -e para que el script continue aunque falle algún comando opcional

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Variables de configuración
APP_NAME="VendorRatesService"
APP_DIR="$(pwd)"  # Usar directorio actual
APP_USER="idt3vapp"
PYTHON_VERSION="3.10"
PORT="63400"

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}VendorRatesService - Instalación Segura${NC}"
echo -e "${GREEN}Directorio: $APP_DIR${NC}"
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

# Verificar que estamos en el directorio correcto
if [ ! -f "main.py" ]; then
    echo -e "${RED}ERROR: Este script debe ejecutarse desde el directorio VendorRatesService${NC}"
    echo "Directorio actual: $(pwd)"
    echo ""
    echo "Por favor:"
    echo "  cd /ruta/donde/descomprimiste/VendorRatesService"
    echo "  sudo bash setup-linux.sh"
    exit 1
fi

echo -e "${BLUE}[VERIFICACIÓN] Revisando dependencias del sistema...${NC}"
echo ""

# Variables para rastrear qué necesita instalarse
NEED_PYTHON3=false
NEED_PIP=false
NEED_VENV=false
NEED_DEV_TOOLS=false
NEED_ODBC=false

# ============================================================================
# PASO 1: Verificar Python 3
# ============================================================================
echo -e "${YELLOW}[1/8] Verificando Python 3...${NC}"
if command -v python3 &> /dev/null; then
    PYTHON_VER=$(python3 --version 2>&1 | awk '{print $2}')
    echo -e "${GREEN}✓ Python $PYTHON_VER ya está instalado${NC}"
else
    echo -e "${YELLOW}⚠ Python 3 NO encontrado${NC}"
    NEED_PYTHON3=true
fi

# ============================================================================
# PASO 2: Verificar pip
# ============================================================================
echo -e "${YELLOW}[2/8] Verificando pip...${NC}"
if command -v pip3 &> /dev/null; then
    PIP_VER=$(pip3 --version 2>&1 | awk '{print $2}')
    echo -e "${GREEN}✓ pip $PIP_VER ya está instalado${NC}"
else
    echo -e "${YELLOW}⚠ pip3 NO encontrado${NC}"
    NEED_PIP=true
fi

# ============================================================================
# PASO 3: Verificar python3-venv y build tools
# ============================================================================
echo -e "${YELLOW}[3/8] Verificando python3-venv y herramientas de desarrollo...${NC}"
MISSING_PACKAGES=""

if ! dpkg -l | grep -q "^ii  python3-venv"; then
    echo -e "${YELLOW}⚠ python3-venv NO encontrado${NC}"
    NEED_VENV=true
    MISSING_PACKAGES="$MISSING_PACKAGES python3-venv"
else
    echo -e "${GREEN}✓ python3-venv instalado${NC}"
fi

if ! dpkg -l | grep -q "^ii  python3-dev"; then
    MISSING_PACKAGES="$MISSING_PACKAGES python3-dev"
    NEED_DEV_TOOLS=true
fi

if ! dpkg -l | grep -q "^ii  build-essential"; then
    MISSING_PACKAGES="$MISSING_PACKAGES build-essential"
    NEED_DEV_TOOLS=true
fi

if [ -z "$MISSING_PACKAGES" ]; then
    echo -e "${GREEN}✓ Herramientas de desarrollo instaladas${NC}"
else
    echo -e "${YELLOW}⚠ Paquetes faltantes:$MISSING_PACKAGES${NC}"
fi

# ============================================================================
# PASO 4: Verificar ODBC Driver
# ============================================================================
echo -e "${YELLOW}[4/8] Verificando ODBC Driver para SQL Server...${NC}"
if odbcinst -q -d -n "ODBC Driver 17 for SQL Server" > /dev/null 2>&1; then
    echo -e "${GREEN}✓ ODBC Driver 17 ya está instalado${NC}"
elif odbcinst -q -d -n "ODBC Driver 18 for SQL Server" > /dev/null 2>&1; then
    echo -e "${GREEN}✓ ODBC Driver 18 ya está instalado${NC}"
    echo -e "${YELLOW}⚠ Recuerda actualizar config.cfg para usar Driver 18${NC}"
else
    echo -e "${YELLOW}⚠ ODBC Driver NO encontrado${NC}"
    NEED_ODBC=true
fi

echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}RESUMEN DE VERIFICACIÓN:${NC}"
echo -e "${BLUE}========================================${NC}"

# ============================================================================
# Mostrar resumen
# ============================================================================
MISSING_COUNT=0

if [ "$NEED_PYTHON3" = true ]; then
    echo -e "${RED}✗ Python 3 - NECESITA INSTALARSE${NC}"
    ((MISSING_COUNT++))
else
    echo -e "${GREEN}✓ Python 3 - OK${NC}"
fi

if [ "$NEED_PIP" = true ]; then
    echo -e "${RED}✗ pip3 - NECESITA INSTALARSE${NC}"
    ((MISSING_COUNT++))
else
    echo -e "${GREEN}✓ pip3 - OK${NC}"
fi

if [ "$NEED_VENV" = true ] || [ "$NEED_DEV_TOOLS" = true ]; then
    echo -e "${RED}✗ Herramientas Python - NECESITAN INSTALARSE${NC}"
    ((MISSING_COUNT++))
else
    echo -e "${GREEN}✓ Herramientas Python - OK${NC}"
fi

if [ "$NEED_ODBC" = true ]; then
    echo -e "${RED}✗ ODBC Driver - NECESITA INSTALARSE${NC}"
    ((MISSING_COUNT++))
else
    echo -e "${GREEN}✓ ODBC Driver - OK${NC}"
fi

echo -e "${BLUE}========================================${NC}"
echo ""

# ============================================================================
# Instalar dependencias faltantes
# ============================================================================
if [ $MISSING_COUNT -gt 0 ]; then
    echo -e "${YELLOW}Se necesita instalar $MISSING_COUNT tipo(s) de dependencias.${NC}"
    echo ""

    # Instalar paquetes Python básicos
    if [ "$NEED_PYTHON3" = true ] || [ "$NEED_PIP" = true ] || [ "$NEED_VENV" = true ] || [ "$NEED_DEV_TOOLS" = true ]; then
        echo -e "${YELLOW}Instalando dependencias Python del sistema...${NC}"

        PACKAGES=""
        [ "$NEED_PYTHON3" = true ] && PACKAGES="$PACKAGES python3"
        [ "$NEED_PIP" = true ] && PACKAGES="$PACKAGES python3-pip"
        [ -n "$MISSING_PACKAGES" ] && PACKAGES="$PACKAGES$MISSING_PACKAGES"

        if [ -n "$PACKAGES" ]; then
            echo -e "${BLUE}Paquetes a instalar:$PACKAGES${NC}"
            # IMPORTANTE: NO hacer apt-get update completo, solo instalar paquetes
            apt-get install -y $PACKAGES
            echo -e "${GREEN}✓ Paquetes Python instalados${NC}"
        fi
    fi

    # Instalar ODBC Driver si falta
    if [ "$NEED_ODBC" = true ]; then
        echo ""
        echo -e "${YELLOW}Instalando ODBC Driver 17 para SQL Server...${NC}"
        echo -e "${YELLOW}Esto puede tardar un momento...${NC}"

        # Verificar si el repositorio de Microsoft ya está agregado
        if [ ! -f /etc/apt/sources.list.d/mssql-release.list ]; then
            echo "Agregando repositorio de Microsoft..."
            curl -sSL https://packages.microsoft.com/keys/microsoft.asc | apt-key add -
            curl -sSL https://packages.microsoft.com/config/ubuntu/22.04/prod.list > /etc/apt/sources.list.d/mssql-release.list
            # SOLO actualizar si agregamos el repositorio
            apt-get update -qq
        else
            echo -e "${GREEN}✓ Repositorio de Microsoft ya está agregado${NC}"
        fi

        # Instalar ODBC Driver
        ACCEPT_EULA=Y apt-get install -y msodbcsql17 unixodbc-dev
        echo -e "${GREEN}✓ ODBC Driver 17 instalado${NC}"
    fi

    echo ""
    echo -e "${GREEN}✓ Todas las dependencias instaladas${NC}"
else
    echo -e "${GREEN}✓ Todas las dependencias del sistema ya están instaladas${NC}"
    echo -e "${GREEN}No es necesario instalar nada adicional${NC}"
fi

echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}CONFIGURACIÓN DE LA APLICACIÓN${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# ============================================================================
# PASO 5: Crear directorios necesarios
# ============================================================================
echo -e "${YELLOW}[5/6] Creando directorios necesarios...${NC}"

# Crear directorios si no existen
mkdir -p logs
mkdir -p temp_vendor_files

echo -e "${GREEN}✓ Directorios creados${NC}"

# Limpiar archivos temporales
echo -e "${YELLOW}Limpiando archivos temporales...${NC}"
rm -rf __pycache__
rm -rf routes/
rm -rf templates/
rm -f nul
rm -f server.log
rm -f logs/*.log 2>/dev/null || true
echo -e "${GREEN}✓ Archivos temporales eliminados${NC}"

# ============================================================================
# PASO 6: Crear virtual environment e instalar dependencias
# ============================================================================
echo -e "${YELLOW}[6/6] Configurando entorno virtual Python...${NC}"

if [ -d "venv" ]; then
    echo -e "${YELLOW}⚠ Virtual environment ya existe, recreando...${NC}"
    rm -rf venv
fi

echo "Creando virtual environment..."
if python3 -m venv venv 2>/dev/null; then
    echo -e "${GREEN}✓ Virtual environment creado${NC}"
else
    echo -e "${RED}ERROR: No se pudo crear el virtual environment${NC}"
    echo -e "${YELLOW}Esto puede ser porque falta python3-venv.${NC}"
    echo ""
    echo "Por favor ejecuta manualmente:"
    echo "  sudo apt-get install -y python3-venv"
    echo ""
    echo "Luego ejecuta este script nuevamente."
    exit 1
fi

echo -e "${YELLOW}Instalando dependencias Python...${NC}"
source venv/bin/activate
pip install --upgrade pip --quiet
pip install -r requirements.txt

echo ""
echo -e "${YELLOW}Verificando instalación de paquetes Python...${NC}"
python -c "import fastapi; print('  ✓ FastAPI')"
python -c "import sqlalchemy; print('  ✓ SQLAlchemy')"
python -c "import pydantic; print('  ✓ Pydantic')"
python -c "import jwt; print('  ✓ PyJWT')"

# Verificar pyodbc
if python -c "import pyodbc" 2>/dev/null; then
    echo "  ✓ pyodbc"
else
    echo -e "  ${YELLOW}⚠ pyodbc instalado pero necesita ODBC Driver${NC}"
fi

echo ""
echo -e "${YELLOW}Configurando permisos del directorio...${NC}"
chown -R $APP_USER:$APP_USER $APP_DIR
echo -e "${GREEN}✓ Permisos configurados para usuario $APP_USER${NC}"

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}✓ Instalación completada exitosamente${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${YELLOW}Ubicación: $APP_DIR${NC}"
echo ""
echo -e "${BLUE}Próximos pasos:${NC}"
echo ""
echo "1. Verificar configuración:"
echo "   nano config/config.cfg"
echo ""
echo "2. Probar la aplicación:"
echo "   su - $APP_USER"
echo "   cd $APP_DIR"
echo "   source venv/bin/activate"
echo "   python main.py"
echo ""
echo "3. En otra terminal, probar:"
echo "   curl http://localhost:$PORT/"
echo ""
echo "4. Para ejecutar en background (con screen):"
echo "   su - $APP_USER"
echo "   cd $APP_DIR"
echo "   screen -S vendorrates"
echo "   source venv/bin/activate"
echo "   python main.py"
echo "   # Presiona Ctrl+A, luego D para detach"
echo ""
echo "5. Para reconectar al screen:"
echo "   screen -r vendorrates"
echo ""
echo "6. Ver logs:"
echo "   tail -f $APP_DIR/logs/vendor-rates-service.log"
echo ""
