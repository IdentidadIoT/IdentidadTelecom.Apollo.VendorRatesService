@echo off
REM Script para ejecutar OBRMs en Windows

echo ========================================
echo OBRMs - Outbound Rate Management Service
echo ========================================
echo.

REM Activar entorno virtual
if exist venv\Scripts\activate.bat (
    echo Activando entorno virtual...
    call venv\Scripts\activate.bat
) else (
    echo ERROR: Entorno virtual no encontrado
    echo Ejecuta primero: python -m venv venv
    pause
    exit /b 1
)

REM Verificar que existe config.cfg
if not exist config\config.cfg (
    echo ERROR: Archivo config\config.cfg no encontrado
    echo Asegurate de que existe el archivo de configuracion
    pause
    exit /b 1
)

echo.
echo Iniciando servidor FastAPI...
echo URL: http://localhost:8000
echo Docs: http://localhost:8000/docs
echo.

REM Ejecutar aplicación
python main.py

pause
