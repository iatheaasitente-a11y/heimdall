# Arquitectura

## Capas (de fuera hacia dentro)

    Chatbot (interfaz, herramientas)
      -> Router / fábrica de agentes
        -> Agentes (personal, NBA)
          -> Servicios (lógica de aplicación)
            -> Repositorios -> SQLite

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
| `agents` | `domain.message`, `llm`, `tools`, `agents` | Sí |
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
y convierten sus resultados a JSON; los `ErrorDeServicio` se devuelven como
errores estructurados. Las operaciones internas de recordatorios no se exponen.

La capa `app/llm` devuelve únicamente intención, campos y confianza. Está
apagada por defecto; Ollama usa `urllib` con timeout y sin reintentos, mientras
que el motor nube permanece como esqueleto sin credenciales ni red. Los frenos
limitan consultas por conversación y descartan respuestas de baja confianza.

`AgentePersonal` evalúa primero patrones deterministas y delega en herramientas.
Solo si no hay una regla aplicable y se configura un motor consulta el LLM; el
agente no contiene lógica de negocio.
