#!/bin/bash
################################################################################
# Script para iniciar VendorRatesService
# Ejecutar: ./start.sh
################################################################################

# Colores
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Obtener directorio del script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Archivo para guardar el PID
PID_FILE="$SCRIPT_DIR/vendorrates.pid"

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Iniciando VendorRatesService${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Verificar si ya está corriendo
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if ps -p "$OLD_PID" > /dev/null 2>&1; then
        echo -e "${YELLOW}⚠ El servicio ya está corriendo (PID: $OLD_PID)${NC}"
        echo ""
        echo "Para reiniciar, primero ejecuta:"
        echo "  ./stop.sh"
        exit 1
    else
        echo -e "${YELLOW}⚠ Limpiando PID antiguo...${NC}"
        rm -f "$PID_FILE"
    fi
fi

# Verificar que existe main.py
if [ ! -f "main.py" ]; then
    echo -e "${RED}ERROR: No se encontró main.py${NC}"
    echo "Asegúrate de ejecutar este script desde el directorio VendorRatesService"
    exit 1
fi

# Verificar que existe el virtual environment
if [ ! -d "venv" ]; then
    echo -e "${RED}ERROR: No existe el virtual environment${NC}"
    echo ""
    echo "Por favor ejecuta primero:"
    echo "  sudo bash setup-linux.sh"
    echo "O:"
    echo "  bash setup-manual.sh"
    exit 1
fi

# Verificar si el puerto 63400 está en uso
echo -e "${YELLOW}Verificando puerto 63400...${NC}"
PORT_IN_USE=$(netstat -tlnp 2>/dev/null | grep ":63400 " || ss -tlnp 2>/dev/null | grep ":63400 " || true)

if [ -n "$PORT_IN_USE" ]; then
    echo -e "${RED}✗ El puerto 63400 ya está en uso${NC}"
    echo ""
    echo "Proceso usando el puerto:"
    echo "$PORT_IN_USE"
    echo ""

    # Intentar extraer el PID del proceso
    PORT_PID=$(echo "$PORT_IN_USE" | grep -oP '(?<=pid=)\d+|(?<=,pid=)\d+|(?<=users:\(\(")\S+(?=",pid=)' | grep -oP '\d+' || echo "")

    if [ -z "$PORT_PID" ]; then
        # Buscar de otra forma
        PORT_PID=$(lsof -ti:63400 2>/dev/null || fuser 63400/tcp 2>/dev/null | awk '{print $1}' || echo "")
    fi

    if [ -n "$PORT_PID" ]; then
        echo "PID del proceso: $PORT_PID"
        echo "Comando: $(ps -p $PORT_PID -o cmd= 2>/dev/null || echo 'Desconocido')"
        echo ""

        # Verificar si es nuestro servicio
        if ps -p $PORT_PID -o cmd= 2>/dev/null | grep -q "${SCRIPT_DIR}/main.py"; then
            echo -e "${YELLOW}Este es un proceso de VendorRatesService${NC}"
            echo ""
            read -p "¿Deseas detenerlo y reiniciar? (s/n): " -n 1 -r
            echo
            if [[ $REPLY =~ ^[Ss]$ ]]; then
                echo "Deteniendo proceso anterior..."
                kill $PORT_PID 2>/dev/null
                sleep 3
                echo -e "${GREEN}✓ Proceso anterior detenido${NC}"
            else
                echo "Operación cancelada"
                exit 1
            fi
        else
            echo -e "${RED}⚠ ADVERTENCIA: Este NO es VendorRatesService${NC}"
            echo "No es seguro detener este proceso automáticamente"
            echo ""
            echo "Para detenerlo manualmente:"
            echo "  sudo kill $PORT_PID"
            echo ""
            echo "O cambia el puerto en config/config.cfg"
            exit 1
        fi
    else
        echo -e "${YELLOW}No se pudo identificar el PID del proceso${NC}"
        echo ""
        echo "Ejecuta manualmente:"
        echo "  sudo netstat -tlnp | grep :63400"
        echo "  sudo lsof -i :63400"
        exit 1
    fi
fi

# Activar virtual environment e iniciar servicio
echo -e "${YELLOW}Activando virtual environment...${NC}"
source venv/bin/activate

echo -e "${YELLOW}Iniciando servicio en background...${NC}"
nohup python main.py > logs/nohup.log 2>&1 &
SERVICE_PID=$!

# Guardar PID
echo "$SERVICE_PID" > "$PID_FILE"

# Esperar un momento para verificar que inició correctamente
sleep 2

if ps -p "$SERVICE_PID" > /dev/null 2>&1; then
    echo ""
    echo -e "${GREEN}✓ VendorRatesService iniciado exitosamente${NC}"
    echo -e "${GREEN}  PID: $SERVICE_PID${NC}"
    echo -e "${GREEN}  Puerto: 63400${NC}"
    echo ""
    echo "Comandos útiles:"
    echo "  ./stop.sh          - Detener el servicio"
    echo "  tail -f logs/nohup.log - Ver logs en tiempo real"
    echo "  curl http://localhost:63400/ - Probar el servicio"
else
    echo ""
    echo -e "${RED}✗ Error al iniciar el servicio${NC}"
    echo ""
    echo "Ver logs para más detalles:"
    echo "  tail -50 logs/nohup.log"
    rm -f "$PID_FILE"
    exit 1
fi
