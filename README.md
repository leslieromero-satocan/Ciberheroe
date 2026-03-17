# Resumen de la integración con Knowbe4

## Resumen
En general, el script se encarga de obtener los datos de Knowbe4 a través de las APIs, REST y GraphQL API. Procesa los datos para que se pueda trabajar con ellos y se los pasa a distintas funciones auxiliares que realizan la lógica necesaria para calcular las métricas que se han establecido. Los datos calculados se utilizan para obtener las puntuaciones los usuarios. Una vez recolectada toda esta información, se introduce por partes en la base de datos.

## Implementación
El script tiene varios módulos que realizan la gran mayoría de los cálculos: 
- `main.py`: lógica principal, se encarga de las solicitudes a las APIs de Knowbe4, el procesamiento de esos datos y de llamar a las funciones de otros módulos pasándoles los datos obtenidos.
- `basic_metrics.py`: métricas generales de la organización y métricas de usuarios (mensual, ventana activa, anual)
- `admin_metrics.py`: métricas exclusivas para los administradores como usuarios vulnerables, detecciones de contraseñas, etc.
- `scores.py`: cálculo de puntuaciones por usuario (logros completados)
- `db.py`: operaciones de la base de datos: inserción, actualización y lectura de datos.
- `helper_functions.py`: funciones auxiliares para depuración del código y verificación de datos

Asimismo, también existen archivos que no contienen funciones, sino que están dedicados al `type hinting` de Python para hacer el código más robusto y excepciones:
- `custom_types.py`: uso de clases heredadas de TypedDict para el esquema de los datos (type hinting)
- `exceptions.py`: excepciones personalizadas para casos específicos.

A continuación, voy a listar los puntos destacables de cada archivo para referencia en el futuro.
### main.py

En este archivo se encuentran las variables globales con respecto a las APIs. Toda la información importante como las API Keys se pasan a través del archivo `.env`, por lo que si hay que cambiar la API Key o modificar cualquier cosa, se haría en el archivo `.env`.

```python
load_dotenv()

REPORT_API_URL = "https://eu.api.knowbe4.com/v1"
REPORT_API_TOKEN = os.environ.get("REPORT_API_TOKEN")
REPORT_API_HEADERS = {
    "Authorization": f"Bearer {REPORT_API_TOKEN}",
    "Content-Type": "application/json",
    "User-Agent": "My-KnowBe4-Integration-Script",
}
GRAPH_API_URL = "https://eu.knowbe4.com/graphql"
GRAPH_API_PASS = os.environ.get("PASS_API_TOKEN")
GRAPH_API_KSAT = os.environ.get("KSAT_API_TOKEN")
PASSWORDIQ_HEADERS = {
    "Authorization": f"Bearer {GRAPH_API_PASS}",
    "Content-Type": "application/json",
    "User-Agent": "My-KnowBe4-Integration-Script",
}
KSAT_HEADERS = {
    "Authorization": f"Bearer {GRAPH_API_KSAT}",
    "Content-Type": "application/json",
    "User-Agent": "My-KnowBe4-Integration-Script",
}

SUPABASE_URL = os.environ.get("SUPABASE_PROJECT_URL", "SUPABASE_PROJECT_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "SUPABASE_SERVICE_KEY")
```
También existen otras variables como `HISTORICAL_DATA` que se pueden activar. Sin embargo, esta es para usar los datos de las puntuaciones de riesgo de Knowbe4 de diciembre de 2024 en el caso de que no tuviesemos datos posteriores a esa fecha que sirvan para calcular puntuacionies, algo que no debería ocurrir ya que se mantiene registro de las puntuaciones desde noviembre de 2025.

En este archivo también está la declaración del logger. Con la implementación actual se mantienen 3 archivos de logger como máximo, 1 será el activo y 2 de "backup", con un límite de 285MB por archivo, está calculado para que entre los tres se puedan mantener logs de las ejecuciones diarias durante 6 meses. Los logs se borran y crean solos en la misma ruta en la que se encuentra el script.

