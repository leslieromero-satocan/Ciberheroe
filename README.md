## Título y Descripción
**Nombre del Proyecto**: Ciberhéroe
<br/>
**Título del Trabajo**: Plataforma de análisis y visualización de métricas de ciberseguridad basadas en el comportamiento del usuario en entornos corporativos
<br/>
**Descripción**: Pipeline ETL que extrae métricas de las distintas APIs de Google Workspace y registros de eventos de Windows para calcular puntuaciones de seguridad de los usuarios.
<br/>
**Contexto:** Trabajo de Fin de Título para el Grado en Ingeniería Informática

## Arquitectura del sistema
### Fuentes de datos
Se extraen datos de las APIs de Google: **Admin SDK** para métricas visibles solo para administradores (contraseñas vulnerables o reutilizadas, visitas a páginas no seguras, descargas de malware o archivos peligrosos, uso de dispositivos no corporativos junto con las plataformas utilizadas, etc.), **Drive** para métricas relacionadas con los archivos guardados en el almacenamiento de Google Drive (archivos compartidos con enlace público, archivos compartidos por un tiempo limitado con fecha de caducidad), **Gmail** para métricas relacionadas con los mensajes enviados a través de la plataforma de correo de Gmail (correos enviados en modo confidencial). También se extraen datos de la auditoría nativa de eventos de Windows a través de un mecanismo centralizado organizado por la empresa, los eventos relevantes extraídos son los siguientes: 
- **4626 - Inicio de sesión exitoso**
- **4625 - Inicio de sesión fallido**
- **4800/4802 - Bloqueo manual del dispositivo**
- **1074 - Reinicio**
- **19 - Descarga de actualizaciones del sistema**
- **4663/20001/20003 - Dispositivos USB**

> [!NOTE]
> El módulo de extracción de eventos no ha sido probado con datos reales, se ha implementado completamente con datos sintéticos lo más cercano a los datos reales posible, para confirmar su correcto funcionamiento habría que realizar pruebas adicionales.

### Procesamiento (ETL)
Se realiza la extracción a través de llamadas a las distintas APIs en el caso del módulo de Google, utilizando subprocesos múltiples (*multithreading*) para mayor eficiencia y reducido tiempo de ejecución. En el caso del módulos de eventos, se lee el archivo JSON resultante de la lectura de los eventos de todos los dispositivos corporativos registrados, la ejecución y subsecuente generación de este archivo es ajena a este proyecto.

Los datos obtenidos en ambos módulos se procesan a través de funciones que acumulan las métricas del mes en curso ya existentes en la base de datos y las suman con las nuevas métricas calculadas a partir de los nuevos datos utilizando un patrón de carga delta. Tras la obtención de las métricas resultantes se calculan puntuaciones para cada uno de los usuarios.

Finalmente, se guardan las métricas y puntuaciones obtenidas en la base de datos de **Supabase**. Las métricas seleccionadas son las siguientes:

*Métricas de Google*

| Métrica | Definición |
| --- | --- |
| **Reutilización de contraseñas** | El usuario no tiene contraseñas reutilizadas en páginas no corporativas. |
| **Mensajes en modo confidencial** | El usuario ha enviado correos (Gmail) en modo confidencial, los puntos se asignan por cada correo enviado en el mes. |
| **Verificación en dos pasos** | El usuario tiene activada la verificación en dos pasos. |
| **Visita a una página no segura** | Se ha detectado un acceso a una página en la que se ha omitido la advertencia de error de certificado. Se otorgan los puntos si el evento no se ha detectado en todo el mes. |
| **Descarga de archivos peligrosos** | El usuario no se ha descargado archivos con extensiones consideradas como peligrosas (.exe, .bat, .cmd, .ps1, .vbs, .scr, .msi, .jar). |
| **Archivos con fecha de caducidad** | El usuario tiene archivos compartidos con fecha de caducidad, los puntos se asignan por cada archivo compartido en el mes hasta un máximo de 10. |
| **Uso de dispositivos no corporativos** | El usuario no ha utilizado dispositivos no corporativos en los últimos 30 días. |
| **Archivos con enlace público** | El usuario no ha compartido archivos con enlace público (abierto a todas las personas con el link). |
| **Contraseñas vulneradas** | El usuario no tiene contraseñas que se han filtrado. |
| **Plataforma de dispositivo** | La plataforma principal del usuario es principalmente Windows, la cual se considera más segura. Se calculará el porcentaje del uso de Windows sobre otras plataformas y se asignará dicho porcentaje de la puntuación al usuario. |
| **Descarga de malware** | El usuario no ha descargado o entrado en contacto con malware de algún tipo en todo el mes. |


