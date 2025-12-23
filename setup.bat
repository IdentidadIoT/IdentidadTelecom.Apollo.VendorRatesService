@echo off
REM Script de instalación inicial para OBRMs (Windows)

echo ========================================
echo OBRMs - Setup Inicial
echo ========================================
echo.

REM Verificar Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python no está instalado o no está en PATH
    pause
    exit /b 1
)

echo [1/4] Verificando Python... OK
echo.

REM Crear entorno virtual
if not exist venv (
    echo [2/4] Creando entorno virtual...
    python -m venv venv
    echo Entorno virtual creado exitosamente
) else (
    echo [2/4] Entorno virtual ya existe... SKIP
)
echo.

REM Activar entorno virtual e instalar dependencias
echo [3/4] Instalando dependencias...
call venv\Scripts\activate.bat
pip install --upgrade pip
pip install -r requirements.txt
echo.

REM Verificar que existe config.cfg
if not exist config\config.cfg (
    echo [4/4] ERROR: Falta archivo config\config.cfg
    echo.
    echo IMPORTANTE: Crea el archivo config\config.cfg con tus credenciales
    echo.
) else (
    echo [4/4] Archivo config\config.cfg encontrado... OK
)

echo ========================================
echo Setup completado exitosamente!
echo ========================================
echo.
echo Próximos pasos:
echo 1. Verifica/edita config\config.cfg con tus credenciales
echo 2. Ejecuta run.bat para iniciar el servidor
echo.
pause
