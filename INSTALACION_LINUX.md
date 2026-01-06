# Instalación de VendorRatesService en Linux Ubuntu 22.04

**IMPORTANTE:** Esta guía asume que ya tienes los archivos en `/opt/pythonapps/VendorRatesService/` en el servidor.

## 📋 Pre-requisitos

- Ubuntu 22.04 LTS ✅
- Python 3.10.12 ✅
- Usuario: `idt3vapp` ✅
- Acceso sudo (necesario para instalación)
- Puerto 63400 libre ✅
- Archivos en /opt/pythonapps/VendorRatesService/ ✅

---

## 🚀 Instalación Paso a Paso

### PASO 1: Ir al directorio y ejecutar instalación (necesita sudo)

```bash
# Ir al directorio
cd /opt/pythonapps/VendorRatesService

# Verificar que los archivos están
ls -la

# Dar permisos de ejecución al script
chmod +x setup-linux.sh

# IMPORTANTE: Ejecutar con sudo
sudo bash setup-linux.sh
```

**El script hará:**
1. Actualizar paquetes del sistema
2. Instalar Python y dependencias
3. Instalar ODBC Driver 17 para SQL Server
4. Crear directorios necesarios
5. Crear virtual environment
6. Instalar paquetes Python
7. Configurar permisos

---

### PASO 2: Verificar configuración de archivos

```bash
# Verificar que los archivos de configuración estén correctos
cat config/config.cfg

# Si necesitas editar algo:
sudo nano config/config.cfg
```

**Verifica especialmente:**
- `[Database_SQLServer]` - Credenciales de Azure SQL
- `[Smtp_Server]` - Configuración de email
- `[AppInsights]` - enabled = true
- `[Apollo_Auth]` - Credenciales JWT (cliente, password, secret)

**Configuración importante:**
Asegúrate que el puerto esté configurado correctamente en `config.cfg`:
```ini
[General]
port = 63400
```

---

### PASO 3: Probar la aplicación manualmente

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
# Test de health check
curl http://localhost:63400/

# Test de login JWT
curl -X POST http://localhost:63400/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"apollo","password":"1d3nt1d@d5m5."}'

# Ver documentación API
curl http://localhost:63400/docs
```

**Probar desde tu máquina Windows (reemplaza IP):**
```bash
# Test de login desde red
curl -X POST http://172.16.111.67:63400/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"apollo","password":"1d3nt1d@d5m5."}'
```

Si funciona, presiona `Ctrl+C` para detener y continúa al siguiente paso.

---

### PASO 4: Crear servicio systemd (necesita sudo)

```bash
# Copiar archivo de servicio
sudo cp vendorrates.service /etc/systemd/system/

# Recargar systemd
sudo systemctl daemon-reload

# Habilitar servicio para inicio automático
sudo systemctl enable vendorrates.service

# Iniciar servicio
sudo systemctl start vendorrates.service

# Verificar estado
sudo systemctl status vendorrates.service
```

**Comandos útiles:**
```bash
# Ver logs del servicio
sudo journalctl -u vendorrates.service -f

# Reiniciar servicio
sudo systemctl restart vendorrates.service

# Detener servicio
sudo systemctl stop vendorrates.service

# Ver logs de la aplicación
tail -f /opt/pythonapps/VendorRatesService/logs/vendor-rates-service.log
```

---

### PASO 5: Actualizar frontend C# para apuntar al servidor Linux

En tu `Web.config` del frontend C#:

```xml
<!-- ANTES (localhost) -->
<add key="VendorRatesBackUrl" value="http://localhost:63400" />

<!-- DESPUÉS (servidor Linux con IP) -->
<add key="VendorRatesBackUrl" value="http://172.16.111.67:63400" />

<!-- O si usas hostname -->
<add key="VendorRatesBackUrl" value="http://mi1-dev-app067:63400" />
```

**IMPORTANTE:** Nota que ahora incluimos el puerto **:63400** porque accedemos directamente al servicio Python sin Nginx.

Las credenciales JWT ya deben estar configuradas:
```xml
<add key="UsernameVendorRatesApi" value="apollo" />
<add key="PasswordVendorRatesApi" value="1d3nt1d@d5m5." />
```

---

### PASO 6: Verificar que todo funciona

```bash
# 1. Verificar servicio
sudo systemctl status vendorrates.service

# 2. Test desde localhost
curl http://localhost:63400/

# 3. Test de login
curl -X POST http://localhost:63400/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"apollo","password":"1d3nt1d@d5m5."}'

# 4. Ver logs en tiempo real
tail -f /opt/pythonapps/VendorRatesService/logs/vendor-rates-service.log
```

**Desde tu máquina Windows:**
```
http://172.16.111.67:63400/docs
```

---

## 🔧 Troubleshooting

### Error: "No module named 'pyodbc'"
```bash
cd /opt/pythonapps/VendorRatesService
source venv/bin/activate
pip install pyodbc
```

### Error: "Can't open lib 'ODBC Driver 17 for SQL Server'"
```bash
# Verificar instalación de ODBC Driver
odbcinst -q -d -n "ODBC Driver 17 for SQL Server"

