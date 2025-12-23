#!/bin/bash
# Script de instalación inicial para OBRMs (Linux/Mac)

echo "========================================"
echo "OBRMs - Setup Inicial"
echo "========================================"
echo ""

# Verificar Python
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 no está instalado"
    exit 1
fi

echo "[1/4] Verificando Python... OK"
echo ""

# Crear entorno virtual
if [ ! -d "venv" ]; then
    echo "[2/4] Creando entorno virtual..."
    python3 -m venv venv
    echo "Entorno virtual creado exitosamente"
else
    echo "[2/4] Entorno virtual ya existe... SKIP"
fi
echo ""

# Activar entorno virtual e instalar dependencias
echo "[3/4] Instalando dependencias..."
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
echo ""

# Verificar que existe config.cfg
if [ ! -f "config/config.cfg" ]; then
    echo "[4/4] ERROR: Falta archivo config/config.cfg"
    echo ""
    echo "IMPORTANTE: Crea el archivo config/config.cfg con tus credenciales"
    echo ""
else
    echo "[4/4] Archivo config/config.cfg encontrado... OK"
fi

# Dar permisos de ejecución a run.sh
chmod +x run.sh

echo "========================================"
echo "Setup completado exitosamente!"
echo "========================================"
echo ""
echo "Próximos pasos:"
echo "1. Verifica/edita config/config.cfg con tus credenciales"
echo "2. Ejecuta ./run.sh para iniciar el servidor"
echo ""