```python
logger = logging.getLogger("kb4_integration")
logger.setLevel(logging.INFO)

MAX_BYTES = 285 * 1024
BACKUP_COUNT = 2

if not logger.handlers:
    file_handler = RotatingFileHandler(
        "knowbe4_integration.log", maxBytes=MAX_BYTES, backupCount=BACKUP_COUNT
    )
    formatter = logging.Formatter(
        fmt="%(asctime)s - %(levelname)s - %(name)s: line %(lineno)d - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
```

Con respecto al resto de funciones, las más destacadas son las funciones genéricas para extraer datos de la API REST (`request_rest_api()`) y de la Graph API (`request_graphql_api()`) que están documentadas por si tuviesen que usarse para añadir más funcionalidades.

Específicamente para la Graph API, se necesita consultar la documentación de Knowbe4 para poder saber como se realizarían las `queries`. Podrían tomar alguna de las mías como ejemplo. Que, hablando de queries, en vez de crearlas como literales, he creado funciones que me permiten pasarle argumentos, para poder lidiar con paginación y evitar pedir demasiados datos a la API, lo que cause Timeouts. Todas las funciones que empiezan por `get_query` son para estos propósitos.

Luego, las funciones `fetch` se encargan de llamar a las funciones `request` mencionadas anteriormente, para realizar las diversas consultas a las APIs.

Una vez en la función `main()`, en su gran mayoría se trata de llamadas a otras funciones, ya sean del módulo actual o de otros módulos, pero si hay ciertos aspectos que destacar como la sección que se encarga de obtener la puntuación de riesgo del mes anterior o la que se encarga de obtener los ciberpuntos de meses anteriores para poder acumularlos correctamente, teniendo en cuenta los registros activos:
```py
# Obtenemos el riesgo del mes anterior
now = datetime.now(pytz.utc).replace(
    day=1, hour=0, minute=0, second=0, microsecond=0
)
ref_date = now - relativedelta(months=1)
if ref_date < pytz.utc.localize(datetime(2025, 11, 1)):
    ref_date = pytz.utc.localize(datetime(2024, 12, 1))
db_last_risk = db.read_db_data(
    db_client,
    "kb4_monthly_risk",
    "user_id, risk_score",
    "created_at",
    ref_date.isoformat(),
)

# (...)

# Leemos las puntuaciones de los últimos meses para sumar a las de este mes
# La función ya filtra si son registros activos o no
db_last_months_scores = db.read_last_months_scores(
    db_client, active_window
)

db_score_data = {user["id"]: 0 for user in users}
if db_last_months_scores != list():
    # save_json({"scores": db_last_months_scores}, "last_months_scores")
    db_score_data = {
        score["user_id"]: score["total_score"]
        for score in db_last_months_scores
    }
```
Por último solo queda el cálculo de puntuaciones y el guardado en la BD que no tienen ninguna peculiaridad.

### basic_metrics.py

Este archivo está conformado puramente por funciones que realizan cálculos de métricas, dichos cálculos han sido comprobados y corregidos en múltiples ocasiones por lo que no deberían tener que modificarse. La única peculiaridad de este módulo es la función auxiliar `filter_by_year()`, esta función se encarga de filtrar los registros que se le pasan por parámetro a razón de los últimos 12 meses, es una variante de la función `filter_by_date()` que se encuentra en el módulo `scores,py`, ambas están documentadas de manera extensa para evitar confusiones:

