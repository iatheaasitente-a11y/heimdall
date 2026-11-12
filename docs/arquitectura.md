# Arquitectura

## Capas (de fuera hacia dentro)

    Chatbot (interfaz, herramientas)
      -> Router / fábrica de agentes
        -> Agentes (personal, NBA)
          -> Servicios (lógica de aplicación)
            -> Repositorios -> SQLite
          -> Fuente NBA (interfaz inyectada)

    Dominio (app/domain) y Esquemas (app/schemas) los usan todas las capas.

Hoy existen el dominio, los esquemas, la base de datos SQLite, los repositorios
SQLite y los seis servicios: usuarios, agenda, recordatorios, hábitos, objetivos
y conversaciones.

## Reglas
1. `app/domain` es puro: sin SQL, sin FastAPI, sin librerías de IA, sin I/O.
2. Los datos externos entran por esquemas Pydantic antes de crear objetos de dominio.
3. El modelo de lenguaje nunca accede a la base de datos; solo llama a
   herramientas que usan servicios.
4. Los agentes no contienen lógica de negocio: delegan en servicios.
5. Fechas siempre con zona horaria; se guardan en UTC.
6. La interpretación de expresiones naturales de fecha recibe el instante de
   referencia con zona; no consulta relojes ni zonas globales.

## Ejemplo: "¿qué tengo hoy?"
1. El agente detecta la intención y llama a una herramienta.
2. La herramienta pide al servicio los eventos, hábitos y recordatorios del usuario.
3. `resumen_del_dia` calcula el resultado en Python, sin modelo de lenguaje.
4. El modelo, si se usa, solo redacta la respuesta con ese resultado.

## Fronteras de importación
Las vigila `tests/test_importaciones.py`, que analiza los `import` con `ast`
sin ejecutar código. Cada fallo indica archivo y línea.

| Capa | Puede importar | Bibliotecas externas |
|---|---|---|
| `domain` | `domain` | No |
| `schemas` | `domain`, `schemas` | Sí |
| `database` | `database` | No |
| `repositories` | `domain`, `database`, `repositories` | No |
| `services` | `domain`, `schemas`, `repositories.interfaces`, `services` | No |
| `tools` | `domain`, `schemas`, `services`, `tools` | Sí |
| `llm` | solo `llm` | No |
| `agents` | `domain.message`, `domain.lenguaje_fechas`, `llm`, `tools`, `agents` | Sí |
| `chatbot` | `composicion`, `database`, `domain.message`, `llm.configuracion`, `llm.ollama` | No |

- `sqlite3` solo se usa en `database` y `repositories`.
- Las implementaciones `sqlite_*` solo las importa `app/composicion.py`,
  que es el único archivo exento.
- `app/chatbot.py` es el punto de entrada de terminal y tiene sus dependencias
  explícitas en `REGLAS` de `tests/test_importaciones.py`.
- Para permitir una dependencia nueva hay que ampliar `REGLAS` en el test y dejarlo escrito aquí.

## Herramientas

Cada herramienta declara argumentos en un modelo Pydantic del que obtiene su
esquema JSON. El `usuario_id` se pasa por separado desde el sistema y nunca
forma parte de los argumentos del modelo. Las herramientas delegan en servicios
y convierten sus resultados a JSON; los textos se limitan a 500 caracteres y
los valores numéricos rechazan NaN e infinito. Los `ErrorDeServicio` se devuelven
como errores estructurados. Las operaciones internas de recordatorios no se exponen.
Los selectores de hábito, objetivo, evento y recordatorio aceptan UUID o nombre
exacto sin distinguir mayúsculas ni tildes; la búsqueda se limita al usuario.
Una selección ausente o ambigua devuelve candidatos, y hay herramientas para
listar hábitos y recordatorios.

La capa `app/llm` devuelve únicamente intención, campos y confianza. El catálogo
inyectado asigna modelos explícitos a TEXTO, ENRUTADOR, VISION, OCR y VOZ; sin
configuración, cada rol queda apagado. Las variables son
`HEIMDALL_MODELO_TEXTO`, `HEIMDALL_MODELO_ENRUTADOR`,
`HEIMDALL_MODELO_VISION`, `HEIMDALL_MODELO_OCR` y `HEIMDALL_MODELO_VOZ`.
Ollama usa `urllib`, timeouts por rol y ningún reintento; el motor nube sigue
siendo un esqueleto sin credenciales ni red y no hay fallback silencioso.

El planificador usa un lock compartido dentro del proceso. Antes de cambiar de
modelo solicita su descarga (`keep_alive: 0`) y verifica `/api/ps`; si no
confirma la descarga o que solo el modelo solicitado quedó cargado, falla
cerrado. Los plazos monotónicos por rol y el umbral mínimo de confianza (0,70)
están en [`plan-llm.md`](./plan-llm.md). El lock no coordina otros procesos ni
otros clientes de Ollama, así que no garantiza exclusión frente a ellos.
Los nombres de modelo sin etiqueta se normalizan a `:latest` tanto al guardar
el catálogo como al comparar la salida de `/api/ps`.
Los frenos limitan consultas por conversación y tratan la confianza ausente,
ilegible o fuera de rango como baja. Antes de ejecutar, el agente comprueba que
la herramienta y sus argumentos pertenecen al catálogo; al motor solo pasa los
últimos cuatro turnos y, si hay una aclaración pendiente, la pregunta bajo
`esperando`.

Los motores de VISION y OCR aceptan rutas locales a imágenes JPEG o PNG.
`app/llm/vision.py` aplica los límites de tamaño y dimensiones aprobados,
rechaza enlaces simbólicos y comprueba el tamaño antes de leer. El planificador
pasa los bytes ya validados al motor y evita releer el archivo. Ollama solo
admite endpoints HTTP(S) locales. La imagen se envía como entrada multimodal.
El contrato de salida sigue siendo intención, campos y confianza; los tests
usan motores falsos y no requieren Ollama.

La entrada de voz valida WAV PCM sin comprimir mediante `wave`, con límites
de tamaño y duración. Incluye un transcriptor falso; `MotorOllamaVoz` permanece
como esqueleto y no realiza llamadas de red. El planificador rechaza el rol
VOZ hasta que haya una implementación operativa.

`AgentePersonal` evalúa primero patrones deterministas y delega en herramientas.
Las reglas interpretan fechas con `app/domain/lenguaje_fechas.py`; si faltan
datos, la hora es ambigua o hay varios nombres candidatos, piden aclaración.
Solo si no hay una regla aplicable y se configura un motor consulta el LLM; el
agente no contiene lógica de negocio.

`app/domain/lenguaje_fechas.py` interpreta expresiones de fecha y hora con la
zona del `datetime` inyectado. No depende de Pydantic ni de otras librerías.

El módulo NBA solo define el contrato `FuenteNBA` y una implementación falsa
para pruebas. La herramienta se registra únicamente cuando la composición
recibe una fuente; no hay conexiones a servicios externos ni API real.
