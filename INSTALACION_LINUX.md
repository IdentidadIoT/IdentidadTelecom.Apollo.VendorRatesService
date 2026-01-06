# Instalación de VendorRatesService en Ubuntu 22.04

Guía de instalación simplificada para VendorRatesService en Linux.

---

## 📋 Pre-requisitos

- Ubuntu 22.04 LTS
- Acceso sudo (para instalar dependencias del sistema)
- Usuario de aplicación: `idt3vapp` (debe existir)

---

## 📦 Preparar archivos para publicar

Desde Windows, comprimir los archivos del proyecto:

```powershell
# En PowerShell (desde la carpeta del proyecto)
tar -czvf proyecto.tar.gz `
  --exclude=VendorRatesService/venv `
  --exclude=VendorRatesService/.git `
  --exclude=VendorRatesService/logs `
  --exclude=VendorRatesService/.vscode `
  --exclude='*/__pycache__/*' `
  --exclude='*.pyc' `
  VendorRatesService
```

Esto crea `proyecto.tar.gz` con todos los archivos necesarios.

---

## 🚀 Instalación en el Servidor

### PASO 1: Subir archivos al servidor

Usando WinSCP, FileZilla, o `scp`:

```bash
# Ejemplo con scp
scp proyecto.tar.gz usuario@servidor:/tmp/
```

### PASO 2: Descomprimir en el directorio deseado

```bash
# Conectar al servidor
ssh usuario@servidor

# Ir al directorio donde quieres la aplicación
# Puede ser cualquiera de estos:
cd /opt/pythonapps/
# O
cd ~/pythonapps/
# O el directorio que prefieras

# Descomprimir
tar -xzvf /tmp/proyecto.tar.gz

# Verificar que los archivos están
ls -la VendorRatesService/
```

Deberías ver:
```
main.py
config.py
requirements.txt
config/
core/
setup-linux.sh
setup-manual.sh
...
```

### PASO 3: Ejecutar instalación con sudo

```bash
# Ir al directorio de la aplicación
cd VendorRatesService/

# Dar permisos de ejecución al script
chmod +x setup-linux.sh

# Ejecutar instalación (requiere sudo)
sudo bash setup-linux.sh
```

**El script hará:**
1. ✅ Verificar Python 3, pip, python3-venv
2. ✅ Verificar ODBC Driver para SQL Server
3. ✅ Instalar SOLO las dependencias faltantes
4. ✅ Crear directorios necesarios (logs/, temp_vendor_files/)
5. ✅ Crear virtual environment
6. ✅ Instalar dependencias Python
7. ✅ Cambiar permisos al usuario `idt3vapp`

**IMPORTANTE**: El script trabaja en el directorio actual, NO copia archivos a otro lugar.

---

## ⚙️ Configuración

### Verificar configuración de base de datos

```bash
nano config/config.cfg
```

**Verifica:**
- `[Database_SQLServer]` - Credenciales Azure SQL
- `[Apollo_Auth]` - Credenciales JWT
- `[Smtp_Server]` - Configuración email
- `[AppInsights]` - Instrumentación Azure

**Si el script advirtió sobre ODBC Driver 18:**
```ini
[Database_SQLServer]
# Cambiar de:
DB_DRIVER = ODBC Driver 17 for SQL Server
# A:
DB_DRIVER = ODBC Driver 18 for SQL Server
```

---

## 🎯 Ejecutar la Aplicación

### Opción 1: Prueba manual (para testing)

```bash
# Cambiar al usuario de aplicación
su - idt3vapp

# Ir al directorio
cd /opt/pythonapps/VendorRatesService  # (o donde descomprimiste)

# Activar virtual environment
source venv/bin/activate

# Ejecutar
python main.py
```

**Deberías ver:**
```
[INFO] VendorRatesService - Iniciando microservicio
[INFO] Database: identidadvoip.database.windows.net/ApolloProdDb
[INFO] [AUTH JWT] [OK] Cliente: apollo
INFO:     Uvicorn running on http://0.0.0.0:63400 (Press CTRL+C to quit)
```

**En otra terminal, probar:**
```bash
# Health check
curl http://localhost:63400/

# Test JWT login
curl -X POST http://localhost:63400/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"apollo","password":"1d3nt1d@d5m5."}'
```

Si funciona, presiona `Ctrl+C` y continúa al siguiente paso.

---

### Opción 2: Ejecutar en background con screen (RECOMENDADO)

```bash
# Cambiar al usuario de aplicación
su - idt3vapp

# Ir al directorio
cd /opt/pythonapps/VendorRatesService

# Verificar que screen está instalado
which screen
# Si no está: sudo apt-get install screen

# Crear sesión screen
screen -S vendorrates

# Activar venv y ejecutar
source venv/bin/activate
python main.py

# Para DETACH (dejar corriendo en background):
# Presiona: Ctrl+A, luego D
```

**Comandos útiles de screen:**
```bash
# Ver sesiones activas
screen -ls

# Reconectar a la sesión
screen -r vendorrates

