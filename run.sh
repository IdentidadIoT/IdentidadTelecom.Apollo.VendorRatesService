#!/bin/bash
# Script para ejecutar OBRMs en Linux/Mac

echo "========================================"
echo "OBRMs - Outbound Rate Management Service"
echo "========================================"
echo ""

# Activar entorno virtual
if [ -f "venv/bin/activate" ]; then
    echo "Activando entorno virtual..."
    source venv/bin/activate
else
    echo "ERROR: Entorno virtual no encontrado"
    echo "Ejecuta primero: python -m venv venv"
    exit 1
fi

# Verificar que existe config.cfg
if [ ! -f "config/config.cfg" ]; then
    echo "ERROR: Archivo config/config.cfg no encontrado"
    echo "Asegurate de que existe el archivo de configuracion"
    exit 1
fi

echo ""
echo "Iniciando servidor FastAPI..."
echo "URL: http://localhost:8000"
echo "Docs: http://localhost:8000/docs"
echo ""

# Ejecutar aplicación
python main.py