```python
def filter_by_year(items: filterByDateInput, property_name: str, by_year: datetime):
    """Filtra las formaciones asignadas por año (copia de filter_by_date, exclusiva por 12 meses)

    Parameters:
        items: la lista de elementos que queramos filtrar por fecha
        property_name: la propiedad que contiene la fecha formateada en ISO8601
        by_year: la fecha desde la que se quieren calcular los 12 meses anteriores

    Return:
        La lista de elementos pasada por parámetro filtrada por los últimos 12 meses

    """
    if by_year.tzinfo is None or by_year.tzinfo.utcoffset(by_year) is None:
        end_date = by_year.replace(tzinfo=pytz.utc)
    else:
        end_date = by_year.astimezone(pytz.utc)

    def check_match(e):
        if e[property_name] is not None:
            date = isoparse(e[property_name])
        else:
            return False
        if date.tzinfo is None or date.tzinfo.utcoffset(date) is None:
            date = date.replace(tzinfo=pytz.utc)
        start_date = end_date - relativedelta(months=12)
        return start_date <= date <= end_date

    return list(filter(check_match, items))
```

### admin_metrics.py

Este archivo se encarga de filtrar la información obtenida de la API que se va a mostrar exclusivamente en el panel admin; usuarios vulnerables, detección de contraseñas, resultados de los tests de seguridad... Más que una lógica compleja, las funciones en este módulo se centran simplemente en filtrado y formateado para preparar los datos para la BD.

### scores.py

En este archivo encontramos la versión original y más versátil de `filter_by_year()` que es `filter_by_date()` esta te permite filtrar ya sea por número de meses concreto (`active_window`) o por mes individual; tiene más parámetros pero está igualmente documentada de manera extensa:

```python
def filter_by_date(
    items: filterByDateInput,
    property_name: str,
    active_window: int,
    by_active_window: datetime,
    by_month: tuple[int, int] | None = None,
):
    """Filtra las formaciones asignadas por fecha

    Parameters:
        items: la lista de elementos que queramos filtrar por fecha
        property_name: la propiedad que contiene la fecha formateada en ISO8601
        active_window: el número de meses que se quiere tener en cuenta
        by_active_window: la fecha desde la que se quieren calcular los meses anteriores de la ventana activa
        by_month: tupla con el número del mes y el año para filtrar por mes
    
    Return:
        La lista de elementos pasada por parámetro filtrada por fecha

    """
    if by_active_window.tzinfo is None or by_active_window.tzinfo.utcoffset(by_active_window) is None:
        end_date = by_active_window.replace(tzinfo=pytz.utc)
    else:
        end_date = by_active_window.astimezone(pytz.utc)

    def check_match(e):
        if e[property_name] is not None:
            date = isoparse(e[property_name])
        else:
            return False
        if date.tzinfo is None or date.tzinfo.utcoffset(date) is None:
            date = date.replace(tzinfo=pytz.utc)
        if by_month is not None:
            return date.month == by_month[0] and date.year == by_month[1]
        else:
            start_date = end_date - relativedelta(months=active_window)
            return start_date <= date <= end_date

    return list(filter(check_match, items))
```

Más allá de esto, la función principal es la que se dedica al cálculo de las puntuaciones y existen otras funciones auxiliares poco relevantes.

### db.py

