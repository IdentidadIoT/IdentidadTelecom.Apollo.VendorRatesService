# OBRMs - Outbound Rate Management Service

Microservicio Python FastAPI para procesamiento de archivos OBR (Outbound Rate) de vendors de telecomunicaciones.

## Descripción

OBRMs es un microservicio que migra la funcionalidad de procesamiento OBR del backend .NET principal. Implementa un patrón "fire-and-forget" donde recibe archivos Excel de vendors, responde inmediatamente, y procesa los datos en background.

### Vendors Soportados

- **Belgacom Platinum** ✅

## Características

- **Procesamiento asíncrono**: Fire-and-forget pattern para respuesta inmediata
- **Compatible con backend .NET**: Usa misma autenticación, base de datos, y lógica de negocio
- **Cache inteligente**: TTL configurable (default 30 segundos) para datos maestros
- **Logging centralizado**: Application Insights + archivo local
- **Notificaciones por email**: SMTP con plantillas HTML
- **Arquitectura escalable**: Diseñado para agregar más vendors fácilmente

## Requisitos

- Python 3.10+
- SQL Server (compartido con backend .NET)
- SMTP server para emails
- Azure Application Insights (opcional)

## Instalación

### 1. Clonar repositorio

```bash
cd C:\proyects\apollo\apollo\OBRMs
```

### 2. Crear entorno virtual

```bash
python -m venv venv
```

### 3. Activar entorno virtual

**Windows:**
```bash
venv\Scripts\activate
```

**Linux/Mac:**
```bash
source venv/bin/activate
```

### 4. Instalar dependencias

```bash
pip install -r requirements.txt
```

### 5. Configurar variables de entorno

Copiar `.env.example` a `.env` y configurar:

```bash
copy .env.example .env
```

Editar `.env` con tus credenciales:

```env
# Database
DB_SERVER=tu-servidor-sql
DB_DATABASE=tu-base-datos
DB_USERNAME=tu-usuario
DB_PASSWORD=tu-password

# OAuth2 (DEBE ser igual al backend .NET)
SECRET_KEY=clave-secreta-compartida-con-dotnet

# SMTP
SMTP_HOST=smtp.tu-servidor.com
SMTP_PORT=587
SMTP_USERNAME=tu-email@dominio.com
SMTP_PASSWORD=tu-password-smtp

# Application Insights (opcional)
APPINSIGHTS_ENABLED=true
APPINSIGHTS_INSTRUMENTATION_KEY=tu-instrumentation-key
```

## Ejecución

### Modo desarrollo

```bash
python -m app.main
```

O con uvicorn directamente:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Modo producción

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

## Uso

### Endpoint principal

**POST** `/api/obr/upload`

Carga archivo Excel de vendor para procesamiento.

**Headers:**
```
Authorization: Bearer {token-jwt}
Content-Type: multipart/form-data
```

**Form Data:**
- `file`: Archivo Excel (.xlsx)
- `vendor_name`: Nombre del vendor (ej: "Belgacom Platinum")
- `user_email`: Email para notificaciones

**Respuesta:**
```json
{
  "message": "The OBR Request was created successfully",
  "vendor_name": "Belgacom Platinum",
  "user": "usuario@dominio.com",
  "status": "processing"
}
```

### Ejemplo con cURL

```bash
curl -X POST "http://localhost:8000/api/obr/upload" \
  -H "Authorization: Bearer eyJhbGc..." \
  -F "file=@belgacom.xlsx" \
  -F "vendor_name=Belgacom Platinum" \
  -F "user_email=usuario@dominio.com"
```

### Ejemplo con Python requests

```python
import requests

url = "http://localhost:8000/api/obr/upload"
headers = {"Authorization": "Bearer your-jwt-token"}

files = {"file": open("belgacom.xlsx", "rb")}
data = {
    "vendor_name": "Belgacom Platinum",
    "user_email": "usuario@dominio.com"
}

response = requests.post(url, headers=headers, files=files, data=data)
print(response.json())
```