# Matar sesión (si necesitas reiniciar)
screen -X -S vendorrates quit
```

---

### Opción 3: Scripts de inicio/detención con nohup

Crear scripts para facilitar el manejo:

**Crear start.sh:**
```bash
nano start.sh
```

```bash
#!/bin/bash
cd /opt/pythonapps/VendorRatesService  # Ajustar ruta
source venv/bin/activate
nohup python main.py > logs/nohup.log 2>&1 &
echo $! > vendorrates.pid
echo "VendorRatesService iniciado (PID: $(cat vendorrates.pid))"
```

**Crear stop.sh:**
```bash
nano stop.sh
```

```bash
#!/bin/bash
if [ -f /opt/pythonapps/VendorRatesService/vendorrates.pid ]; then
    PID=$(cat /opt/pythonapps/VendorRatesService/vendorrates.pid)
    kill $PID
    rm /opt/pythonapps/VendorRatesService/vendorrates.pid
    echo "VendorRatesService detenido (PID: $PID)"
else
    echo "No se encontró archivo PID"
fi
```

**Dar permisos y usar:**
```bash
chmod +x start.sh stop.sh

# Iniciar
./start.sh

# Detener
./stop.sh

# Ver logs
tail -f logs/nohup.log
```

---

## 📊 Monitoreo

### Ver logs
```bash
# Logs de aplicación
tail -f logs/vendor-rates-service.log

# Logs de nohup (si usas nohup)
tail -f logs/nohup.log
```

### Ver proceso
```bash
# Ver si está corriendo
ps aux | grep "python main.py"

# Ver puerto escuchando
netstat -tlnp | grep 63400

# Ver uso de recursos
top -u idt3vapp
```

---

## 🔄 Actualización de la Aplicación

```bash
# 1. Detener aplicación
screen -X -S vendorrates quit
# O si usas nohup:
./stop.sh

# 2. Backup (importante!)
cd /opt/pythonapps/
cp -r VendorRatesService VendorRatesService.backup.$(date +%Y%m%d)

# 3. Subir nuevo proyecto.tar.gz y descomprimir
# IMPORTANTE: Esto reemplazará los archivos existentes
cd VendorRatesService/
tar -xzvf /tmp/proyecto.tar.gz --strip-components=1

# 4. Actualizar dependencias si cambió requirements.txt
source venv/bin/activate
pip install -r requirements.txt

# 5. Verificar configuración (por si hay nuevos parámetros)
nano config/config.cfg

# 6. Reiniciar con screen
screen -S vendorrates
source venv/bin/activate
python main.py
# Ctrl+A, D

# O reiniciar con nohup:
./start.sh
```

---

## ⚠️ Troubleshooting

### Error: "No module named 'pyodbc'"
```bash
source venv/bin/activate
pip install pyodbc
```

### Error: "Can't open lib 'ODBC Driver 17 for SQL Server'"
```bash
# Verificar drivers instalados
odbcinst -q -d

# Si ves "ODBC Driver 18", actualizar config.cfg:
nano config/config.cfg
# Cambiar a: DB_DRIVER = ODBC Driver 18 for SQL Server

# Si no hay ningún driver, instalar:
sudo apt-get update
sudo ACCEPT_EULA=Y apt-get install -y msodbcsql17
```

### Puerto 63400 ya en uso
```bash
# Ver qué está usando el puerto
netstat -tlnp | grep 63400

# Matar el proceso si es necesario
kill <PID>
```

### Screen no disponible
```bash
# Verificar
which screen

# Instalar
sudo apt-get install screen

# Alternativa: usar nohup (ver Opción 3 arriba)
```

### Permisos incorrectos
```bash
# Si el usuario idt3vapp no puede escribir logs
cd /opt/pythonapps/
sudo chown -R idt3vapp:idt3vapp VendorRatesService/
```

---

## 🎯 Acceso desde el Frontend C#

Configurar en [Web.config](../Frontend/Web.config):

```xml
<add key="VendorRatesBackUrl" value="http://172.16.111.67:63400" />
<add key="UsernameVendorRatesApi" value="apollo" />
<add key="PasswordVendorRatesApi" value="1d3nt1d@d5m5." />
```

Reemplazar `172.16.111.67` con la IP real del servidor Linux.

---

## ✅ Checklist de Instalación

- [ ] Archivos descomprimidos en el servidor
- [ ] Script setup-linux.sh ejecutado exitosamente
- [ ] ODBC Driver verificado (o instalado)
- [ ] Archivo config/config.cfg revisado y configurado
- [ ] Aplicación probada manualmente (curl localhost:63400)
- [ ] Screen instalado (o scripts nohup creados)
- [ ] Aplicación corriendo en background
- [ ] Frontend C# actualizado con URL del servidor
- [ ] Test end-to-end desde frontend funcionando

---

## 📍 Rutas Importantes

```
/opt/pythonapps/VendorRatesService/     # Directorio de aplicación
├── main.py                              # Punto de entrada
├── config/config.cfg                    # Configuración principal
├── logs/vendor-rates-service.log        # Logs de aplicación
├── venv/                                # Virtual environment
└── temp_vendor_files/                   # Archivos temporales
```

---

## 📞 Resumen: Comandos Rápidos

```bash
# Instalación inicial
cd /ruta/donde/descomprimiste/VendorRatesService/
sudo bash setup-linux.sh

# Iniciar (con screen)
su - idt3vapp
cd /opt/pythonapps/VendorRatesService
screen -S vendorrates
source venv/bin/activate && python main.py
# Ctrl+A, D

# Ver sesiones screen
screen -ls

# Reconectar
screen -r vendorrates

# Ver logs
tail -f logs/vendor-rates-service.log

# Test local
curl http://localhost:63400/

# Test login JWT
curl -X POST http://localhost:63400/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"apollo","password":"1d3nt1d@d5m5."}'
```