En este archivo se realizan todas las operaciones con la base de datos, existen dos tipos principales: `read` y `fill_db`, todas aquellas funciones `read`, incluída la genérica `read_db_data()' se encargan de obtener información necesaria para los cálculos, como las puntuaciones de cada logro, que se establecen en la BD, la ventana activa o los historiales de puntuaciones para sumarlas a las calcualdas.

### custom_types.py

En este archivo se encuentran exclusivamente las declaraciones de los diccionarios (`TypedDict`) que declaran la estructura de la información con la que se trabaja en el script, ya sea al extraer información de la API, escribirla en la Base de Datos con la estructura adecuada a las tablas o simplemente para uso interno y mayor comodidad. Puede haber cierta confusión con los nombres, por la similitud entre algunas queries de GraphQL e incluso la repetición de los parámetros entre distintas queries, por lo que el archivo está comentado de la manera más clara posible.  

### helper_functions.py

En este archivo se encuentran funciones auxiliares que ayudan al correcto funcionamiento del código principal (`enum_serializer()`, conversión de string a enum para los `Achievement`) o asisten en la depuración el código (`save_json()`).

### Otros archivos

Con respecto a `exceptions.py` y cualquier otro archivo que no se haya mencionado anteriormente, no hay nada que destacar.

### Depuración de datos con funciones auxiliares

#### save_json()

Como se puede ver en el código, y especialmente en el main, existen algunas líneas que empiezan por `save_json()`. Estas llamadas son exclusivamente para la depuración de datos y están colocadas en puntos estratégicos en los que se extraen datos o, en algunas ocasiones, se van a introducir datos, y se quiere comprobar qué datos se están procesando. La función `save_json()`se encarga de leer los datos pasados por parámetro y exportarlos a un JSON (**IMPORTANTE**: recomiendo que se lean los archivos resultantes utilizando VS Code o un editor similar que contenga un formateador, para poder visualizarlos de manera cómoda, en VS Code Shift+Alt+F es el comando para formatear los archivos si existe un formateador compatible, si no se formatea el archivo, se verá todo en una sola línea, lo que lo hace muy complicado de visualizar).

Los archivos más relevantes que se pueden generar:

`save_json(dict(campaign_runs), "campaigns")`: genera el archivo `campaigns.json` que contiene la información directamente sacada de la Graph API con los campos especificados en la query (`get_query_pst()`). Este archivo se puede utilizar para buscar detalles de cada prueba de phishing que se ha enviado, incluye al usuario al que se le ha enviado y métricas de clicks, denuncias, cuándo lo ha abierto, etc.

`save_json(dict(user_info), "user_info")`: genera el archivo `user_info.json` que contiene la información relativa a los usuarios, también extraída directamente de la API. Los campos están en la query `get_query_user()` y cubren el ID del usuario, nombre y apellidos, sus formaciones obligatorias, su puntuación de riesgo actual, etc. Anteriormente se podían extraer los historiales hasta diciembre de 2024, pero ahora la función está obsoleta después de que estuve hablando con soporte.

`save_json({"scores": db_last_months_scores}, "last_months_scores")`: genera el archivo `last_months_scores.json` que contiene las puntuaciones que se extraen de la tabla de la BD "kb4_user_score_history", dichas puntuaciones son la suma de todas aquellas pertenecientes a la ventana activa y que se encuentren con estado "active". Estas puntuaciones son las que se pasan al cálculo de puntuaciones que se realiza en `scores.py` y se suman a las calculadas para posteriormente sumarles el bonus de riesgo. Si existiese alguna discrepancia con las puntuaciones o se quiere revisar sin tener que recurrir ar leer directamente la BD, este archivo es un buen sitio donde consultar.

Aunque aquí dejo los más relevantes, otros archivos se pueden generar sin problemas y se puede llamar a la función `save_json()` en cualquier momento siempre y cuando se usen los parámetros adecuados.

#### Logger
Aparte de la función `save_json()` se pueden comprobar los datos obtenidos cambiando el nivel del logger de `INFO` (como está por defecto) a `DEBUG`, la configuración del logger se encuentra en la parte superior del módulo `main.py` (línea 70), tras la declaración de las variables globales:
```python
# ========================== LOGGING ==========================

