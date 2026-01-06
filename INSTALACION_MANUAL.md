# Instalación Manual de VendorRatesService (Sin Sudo)

Guía para instalar VendorRatesService sin permisos de administrador.

**IMPORTANTE:** Esta guía asume que ya tienes los archivos en `~/pythonapps/VendorRatesService/` en el servidor.
comando para comprimir los archivos a publicar.
tar -czvf proyecto.tar.gz `
>>   --exclude=VendorRatesService/venv `
>>   --exclude=VendorRatesService/.git `
>>   --exclude=VendorRatesService/logs `
>>   --exclude=VendorRatesService/.vscode `
>>   --exclude='*/__pycache__/*' `
>>   --exclude='*.pyc' `
>>   VendorRatesService
---
comando para descomprimir
tar -xzvf proyecto.tar.gz

## 📋 Pre-requisitos Verificados

✅ Ubuntu 22.04 LTS
✅ Python 3.10.12
✅ pip instalado
✅ Usuario: idt3vapp
✅ Archivos en ~/pythonapps/VendorRatesService/
⚠️ ODBC Driver (verificaremos si está)
⚠️ Nginx (admin necesita configurar)

---

## 🚀 Instalación Rápida

### PASO 1: Ir al directorio y ejecutar instalación

```bash
# Ir al directorio
cd ~/pythonapps/VendorRatesService

# Verificar que los archivos están
ls -la

# Dar permisos de ejecución al script
chmod +x setup-manual.sh

# Ejecutar instalación (SIN sudo)
bash setup-manual.sh
```

**El script hará:**
1. ✅ Verificar Python y pip
2. ✅ Verificar ODBC Driver (advertirá si falta)
3. ✅ Crear directorios necesarios
4. ✅ Limpiar archivos temporales
5. ✅ Crear virtual environment
6. ✅ Instalar dependencias Python

---

### PASO 2: Verificar configuración

```bash
# Ver configuración actual
cat config/config.cfg

# Editar si es necesario
nano config/config.cfg
nano config/auth_config.cfg
```

**Verifica:**
- `[Database_SQLServer]` - Credenciales correctas
- `[Smtp_Server]` - Configuración email correcta
- `[AppInsights]` - enabled = true

**Si el script advirtió sobre ODBC Driver 18:**
```ini
[Database_SQLServer]
# Cambiar de:
DB_DRIVER = ODBC Driver 17 for SQL Server
# A:
DB_DRIVER = ODBC Driver 18 for SQL Server
```

---

### PASO 3: Probar la aplicación

```bash
# Activar virtual environment
source venv/bin/activate

# Ejecutar aplicación
python main.py
```

**Deberías ver:**
```
[INFO] VendorRatesService - Iniciando microservicio
[INFO] Database: identidadvoip.database.windows.net/ApolloProdDb
[INFO] [AUTH JWT] [OK] Cliente: apollo
INFO:     Uvicorn running on http://0.0.0.0:63400 (Press CTRL+C to quit)
```

**Probar en otra terminal:**
```bash
# Health check
curl http://localhost:63400/

# Test JWT login
curl -X POST http://localhost:63400/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"apollo","password":"1d3nt1d@d5m5."}'
```

Si funciona correctamente, presiona `Ctrl+C` y continúa al siguiente paso.

---

### PASO 4: Ejecutar en background con screen

Ya que **no puedes crear servicio systemd sin sudo**, usaremos `screen`:

```bash
# Verificar si screen está instalado
which screen

# Si no está instalado, pide a un admin:
# sudo apt-get install screen

# Crear sesión screen
screen -S vendorrates

# Dentro de screen:
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

### PASO 5: Pedir al admin que configure Nginx

Como **no tienes permisos sudo**, necesitas que un administrador ejecute:

```bash
# Comandos para el admin (desde el directorio de la app):
cd ~/pythonapps/VendorRatesService
sudo cp vendorrates-nginx.conf /etc/nginx/sites-available/vendorrates

sudo ln -s /etc/nginx/sites-available/vendorrates \
           /etc/nginx/sites-enabled/

sudo nginx -t

sudo systemctl reload nginx
```

O envíale el archivo `vendorrates-nginx.conf` para que lo revise primero.

---

### PASO 6: Verificar acceso completo

Después de que el admin configure Nginx:

```bash
# Test directo (siempre debe funcionar)
curl http://localhost:63400/

# Test a través de Nginx
curl http://localhost/api/auth/login \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{"username":"apollo","password":"1d3nt1d@d5m5."}'
```

---

## 🔧 Alternativa: Ejecutar con nohup (sin screen)

Si no tienes `screen`, puedes usar `nohup`:

