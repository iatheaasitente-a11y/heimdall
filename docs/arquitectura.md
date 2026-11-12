# Arquitectura

## Capas (de fuera hacia dentro)

    Chatbot (interfaz, herramientas)
      -> Router / fábrica de agentes
        -> Agentes (personal, NBA)
          -> Servicios (lógica de aplicación)
            -> Repositorios -> SQLite

    Dominio (app/domain) y Esquemas (app/schemas) los usan todas las capas.

Hoy existen el dominio, los esquemas, la base de datos SQLite y los repositorios SQLite de todas las entidades y los servicios de usuarios, agenda, recordatorios y hábitos.

## Reglas
1. `app/domain` es puro: sin SQL, sin FastAPI, sin librerías de IA, sin I/O.
2. Los datos externos entran por esquemas Pydantic antes de crear objetos de dominio.
3. El modelo de lenguaje nunca accede a la base de datos; solo llama a herramientas que usan servicios.
4. Los agentes no contienen lógica de negocio: delegan en servicios.
5. Fechas siempre con zona horaria; se guardan en UTC.

## Ejemplo: "¿qué tengo hoy?"
1. El agente detecta la intención y llama a una herramienta.
2. La herramienta pide al servicio los eventos, hábitos y recordatorios del usuario.
3. `resumen_del_dia` calcula el resultado en Python, sin modelo de lenguaje.
4. El modelo, si se usa, solo redacta la respuesta con ese resultado.

## Fronteras de importación
Las vigila `tests/test_importaciones.py`, que analiza los `import` con `ast` sin ejecutar código.
Cada fallo indica archivo y línea.

| Capa | Puede importar | Bibliotecas externas |
|---|---|---|
| `domain` | `domain` | No |
| `schemas` | `domain`, `schemas` | Sí |
| `database` | `database` | No |
| `repositories` | `domain`, `database`, `repositories` | No |
| `services` | `domain`, `schemas`, `repositories.interfaces`, `services` | No |
| `tools` (futura) | `domain`, `schemas`, `services`, `tools` | Sí |
| `llm` (futura) | solo `llm` | Sí |
| `agents` (futura) | `domain.message`, `llm`, `tools`, `agents` | Sí |

- `sqlite3` solo se usa en `database` y `repositories`.
- Las implementaciones `sqlite_*` solo las importa `app/composicion.py`, que es el único archivo exento.
- Para permitir una dependencia nueva hay que ampliar `REGLAS` en el test y dejarlo escrito aquí.