logger = logging.getLogger("kb4_integration")
logger.setLevel(logging.INFO)   # Nivel INFO
```
Si se cambia a `DEBUG`:
```py
logger.setLevel(logging.INFO)   # Nivel INFO
```
De esta manera, se pueden utilizar las sentencias ya introducidas por mi para poder visualizar con qué datos se está trabajando. Por supuesto, en cualquier momento se pueden añadir más líenas de depuración, solo basta con cambiar luego el nivel del logger nuevamente y se evita que aparezca en los logs normales.

**Línea de código de depuración (basic_metrics.py, linea 315)**
```py
logger.debug(f"{len(month_reporting_users)}/{n_users} usuarios han denunciado phishing este mes")
```
**Resultado en el archivo resultante (knowbe4_integration.log)**
```log
2026-01-21 09:19:11 - DEBUG - kb4_integration.basic_metrics: line 315 - 218/362 usuarios han denunciado phishing este mes
```

### Consideraciones para futuras modificaciones
Para el correcto funcionamiento de todo el código, recordar que en su gran mayoría, el código utiliza `type hinting` lo que mejora la depuración y lo hace más robusto, sin embargo, también implica que requiere más cuidado en caso de algún cambio. Es decir, si se cambia o añade cualquier cosa desde el frontend (página web) que tenga que ver con la base de datos o alguna de sus tablas, hay que recordar que es muy posible que se tengan que realizar cambios en el archivo `db.py` y consecuentemente también en el `custom_types.py` para que el formato de inserción en la base de datos coincida exactamente y no de errores. A su vez, si se añaden argumentos o se necesitan nuevos campos en variables que utilizan un esquema perteneciente a `custom_types.py` hay que recordar realizar el cambio donde convenga. Sin embargo, precisamente al usar `type hinting` y todo lo que conlleva, el IDE (ej. VS Code) suele entender perfectamente el error e incluso realizar sugerencias que evitan errores en el futuro.

Si se crea alguna función nueva, se recomienda mantener la práctica del `type hinting` para mantener la robustez del código y evitar conflictos o la introducción de errores posteriormente

## Base de datos
### Tablas
Con respecto a la base de datos, exissten varias tablas:
- `kb4_achievement_info`: guarda la información relativa a los logros que se pueden obtener para sumar ciberpuntos, contiene un título, descripción detallada, cuántos puntos se otorgan por cada logro, etc. De manera excepcional, también contiene la información de los umbrales temporales que se tienen en cuenta para sumar los puntos como el mínimo de correos enviados al mes, al año y en la ventana activa, el periodo en meses de ventana activa, etc.
- `kb4_assessment_results`: contiene los resultados del cuestionario de seguridad con un par de filas por test.
- `kb4_best_templates`: almacena las consideradas "10 mejores plantillas de phishing" por su porcentaje de clicks.
- `kb4_metrics`: contiene las métricas generales que se muestran en el panel principal: porcentajes de usuarios que han realizado formación, porcentaje de usuarios que han denunciado phishing, porcentaje phish-prone, etc.
- `kb4_monthly_risk`: se utiliza a nivel de historial para guardar las puntuaciones de riesgo (knowbe4) mensuales de cada usuario ya que extraer dichos datos por la API es muy costoso e innecesario.
- `kb4_pwd`: contiene la cantidad de detecciones de contraseñas vulnerables por tipo.
- `kb4_pwd_detections`: contiene cada una de las detecciones junto con los tipos, fecha en la que se dió la detección, el usuario asociado, etc.
- `kb4_rank_info`: contiene la información necesaria para el cálculo de los rangos de cada usuario (umbrales máximo y mínimo).
- `kb4_user_score_history`: mantiene el historial de puntuaciones de los usuarios incluyendo la puntuación acumulada, la puntuación obtenida en el mes, el riesgo con el que se calculó el bonus y otra información relevante como el estado de los registros, ya sean activos o archivados. En cualquier momento, cambiar el estado de los registros de archivado a activo hace que se lo tenga en cuenta para la suma acumulativa de ciberpuntos.
- `kb4_user_scores`: contiene las puntuaciones (ciberpuntos) actuales de todos los usuarios junto con sus logros.
- `kb4_users`: contiene la información de todos los usuarios, incluyendo sus métricas calculadas (clicks, denuncias, correos abiertos, formaciones realizadas).
- `kb4_vulnerable_users`: todos los usuarios considerados vulnerables, sin restricciones.
- `profiles`: necesaria para el funcionamiento correcto de la autenticación con Google y el acceso a los datos de la BD, almacena los perfiles de cada persona que inicia sesión en la página web.
- `user_roles`: asocia los perfiles de la tabla `profiles` con un rol: admin o user, que se utliza para decidir el acceso a los datos, y consecuentemente, al panel admin de la página web.

Todas aquellas tablas que contengan el prefijo `kb4` han sido creadas manualmente y adaptadas a la información extraída y calculada a partir de las APIs de Knowbe4. Casos especiales incluyen `kb4_rank_info` que se encarga de guardar los umbrales de los rangos -es relevante para la página web pero no es un dato calculado u obtenido de las APIs- y `kb4_achievement_info` que sí tiene relación con la información extraída, pero se centra en aportar información explicativa con respecto a los logros que se pueden obtener y ciertos umbrales relevantes para dichos logros. Ambas son tablas auxiliares más que de almacenamiento de datos real.

Otro aspecto relevante es la periodicidad de los datos obtenidos y guardados en cada tabla. En su mayoría, las tablas guardan información mensual, lo que quiere decir que los registros contienen un campo de fecha y una restricción para que solo se puedan guardar regsitros una vez al mes. Esto implica que cada vez que se recalculan los valores en un mismo mes, los datos se sobre-escriben. Esta metodología aplica a:
- `kb4_metrics`: un solo registro por mes. Cada registro contiene las métricas generales de la organización.
- `kb4_monthly_risk`: un registro por usuario por mes, es decir, cada mes se guardan X registros si hay X usuarios activos. Cada registro guarda el riesgo para cada mes de un usuario concreto.
- `kb4_pwd`: un solo registro por mes. Cada registro contiene la cuenta de detecciones de contraseñas vulnerables por tipo.
- `kb4_user_score_history`: un registro por usuario por mes. Guarda los datos relevantes para al cálculo de puntuaciones.

Aquellas tablas que siguen otro sistema son:
- `kb4_achievement_info`: existe un registro por cada valor del enumerado 'kb4_achievement' que en su gran mayoría cubre los logros, pero también se utiliza para guardar valores de umbrales temporales (min. mensual, anual, ventana activa...)
- `kb4_assessment_results`: contiene un par de registros por cada test de seguridad del que se quiera ver los resultados.
- `kb4_pwd_detections`: contiene un registro por cada combinación única de 'user_id', 'fecha en la que se dio el evento, 
- `kb4_rank_info`: se trata de una tabla con un número fijo de registros, uno por cada rango (Bronce, Plata, Oro, Platino) + tier (I, II, III)
- `kb4_user_scores`: guarda la puntuación actual acumulada de cada usuario, por lo que el número de registros será muy similar al número de usuarios activos (no idéntico ya que algunos de los usuarios archivados pueden seguir estando presentes, etc)
- `kb4_users`: contiene toda la información de los usuarios, el núnmero de registros es idéntico al rúmero real de usuarios activos ya que se mantiene un control de estado (active, archived) y una eliminación periódica de los usuarios archivados.
- `kb4_vulnerable_users`: de las tablas menos limitadas, muestra todos los usuarios que hayan cumplido las condiciones para considerarse vulnerables, la única restricción es por ID de usuario. Con cada nuevo cálculo, la tabla se borra y se re-escribe para no mantener a usuarios que hayan dejado de considerarse vulnerables.

### Cron jobs
Actualmente, están implementados tres 'cron jobs' o funciones que se ejecutan periódicamente. Estas se dedican exclusivamente a limpiar la base de datos de registros innecesarios como historiales muy antiguos o usuarios inactivos.
- `borrado--historial-ciberpuntos-antiguos`: se encarga de borrar aquellos registros en la tabla `kb4_user_score_history` cuya fecha sea anterior a los últimos 13 meses. Se ejecuta cada domingo a las 3:00.
- `borrado-usuarios-archivados`: ejecuta la función RPC `clean_stale_users()` que se encarga de borrar al usuario si este está archivado y su información no se ha actualizado en 100 días (significa que no ha estado incluído en la base de datos de Knowbe4 por más de 3 meses), además, borra al usuario de la tabla `profiles`, tabla donde se guarda a los usuarios que inician sesión y se autentican correctamente. Se ejecuta cada día a las 3:00.
- `borrado-puntuaciones-antiguas`: se encarga de borrar aquellos registros en la tabla `kb4_monthly_risk` cuya fecha sea anterior a los últimos 13 meses. También se ejecuta cada domingo a las 3:00.

### Otra información relevante
Con respecto a la base de datos, simplemente recordar que la lectura de las tablas está limitada por RLS (Row Level Security) y políticas de acceso, especialmente para la información exclusiva para admins. Esto significa también que al crear nuevas tablas y activarse RLS (se debería activar automáticamente), si no se crean políticas de acceso la información no se podrá visualizar correctamente. Todo esto de cara a posibles añadidos a la página web desde Lovable.

## Lovable
### Estructura de la página web
La página web está dividida en tres secciones diferenciadas: panel principal, panel admin y sección personal. 

En el panel principal se encuentra toda la información general de la organización y de usuarios junto con el ranking. El ranking muestra al top 10 de usuarios con más ciberpuntos, que son los puntos calculados en `scores.py` a partir de los logros que vayan completando y la puntuación de riesgo. La información presente en todos los elementos del ranking es una combinación entre información directa de la base de datos y cálculos realizados en la propia página web. Cualquier cambio en el panel principal probablemente implica a alguna de las siguientes tablas: `kb4_metrics`, `kb4_users`, `kb4_user_scores`, `kb4_user_score_history`, `kb4_achievement_info` o `kb4_rank_info`. 

En el panel admin se encuentra la información exclusiva a los usuarios considerados como administradores (admin) en la tabla `roles` de la base de datos. Para añadir admins existe una sección al final del panel admin, sin embargo, para eliminar admins o simplemente modificar el rol de cualquier usuario de manera manual, se puede cambiar su rol directamente en la tabla `roles` de la base de dato, buscando de qué usuario se trata en el campo de referencia al usuario `user_id`. En el panel admin se encuentran todos los datos que tratan vulnerabilidades, ya sea de usuarios o contraseñas, información adicional que no ha sido necesaria poner en el panel principal y todas las configuraciones de la página web (puntuaciones de los logros, configuración de umbrales, información de rangos, reseteo de puntuaciones, etc.). Cualquier cambio en el panel de admin probablemente implica a alguna de las siguientes las tablas: `kb4_assessment_results`, `kb4_users`, `kb4_best_templates`, `kb4_pwd_detections`, `kb4_vulnerable_users`, `kb4_achievement_info` o `kb4_rank_info`.

Finalmente, en la sección personal se encuentra la información exclusiva de cada usuario, si el usuario no se encuentra en el top 10, su información de ciberpuntos, logros, etc. es completamente privada. En este panel se muestran todas las métricas posibles acerca del usuario: rango, posición en el ranking principal, ciberpuntos, puntuación de riesgo, formaciones, clicks en phishing, etc. Cualquier cambio en la sección personal probablemente implica a alguna de las sisguientes tablas: `kb4_users`, `kb4_user_scores`. `kb4_user_score_history`, `kb4_achievement_info` o `kb4_rank_info`.

Como recordatorio, muchas de las tablas tienen `foreign keys` entre ellas, especialmente en referencia a la tabla `kb4_users`, por lo que en caso de cualquier modificación, hay que ser consciente de las conexiones entre ellas, lo que puede implicar modificaciones a múltiples tablas en ocasiones. Para más información, se puede consultar el diagrama de tablas en la base de datos.

### Extracción de datos de Supabase
Con respecto a la lectura y procesado de datos desde la página web utilizando Supabase, la integración nativa de Lovable se encarga de realizar las operaciones sin problemas, sin embargo, es bueno saber que si se realizan cambios manuales en el código de la página web, hay que tener cuidado con modificar solo las `queries` a la BD sin cambiar la declaración de las tablas en el archivo correspondiente (`/src/integrations/supabase/types.tsx`)