```bash
# Activar venv
source venv/bin/activate

# Ejecutar en background
nohup python main.py > logs/nohup.log 2>&1 &

# Ver el PID
echo $!

# Ver logs
tail -f logs/nohup.log

# Para detener:
ps aux | grep "python main.py"
kill <PID>
```

---

## 🔧 Scripts de inicio/detención

Crea scripts para facilitar el inicio/detención:

```bash
nano start.sh
```

**Contenido de start.sh:**
```bash
#!/bin/bash
cd ~/pythonapps/VendorRatesService
source venv/bin/activate
nohup python main.py > logs/nohup.log 2>&1 &
echo $! > vendorrates.pid
echo "VendorRatesService iniciado (PID: $(cat vendorrates.pid))"
```

**Contenido de stop.sh:**
```bash
#!/bin/bash
if [ -f ~/pythonapps/VendorRatesService/vendorrates.pid ]; then
    PID=$(cat ~/pythonapps/VendorRatesService/vendorrates.pid)
    kill $PID
    rm ~/pythonapps/VendorRatesService/vendorrates.pid
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

## 📊 Monitoreo sin sudo

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

## 🔄 Actualización de la aplicación

```bash
# 1. Detener aplicación
screen -X -S vendorrates quit
# O si usas nohup:
./stop.sh

# 2. Backup (importante!)
cp -r ~/pythonapps/VendorRatesService ~/pythonapps/VendorRatesService.backup.$(date +%Y%m%d)

# 3. Copiar nuevos archivos
# (Asume que ya subiste los archivos nuevos y reemplazaron los viejos)

# 4. Actualizar dependencias si es necesario
source venv/bin/activate
pip install -r requirements.txt

# 5. Reiniciar con screen
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
cd ~/pythonapps/VendorRatesService
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

# Si no hay ningún driver, pedir al admin:
# sudo apt-get install -y msodbcsql17
```

### Puerto 63400 ya en uso
```bash
# Ver qué está usando el puerto
netstat -tlnp | grep 63400

# Si es tu proceso viejo:
kill <PID>

# Cambiar puerto en main.py si es necesario
nano ~/pythonapps/VendorRatesService/main.py
# Línea 124: port=63401  (o el puerto que prefieras)
```

### Screen no disponible
```bash
# Verificar
which screen

# Pedir al admin que instale:
# sudo apt-get install screen

# Alternativa: usar nohup (ver sección arriba)
```

---

## ✅ Checklist de Instalación Manual

- [ ] Archivos subidos al servidor
- [ ] Script setup-manual.sh ejecutado exitosamente
- [ ] ODBC Driver verificado (o actualizado a Driver 18)
- [ ] Archivos config.cfg y auth_config.cfg revisados
- [ ] Aplicación probada manualmente (curl localhost:63400)
- [ ] Screen instalado o nohup configurado
- [ ] Aplicación corriendo en background
- [ ] Admin configuró Nginx
- [ ] Test desde Nginx exitoso (curl localhost/api/auth/login)
- [ ] Frontend C# actualizado con URL del servidor
- [ ] Test end-to-end desde frontend funcionando

---

## 📞 Resumen: Qué necesitas del Admin

Ya que no tienes sudo, necesitarás que un administrador:

1. **Instale ODBC Driver (si falta):**
   ```bash
   sudo apt-get update
   ACCEPT_EULA=Y sudo apt-get install -y msodbcsql17
   ```

2. **Instale screen (si falta):**
   ```bash
   sudo apt-get install -y screen
   ```

3. **Configure Nginx:**
   ```bash
   sudo cp /home/idt3vapp/pythonapps/VendorRatesService/vendorrates-nginx.conf \
           /etc/nginx/sites-available/vendorrates
   sudo ln -s /etc/nginx/sites-available/vendorrates /etc/nginx/sites-enabled/
   sudo nginx -t
   sudo systemctl reload nginx
   ```

**Todo lo demás lo puedes hacer tú mismo** ✅

---

## 🎯 Comandos Rápidos de Referencia

```bash
# Iniciar (con screen)
screen -S vendorrates
cd ~/pythonapps/VendorRatesService && source venv/bin/activate && python main.py

# Ver sesiones screen
screen -ls

# Reconectar
screen -r vendorrates

# Ver logs
tail -f ~/pythonapps/VendorRatesService/logs/vendor-rates-service.log

# Ver proceso
ps aux | grep "python main.py"

# Test local
curl http://localhost:63400/

# Test con Nginx
curl http://localhost/api/auth/login -X POST \
  -H "Content-Type: application/json" \
  -d '{"username":"apollo","password":"1d3nt1d@d5m5."}'
```