## Documentación API

FastAPI genera documentación automática:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/openapi.json

## Estructura del Proyecto

```
OBRMs/
├── app/
│   ├── api/
│   │   ├── models/          # DTOs y modelos Pydantic
│   │   └── routes/          # Endpoints FastAPI
│   ├── core/
│   │   ├── auth.py          # Autenticación OAuth2
│   │   ├── cache.py         # Cache en memoria con TTL
│   │   └── logging.py       # Configuración de logging
│   ├── repositories/        # Acceso a datos (SQL Server)
│   ├── services/            # Lógica de negocio
│   ├── utils/               # Utilidades (archivos, etc.)
│   ├── config.py            # Configuración centralizada
│   ├── dependencies.py      # Dependency Injection
│   └── main.py              # Aplicación principal
├── .env                     # Variables de entorno (NO commitear)
├── .env.example             # Template de variables
├── requirements.txt         # Dependencias Python
└── README.md
```

## Flujo de Procesamiento

1. **Upload**: Usuario sube archivo Excel via API
2. **Autenticación**: Valida token JWT (compartido con .NET)
3. **Respuesta inmediata**: Retorna éxito sin esperar procesamiento
4. **Background processing**:
   - Lee archivo Excel (2 hojas para Belgacom)
   - Obtiene datos maestros OBR (con cache)
   - Compara y procesa según lógica de negocio
   - Genera archivo CSV con resultados
   - Envía email con CSV adjunto
   - Limpia archivos temporales

## Compatibilidad con Backend .NET

Este microservicio está diseñado para convivir con el backend .NET:

- ✅ Misma autenticación (JWT con mismo secret key)
- ✅ Misma base de datos SQL Server
- ✅ Misma lógica de negocio (casos especiales incluidos)
- ✅ Mismo formato de emails
- ✅ Mismo comportamiento de cache

## Monitoreo

### Health Check

```bash
curl http://localhost:8000/api/obr/health
```

### Logs

Los logs se escriben en:
- **Consola**: stdout
- **Archivo**: `./logs/obrms.log`
- **Application Insights**: Si está habilitado

### Application Insights

Eventos registrados:
- `[OBR START]`: Inicio de procesamiento
- `[OBR END]`: Fin de procesamiento
- Cache hits/misses
- Errores y excepciones

## Troubleshooting

### Error de conexión a SQL Server

Verifica:
- Driver ODBC instalado: `ODBC Driver 17 for SQL Server`
- Credenciales en `.env`
- Firewall permite conexión al puerto SQL Server

### Token JWT inválido

Asegúrate que:
- `SECRET_KEY` en `.env` sea exactamente igual al del backend .NET
- Token no haya expirado
- Header sea `Authorization: Bearer {token}`

### Email no se envía

Verifica:
- Configuración SMTP en `.env`
- Puerto 587 o 465 abierto
- Credenciales SMTP correctas

## Desarrollo

### Agregar nuevo vendor

1. Crear método en `ExcelService` para leer formato del vendor
2. Crear método en `OBRService` para lógica de comparación
3. Agregar validación en `obr_routes.py`
4. Actualizar documentación

### Ejecutar tests

```bash
pytest tests/ -v
```

## Despliegue

### Como servicio Windows

Usar NSSM o crear Windows Service con pywin32

### Con Docker (opcional)

```dockerfile
FROM python:3.10-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Con systemd (Linux)

Crear `/etc/systemd/system/obrms.service`:

```ini
[Unit]
Description=OBRMs FastAPI Service
After=network.target

[Service]
User=www-data
WorkingDirectory=/opt/obrms
Environment="PATH=/opt/obrms/venv/bin"
ExecStart=/opt/obrms/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000

[Install]
WantedBy=multi-user.target
```

## Licencia

Propiedad de IdentidadIech

## Soporte

Para issues y consultas, contactar al equipo de desarrollo.
