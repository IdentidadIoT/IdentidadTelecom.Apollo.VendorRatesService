#!/bin/bash
################################################################################
# Script para detener VendorRatesService
# Ejecutar: ./stop.sh
################################################################################

# Colores
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Obtener directorio del script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Archivo PID
PID_FILE="$SCRIPT_DIR/vendorrates.pid"

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Deteniendo VendorRatesService${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Verificar si existe el archivo PID
if [ ! -f "$PID_FILE" ]; then
    echo -e "${YELLOW}⚠ No se encontró archivo PID${NC}"
    echo -e "${YELLOW}El servicio NO está corriendo (o se inició manualmente sin start.sh)${NC}"
    echo ""

    # IMPORTANTE: Solo buscar en el directorio actual para no afectar otras apps
    echo "Buscando procesos de Python ejecutando main.py en ESTE directorio..."

    # Buscar procesos con ruta completa al main.py de ESTE directorio
    FOUND_PIDS=$(ps aux | grep "[p]ython.*${SCRIPT_DIR}/main.py" | awk '{print $2}')

    if [ -n "$FOUND_PIDS" ]; then
        echo ""
        echo -e "${YELLOW}Se encontraron procesos ejecutando ${SCRIPT_DIR}/main.py:${NC}"
        echo "$FOUND_PIDS" | while read pid; do
            echo "  PID: $pid - $(ps -p $pid -o cmd= | head -c 80)..."
        done
        echo ""
        echo -e "${RED}ADVERTENCIA: Estos procesos se iniciaron fuera de start.sh${NC}"
        read -p "¿Deseas detenerlos? (s/n): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Ss]$ ]]; then
            echo "$FOUND_PIDS" | while read pid; do
                echo "Deteniendo PID $pid..."
                kill "$pid" 2>/dev/null
            done
            sleep 2
            echo -e "${GREEN}✓ Procesos detenidos${NC}"
        else
            echo "No se detuvo ningún proceso"
        fi
    else
        echo -e "${GREEN}No se encontraron procesos de VendorRatesService corriendo${NC}"
    fi
    exit 0
fi

# Leer PID del archivo
SERVICE_PID=$(cat "$PID_FILE")

# Verificar si el proceso existe
if ! ps -p "$SERVICE_PID" > /dev/null 2>&1; then
    echo -e "${YELLOW}⚠ El proceso (PID: $SERVICE_PID) no está corriendo${NC}"
    echo -e "${YELLOW}Limpiando archivo PID...${NC}"
    rm -f "$PID_FILE"
    exit 0
fi

# Detener el proceso
echo -e "${YELLOW}Deteniendo servicio (PID: $SERVICE_PID)...${NC}"
kill "$SERVICE_PID"

# Esperar a que se detenga (máximo 5 segundos)
for i in {1..5}; do
    if ! ps -p "$SERVICE_PID" > /dev/null 2>&1; then
        break
    fi
    sleep 1
    echo -e "${YELLOW}Esperando...${NC}"
done

# Verificar si se detuvo
if ps -p "$SERVICE_PID" > /dev/null 2>&1; then
    echo -e "${YELLOW}El proceso no respondió, forzando detención...${NC}"
    kill -9 "$SERVICE_PID"
    sleep 1
fi

# Limpiar archivo PID
rm -f "$PID_FILE"

echo ""
echo -e "${GREEN}✓ VendorRatesService detenido exitosamente${NC}"
echo ""
echo "Para iniciar nuevamente:"
echo "  ./start.sh"