# Si no está instalado, ejecutar:
sudo apt-get update
ACCEPT_EULA=Y sudo apt-get install -y msodbcsql17

# Si tienes Driver 18, actualiza config.cfg:
nano config/config.cfg
# Cambiar: DB_DRIVER = ODBC Driver 18 for SQL Server
```

### Servicio no inicia
```bash
# Ver logs detallados
sudo journalctl -u vendorrates.service -n 100 --no-pager

# Verificar permisos
ls -la /opt/pythonapps/VendorRatesService
sudo chown -R idt3vapp:idt3vapp /opt/pythonapps/VendorRatesService

# Probar manualmente
cd /opt/pythonapps/VendorRatesService
source venv/bin/activate
python main.py
```

### Puerto 63400 ya en uso
```bash
# Ver qué está usando el puerto
sudo netstat -tlnp | grep 63400

# Matar proceso si es necesario
sudo kill <PID>

# O cambiar puerto en config/config.cfg:
[General]
port = 63401
```

### Error de conexión desde Windows
```bash
# Verificar firewall en servidor Linux
sudo ufw status
sudo ufw allow 63400/tcp

# Verificar que la aplicación escucha en todas las interfaces (0.0.0.0)
netstat -tlnp | grep 63400
# Debe mostrar: 0.0.0.0:63400 (NO 127.0.0.1:63400)
```

### Application Insights falla
```bash
# Si ves warning de Application Insights, es normal
# La app funcionará sin problemas
# Para deshabilitar, edita config.cfg:
[AppInsights]
enabled = false
```

---

## 📊 Monitoreo

### Ver logs en tiempo real
```bash
# Logs de aplicación
tail -f /opt/pythonapps/VendorRatesService/logs/vendor-rates-service.log

# Logs de servicio systemd
sudo journalctl -u vendorrates.service -f

# Ver solo errores
sudo journalctl -u vendorrates.service -p err
```

### Verificar uso de recursos
```bash
# Memoria y CPU
top -p $(pgrep -f "python.*main.py")

# Conexiones activas
ss -tnp | grep :63400

# Espacio en disco
df -h /opt/pythonapps/VendorRatesService
```

### Verificar conectividad
```bash
# Desde el servidor
curl http://localhost:63400/

# Desde otra máquina en la red
curl http://172.16.111.67:63400/

# Ver qué interfaces están escuchando
netstat -tlnp | grep 63400
```

---

## 🔄 Actualización de la aplicación

```bash
# 1. Detener servicio
sudo systemctl stop vendorrates.service

# 2. Hacer backup
sudo cp -r /opt/pythonapps/VendorRatesService /opt/pythonapps/VendorRatesService.backup.$(date +%Y%m%d)

# 3. Subir nuevos archivos (desde Windows con WinSCP/scp)
# O copiar archivos manualmente

# 4. Actualizar dependencias si es necesario
cd /opt/pythonapps/VendorRatesService
source venv/bin/activate
pip install -r requirements.txt

# 5. Verificar configuración
cat config/config.cfg

# 6. Reiniciar servicio
sudo systemctl start vendorrates.service

# 7. Verificar estado
sudo systemctl status vendorrates.service
tail -f logs/vendor-rates-service.log
```

---

## ✅ Checklist Final

- [ ] Script setup-linux.sh ejecutado correctamente
- [ ] ODBC Driver 17 instalado y funcionando
- [ ] Archivos de configuración revisados (config.cfg)
- [ ] Aplicación probada manualmente (curl localhost:63400)
- [ ] Servicio systemd creado y funcionando
- [ ] Puerto 63400 accesible desde red (firewall configurado)
- [ ] Frontend C# actualizado con URL del servidor:63400
- [ ] Test de login JWT desde frontend exitoso
- [ ] Test end-to-end: subir archivo OBR funcionando

---

## 📞 Soporte

Si necesitas ayuda, revisa en orden:

1. **Logs de aplicación:**
   ```bash
   tail -f /opt/pythonapps/VendorRatesService/logs/vendor-rates-service.log
   ```

2. **Logs de systemd:**
   ```bash
   sudo journalctl -u vendorrates.service -n 100
   ```

3. **Estado del servicio:**
   ```bash
   sudo systemctl status vendorrates.service
   ```

4. **Verificar conectividad:**
   ```bash
   curl -v http://localhost:63400/
   netstat -tlnp | grep 63400
   ```

---

## 🔗 URLs de Acceso

**Desde el servidor Linux:**
- Health check: `http://localhost:63400/`
- Documentación: `http://localhost:63400/docs`
- Login: `http://localhost:63400/api/auth/login`

**Desde Windows (red interna):**
- Health check: `http://172.16.111.67:63400/`
- Documentación: `http://172.16.111.67:63400/docs`
- API endpoints: `http://172.16.111.67:63400/api/vendorRates/...`

**NOTA:** Si no puedes acceder desde Windows, verifica:
1. Firewall en Linux: `sudo ufw allow 63400/tcp`
2. La app escucha en 0.0.0.0: `netstat -tlnp | grep 63400`
3. No hay firewall de red bloqueando el puerto
