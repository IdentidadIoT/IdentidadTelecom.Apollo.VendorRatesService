#!/bin/bash
################################################################################
# VendorRatesService - Instalación Inteligente (Segura)
# Para usuario: idt3vapp
# Ejecutar desde: ~/pythonapps/VendorRatesService/
#
# Este script:
# - Verifica PRIMERO si algo ya está instalado
# - SOLO instala lo que falta
# - NO toca repositorios del sistema innecesariamente
# - Pide confirmación antes de instalar paquetes del sistema
################################################################################

# NO usar set -e para que el script continue aunque falle algún comando opcional

# Colores
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

# Variables
APP_NAME="VendorRatesService"
APP_DIR="$(pwd)"
PYTHON_VERSION="3.10"
PORT="63400"

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}VendorRatesService - Instalación Segura${NC}"
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

echo -e "${BLUE}[VERIFICACIÓN] Revisando dependencias del sistema...${NC}"
echo ""

# Variables para rastrear qué necesita instalarse
NEED_PYTHON3=false
NEED_PIP=false
NEED_VENV=false
NEED_ODBC=false

# ============================================================================
# PASO 1: Verificar Python 3
# ============================================================================
echo -e "${YELLOW}[1/6] Verificando Python 3...${NC}"
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
echo -e "${YELLOW}[2/6] Verificando pip...${NC}"
if command -v pip3 &> /dev/null; then
    PIP_VER=$(pip3 --version 2>&1 | awk '{print $2}')
    echo -e "${GREEN}✓ pip $PIP_VER ya está instalado${NC}"
else
    echo -e "${YELLOW}⚠ pip3 NO encontrado${NC}"
    NEED_PIP=true
fi

# ============================================================================
# PASO 3: Verificar python3-venv
# ============================================================================
echo -e "${YELLOW}[3/6] Verificando python3-venv...${NC}"
if dpkg -l | grep -q python3-venv; then
    echo -e "${GREEN}✓ python3-venv ya está instalado${NC}"
else
    echo -e "${YELLOW}⚠ python3-venv NO encontrado${NC}"
    NEED_VENV=true
fi

# ============================================================================
# PASO 4: Verificar ODBC Driver
# ============================================================================
echo -e "${YELLOW}[4/6] Verificando ODBC Driver para SQL Server...${NC}"
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
# Mostrar resumen y pedir confirmación si falta algo
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

if [ "$NEED_VENV" = true ]; then
    echo -e "${RED}✗ python3-venv - NECESITA INSTALARSE${NC}"
    ((MISSING_COUNT++))
else
    echo -e "${GREEN}✓ python3-venv - OK${NC}"
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
# Si falta algo, pedir permisos sudo para instalar
# ============================================================================
if [ $MISSING_COUNT -gt 0 ]; then
    echo -e "${YELLOW}Se necesita instalar $MISSING_COUNT dependencia(s) del sistema.${NC}"
    echo -e "${YELLOW}Esto requiere permisos sudo.${NC}"
    echo ""

    read -p "¿Deseas instalar las dependencias faltantes? (s/n): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Ss]$ ]]; then
        echo -e "${RED}Instalación cancelada por el usuario.${NC}"
        echo ""
        echo "Para continuar sin instalar dependencias del sistema:"
        echo "  - Asegúrate de que Python 3 y pip estén instalados"
        echo "  - Pide a un admin que instale las dependencias faltantes"
        exit 1
    fi

    # Verificar permisos sudo
    if ! sudo -n true 2>/dev/null; then
        echo ""
        echo -e "${YELLOW}Se requiere sudo para instalar dependencias.${NC}"
        echo "Ingresa tu contraseña cuando se solicite:"
        sudo -v
    fi

    # Instalar dependencias faltantes
    if [ "$NEED_PYTHON3" = true ] || [ "$NEED_PIP" = true ] || [ "$NEED_VENV" = true ]; then
        echo ""
        echo -e "${YELLOW}Instalando dependencias Python...${NC}"

        # IMPORTANTE: NO hacer apt-get update completo
        # Solo instalar paquetes específicos
        PACKAGES=""
        [ "$NEED_PYTHON3" = true ] && PACKAGES="$PACKAGES python3"
        [ "$NEED_PIP" = true ] && PACKAGES="$PACKAGES python3-pip"
        [ "$NEED_VENV" = true ] && PACKAGES="$PACKAGES python3-venv"

        if [ -n "$PACKAGES" ]; then
            echo -e "${BLUE}Instalando:$PACKAGES${NC}"
            sudo apt-get install -y $PACKAGES
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
            curl -sSL https://packages.microsoft.com/keys/microsoft.asc | sudo apt-key add -
            curl -sSL https://packages.microsoft.com/config/ubuntu/22.04/prod.list | sudo tee /etc/apt/sources.list.d/mssql-release.list
            sudo apt-get update -qq
        fi

        # Instalar ODBC Driver
        sudo ACCEPT_EULA=Y apt-get install -y msodbcsql17 unixodbc-dev
        echo -e "${GREEN}✓ ODBC Driver 17 instalado${NC}"
    fi

    echo ""
    echo -e "${GREEN}✓ Todas las dependencias del sistema están instaladas${NC}"
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
# PASO 5: Crear directorios
# ============================================================================
echo -e "${YELLOW}[5/6] Creando directorios necesarios...${NC}"
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
    echo -e "${YELLOW}⚠ Virtual environment ya existe${NC}"
    read -p "¿Deseas recrearlo? (s/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Ss]$ ]]; then
        echo "Eliminando venv anterior..."
        rm -rf venv
        echo "Creando nuevo virtual environment..."
        if ! python3 -m venv venv 2>/dev/null; then
            echo -e "${RED}ERROR: No se pudo crear el virtual environment${NC}"
            echo -e "${YELLOW}Instala python3-venv: sudo apt-get install -y python3-venv${NC}"
            exit 1
        fi
    fi
else
    echo "Creando virtual environment..."
    if ! python3 -m venv venv 2>/dev/null; then
        echo -e "${RED}ERROR: No se pudo crear el virtual environment${NC}"
        echo -e "${YELLOW}Instala python3-venv: sudo apt-get install -y python3-venv${NC}"
        exit 1
    fi
fi

if [ ! -d "venv" ]; then
    echo -e "${RED}ERROR: No existe el directorio venv${NC}"
    exit 1
fi

echo -e "${YELLOW}Instalando dependencias Python...${NC}"
source venv/bin/activate
pip install --upgrade pip --quiet
pip install -r requirements.txt

echo ""
echo -e "${YELLOW}Verificando instalación...${NC}"
python -c "import fastapi; print('  ✓ FastAPI')"
python -c "import sqlalchemy; print('  ✓ SQLAlchemy')"
python -c "import pydantic; print('  ✓ Pydantic')"
python -c "import jwt; print('  ✓ PyJWT')"

# Verificar pyodbc (puede fallar si no hay ODBC driver)
if python -c "import pyodbc" 2>/dev/null; then
    echo "  ✓ pyodbc"
else
    echo -e "  ${YELLOW}⚠ pyodbc instalado pero necesita ODBC Driver${NC}"
fi

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
echo "6. Ver logs:"
echo "   tail -f logs/vendor-rates-service.log"
echo ""