*Métricas de eventos*
| Métrica | Definición |
| --- | --- |
| **Reinicio responsable** | El usuario ha reiniciado el dispositivo al menos 4 veces en el último mes. |
| **Bloqueo de pantalla** | El usuario ha bloqueado voluntariamente el dispositivo antes de abandonar su puesto. |
| **Inicio de sesión exitoso** | El usuario ha tenido menos de 10 fallos de inicio de sesión en su dispositivo en el último mes. |
| **Autenticación biométrica con Windows Hello** | El usuario ha utilizado el inicio de sesión con biometría en más de la mitad de sus inicios de sesión en el último mes. |
| **Actualizaciones frecuentes** | El usuario ha instalado las actualizaciones pertinentes en el dispositivo tan pronto como estas han estado disponibles. |
| **Dispositivos USB** | El usuario no ha insertado ningún dispositivo USB desconocido. |


## Requisitos previos
**Entorno**: Python 3.12.12 y `uv` (gestor de paquetes y entornos)
<br/>
**Credenciales**: Cuenta de servicio de Google Cloud (archivo `.json` con los scopes de lectura de Admin, Drive y Gmail habilitados)
<br/>
**Base de Datos**: Proyecto de Supabase configurado
<br/>
## Instalación y Configuración
**Paso 1:** Clonar el repositorio
<br/>
**Paso 2:** Instalar dependencias utilizando `uv sync`
<br/>
**Paso 3:** Configuración de variables de entorno. 
- `REPORT_API_URL`: enlace de la Report API de Knowbe4, disponible en su documentación oficial (https://developer.knowbe4.com/rest/reporting#tag/Base-URL) 
- `GRAPH_API_URL`: enlace de la Graph API de Knowbe4, disponible en su documentación oficial (https://developer.knowbe4.com/graphql/ksat/page/Base-URL)
- `REPORT_API_TOKEN`: token para la Report API de Knowbe4, solo disponible para el administrador de una cuenta de Knowbe4 en el Panel de Control (https://developer.knowbe4.com/rest/reporting#tag/Authentication).
- `PASS_API_TOKEN`: token para la Graph API de PasswordIQ, solo disponible para el administrador de una cuenta de Knowbe4 en el Panel de Control (https://developer.knowbe4.com/graphql/passwordiq/page/Authentication).
- `KSAT_API_TOKEN`: token para la Graph API de la consola KSAT, solo disponible para el administrador de una cuenta de Knowbe4 en el Panel de Control (https://developer.knowbe4.com/graphql/ksat/page/Authentication).
- `SUPABASE_PROJECT_URL`: enlace del proyecto de Supabase
- `SUPABASE_SERVICE_KEY`: clave de servicio del proyecto de Supabase
- `SERVICE_ACCOUNT_FILE_PATH`: enlace al archivo de JSON de la cuenta de servicio de Google para realizar la suplantación de dominio. Los scopes necesarios deben estar habilitados al menos para permitir la lectura.
- `SUBJECT_EMAIL`: correo de un administrador con permisos de lectura para las APIs con restricción de lectura: Admin SDK, Admin Directory, Cloud Identity.
- `PYTHONPATH`: ruta origen para la ejecución de los tests, para el funcionamiento de la orden `uv run pytest -v` se elige el directorio raíz del proyecto (`PYTHONPATH=.`) 
## Estructura del Proyecto
El proyecto está organizado por módulos acorde a las distintas fuentes externas de datos (`src/knowbe4_module`, `src/google_module`, `src/events_module`), asimismo, existe una ruta para la lectura de las variables de entorno y la declaración de excepciones (`src/config`), la declaración de los tipos estáticos (`src/custom_types`) y la declaración de la clase base (`DBClientBase`) para las clases `EventsDBClient`, `GoogleDBClient` y `Knowbe4DBClient`, encargadas de las operaciones con la base de datos de cada módulo.

*Árbol del proyecto (simplificado)*
```
.
├── src/
│   ├── config/
│   │   ├── env_config.py
│   │   └── exceptions.py
│   ├── custom_types/
│   │   ├── events/
│   │   ├── google/
│   │   └── knowbe4/
│   ├── database/
│   │   └── base.py
│   ├── events_module/
│   │   ├── event_codes.json
│   │   ├── etl.py
│   │   ├── events_db.py
│   │   ├── extractor.py
│   │   └── scores.py
│   ├── google_module/
│   │   ├── admin.py
│   │   ├── base.py
│   │   ├── drive.py
│   │   ├── etl.py
│   │   ├── gmail.py
│   │   ├── google_db.py
│   │   └── scores.py
│   ├── knowbe4_module/
│   │   ├── admin_metrics.py
│   │   ├── api.py
│   │   ├── basic_metrics.py
│   │   ├── etl.py
│   │   ├── helper_functions.py
│   │   ├── kb4_db.py
│   │   ├── queries.py
│   │   └── scores.py
│   └── main.py
├── tests/
├── pytest.ini
└── README.md
```

Como se puede apreciar, cada módulo de extracción contiene aproximadamente los mismos archivos:
- `etl.py`: Archivo principal, se encarga de llamar a todas las funciones necesarias, contiene el proceso completo de extracción, procesado de métricas, cálculo de puntuaciones y guardado en la base de datos.
- `scores.py`: Archivo de cálculo de puntuaciones, contiene los cálculos necesarios para asignar las puntuaciones a cada usuario. 
- `*_db.py`: Archivo de base de datos, contiene todas las operaciones que interactúan con la base de datos, lecturas, escrituras, actualizaciones, etc.
- El resto de los archivos presentes en la carpeta de cada módulo se dedica a realizar operaciones necesarias para la extracción de los datos o el cálculo de métricas. La organización de estos archivos depende en gran medida de la fuente de datos en cuestión.
- Excepcionalmente, en el módulo de eventos (`src/events_module`), se encuentra un archivo JSON (`event_codes.json`) que se encarga de la traducción entre los códigos de eventos de Windows y su respectiva etiqueta (las etiquetas son valores pre-definidos en la base de datos para las métricas de los eventos).
  
*event_codes.json*
```json
[
  { "code": 4624, "label": "login_success" },
  { "code": 4800, "label": "lock_screen" },
  { "code": 4802, "label": "lock_screen" },
  { "code": 1074, "label": "restart" },
  { "code": 19, "label": "updates" },
  { "code": 4663, "label": "usb_devices" },
  { "code": 20001, "label": "usb_devices" },
  { "code": 20003, "label": "usb_devices" },
  { "code": 4625, "label": "login_failed" }
]
```

Por último, en el directorio raíz se pueden observar este mismo documento (`README.md`), la carpeta que contiene los tests unitarios (`tests`) y el archivo `pytest.ini`, utilizado para que la ejecución de los tests reconozca las rutas correctamente.  
*pytest.ini*
```ini
[pytest]
pythonpath = . src
```
## Ejecución y Uso
### Ejecución del pipeline principal
Para ejecutar el pipeline completo, solo basta con ejecutar el siguiente comando:
```
uv run src/main.py
```

Para comprobar que la ejecución está en curso, se pueden consultar los logs en la carpeta `logs` que se habrá generado automáticamente dentro de `src`, el código utiliza suficientes entradas de *logs* para poder comprender lo que está ocurriendo en cada momento.

> [!NOTE]
> En los logs pueden aparecer errores durante la ejecución del módulo de Google que advierten de que el servicio no se encuentra activo para un usuario concreto, el sistema está diseñado para ignorar esos errores y continuar la ejecución saltándose a los usuarios que no tienen activado el servicio, todo error crítico contemplado en el código parará la ejecución de inmediato.

Si la ejecución se realiza con éxito, se imprimirá un `OK` en la terminal.

> [!WARNING]
> A pesar de que se utilizan subprocesos (*multithreading*) para realizar las llamadas a las APIs de Google, si los usuarios de la organización son demasiados (+1.000, como es el caso), el tiempo de ejecución puede extenderse hasta 30 minutos o más, esto es normal, si la ejecución tiene una duración excesivamente larga (1 hora o más), se aconseja revisar los logs, si estos se encuentran congelados y no se muestra un error, puede que haya ocurrido un error no contemplado en el código, en ese caso se aconseja interrumpir la ejecución de manera forzada (`Ctrl+C` o cerrar la ventana de la terminal si esta no responde).
### Ejecución de pruebas
Para ejecutar las pruebas se puede ejecutar el siguiente comando:
```
uv run pytest -v
```

Si todas las pruebas se han ejecutado correctamente, se mostrará un mensaje similar a este:
```
tests/test_admin_extractor.py::test_check_ignore_certificate_warning_parses_nested_json PASSED    [  5%]
tests/test_admin_extractor.py::test_check_file_downloads_filters_dangerous_files PASSED           [ 11%]
tests/test_admin_extractor.py::test_check_reuse_password_finds_events PASSED                      [ 16%]
tests/test_admin_extractor.py::test_check_malware_download_finds_events PASSED                    [ 22%]
tests/test_admin_extractor.py::test_check_vulnerable_password_finds_events PASSED                 [ 27%]
tests/test_drive_extractor.py::test_extract_files_with_full_access PASSED                         [ 33%]
tests/test_drive_extractor.py::test_extract_files_with_expiration_date PASSED                     [ 38%]
tests/test_events_calculator.py::test_perfect_user_gets_all_points PASSED                         [ 44%]
tests/test_events_calculator.py::test_risky_user_gets_zero_points PASSED                          [ 50%]
tests/test_events_calculator.py::test_boundary_conditions PASSED                                  [ 55%]
tests/test_events_calculator.py::test_partial_user_mixed_results PASSED                           [ 61%]
tests/test_events_etl.py::test_process_events_by_user_translates_correctly PASSED                 [ 66%]
tests/test_events_etl.py::test_accumulate_event_metrics_calculates_delta_correctly PASSED         [ 72%]
tests/test_gmail_extractor.py::test_extract_messages_confidential PASSED                          [ 77%]
tests/test_google_calculator.py::test_perfect_user_gets_all_points PASSED                         [ 83%]
tests/test_google_calculator.py::test_risky_user_misses_bad_practice_points PASSED                [ 88%]
tests/test_google_calculator.py::test_max_accumulation_cap PASSED                                 [ 94%]
tests/test_google_etl.py::test_get_individual_metrics_calculates_delta_correctly PASSED           [100%]

========================================== 18 passed in 3.48s ==========================================
```
## Trabajo Futuro
Como trabajo futuro, quedaría adaptar la implementación del módulo de extracción de eventos a datos reales extraídos a través de una auditoría centralizada de los eventos de Windows de una red completa de dispositivos corporativos, la implementación actual es completamente funcional para unos datos sintéticos generados a partir de una simulación de los datos reales, tomando como referencia el script de Powershell que se utilizaría para extraerlos.
