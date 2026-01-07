#!/bin/bash
################################################################################
# Script para verificar estado de VendorRatesService
# Ejecutar: ./status.sh
################################################################################

# Colores
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Obtener directorio del script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Archivo PID
PID_FILE="$SCRIPT_DIR/vendorrates.pid"

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Estado de VendorRatesService${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Verificar archivo PID
if [ -f "$PID_FILE" ]; then
    SERVICE_PID=$(cat "$PID_FILE")

    if ps -p "$SERVICE_PID" > /dev/null 2>&1; then
        echo -e "${GREEN}✓ Servicio corriendo${NC}"
        echo -e "${BLUE}  PID: $SERVICE_PID${NC}"

        # Mostrar información del proceso
        echo -e "${BLUE}  Memoria:${NC} $(ps -p $SERVICE_PID -o rss= | awk '{printf "%.2f MB", $1/1024}')"
        echo -e "${BLUE}  CPU:${NC} $(ps -p $SERVICE_PID -o %cpu= | xargs)%"
        echo -e "${BLUE}  Tiempo:${NC} $(ps -p $SERVICE_PID -o etime= | xargs)"

        # Verificar puerto
        echo ""
        if netstat -tlnp 2>/dev/null | grep ":63400" > /dev/null; then
            echo -e "${GREEN}✓ Puerto 63400 escuchando${NC}"
        else
            echo -e "${YELLOW}⚠ Puerto 63400 no está escuchando${NC}"
        fi

        # Test de conectividad
        echo ""
        echo -e "${BLUE}Probando conectividad...${NC}"
        if curl -s http://localhost:63400/ > /dev/null; then
            echo -e "${GREEN}✓ Servicio responde correctamente${NC}"
        else
            echo -e "${RED}✗ Servicio no responde${NC}"
        fi
    else
        echo -e "${RED}✗ Servicio NO está corriendo${NC}"
        echo -e "${YELLOW}  (PID guardado: $SERVICE_PID pero proceso no existe)${NC}"
    fi
else
    echo -e "${RED}✗ Servicio NO está corriendo${NC}"
    echo -e "${YELLOW}  (No se encontró archivo PID)${NC}"

    # IMPORTANTE: Solo buscar en el directorio actual para no confundir con otras apps
    # Buscar procesos con ruta completa al main.py de ESTE directorio
    FOUND_PIDS=$(ps aux | grep "[p]ython.*${SCRIPT_DIR}/main.py" | awk '{print $2}')
    if [ -n "$FOUND_PIDS" ]; then
        echo ""
        echo -e "${YELLOW}⚠ Se encontraron procesos ejecutando ${SCRIPT_DIR}/main.py:${NC}"
        echo "$FOUND_PIDS" | while read pid; do
            echo "  PID: $pid"
        done
        echo -e "${YELLOW}  Estos procesos se iniciaron manualmente (sin start.sh)${NC}"
        echo -e "${YELLOW}  Usa ./stop.sh para detenerlos${NC}"
    fi
fi

echo ""
echo -e "${BLUE}Últimas líneas del log:${NC}"
if [ -f "logs/nohup.log" ]; then
    tail -10 logs/nohup.log
else
    echo -e "${YELLOW}  (No se encontró archivo de log)${NC}"
fi

echo ""
echo -e "${BLUE}Comandos disponibles:${NC}"
echo "  ./start.sh  - Iniciar el servicio"
echo "  ./stop.sh   - Detener el servicio"
echo "  ./status.sh - Ver este estado"
echo "  tail -f logs/nohup.log - Ver logs en tiempo real"
