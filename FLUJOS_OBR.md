# FLUJOS OBR - COMPARACIÓN

## FLUJO VIEJO (.NET Monolito)
la logica de algunos vendors estan aqui 
"C:\proyects\apollo\apollo\Backend\IdentidatTelecom.Apollo.BusinessLogic\ProcessRatesByCustomerBusiness.cs"
```
Browser
  ↓ POST /ProcessRatesByCustomer/UploadVendorFileForOBRVendor
Frontend Controller (ProcessRatesByCustomerController.cs:488)
  ↓ ApolloApiRest.UploadVendorOBRFile()
Backend .NET API
  ↓ POST /api/ProcessRatesByCustomer/PostVendorOBRFile
Controller → ProcessRatesByCustomerBusiness.VendorOBRDataSendForCompareToMera()
  ↓ switch(VendorName) → case "Sunrise"
GenerateOBRSunriseFile()
  ↓ GetVendorSunriseData() - Lee Excel
  ↓ Lógica comparación Sunrise en C#
  ↓ Itera OBR Master Data
  ↓ Filtra por origin_mapping + price_list
  ↓ Lógica especial routing "Vodafone" vs otros
  ↓ GroupBy para eliminar duplicados
  ↓ Genera CSV con StreamWriter
  ↓ Envia email con _SenderEmailHelper
Fin
```

**Archivo:** `Backend\IdentidatTelecom.Apollo.BusinessLogic\ProcessRatesByCustomerBusiness.cs:3927`

**URL Backend:** `{backUrl}/api/ProcessRatesByCustomer/PostVendorOBRFile`

**Formato CSV:** `{item.Rate}` sin formato fijo de decimales

---

## FLUJO NUEVO (Microservicio Python)

```
Browser
  ↓ POST /ProcessRatesByCustomer/UploadVendorFileForOBRVendor
Frontend Controller (ProcessRatesByCustomerController.cs:488)
  ↓ ApolloApiRest.UploadVendorOBRFile()
VendorRatesService Python (puerto 63400)
  ↓ POST /api/vendorRates/fileObrComparison
worker_obr.py:upload_vendor_rates()
  ↓ Crea thread daemon background
  ↓ Thread ejecuta process_sunrise_file()
obr_service.py:process_sunrise_file()
  ↓ save_temp_file()
  ↓ excel_service.read_sunrise_price_list()
  ↓ excel_service.read_sunrise_origin_mapping()
  ↓ _get_obr_master_data_cached()
  ↓ _compare_sunrise_data() - Comparación
  ↓ _generate_csv_file(decimal_places=4, use_variable_decimals=False)
  ↓ email_service.send_obr_success_email()
Fin
```

**Archivo:** `VendorRatesService\core\obr_service.py:144`

**URL Microservicio:** `{VendorRatesBackUrl}/api/vendorRates/fileObrComparison`

**Config:** `Web.config` → `<add key="VendorRatesBackUrl" value="http://localhost:63400" />`

**Formato CSV:** `f"{float(price):.4f}"` - 4 decimales fijos para Sunrise

---

## DIFERENCIAS CLAVE

| Aspecto | VIEJO | NUEVO |
|---------|-------|-------|
| **Backend** | .NET monolito | Python FastAPI microservicio |
| **Endpoint** | `/api/ProcessRatesByCustomer/PostVendorOBRFile` | `/api/vendorRates/fileObrComparison` |
| **Puerto** | Mismo del frontend | 63400 (separado) |
| **Procesamiento** | Síncrono C# | Asíncrono Python (threads) |
| **Estrategias** | Hardcoded en C# | Pattern Strategy (Python) |
| **Logs** | .NET logs | Application Insights Azure |

---

## QXTEL (3 archivos)

**NUEVO:** `POST /api/vendorRates/fileObrComparisonQxtel`

---

## VENDORS AFECTADOS

**NUEVO flujo usa:**
- Belgacom Platinum
- Sunrise
- Qxtel Limited
- Orange France Platinum
- Orange France Win
- Ibasis Global Inc Premium
- HGC Premium
- Oteglobe
- Deutsche Telecom
- Arelion
- Orange Telecom
- Apelby
- Phonetic Limited
