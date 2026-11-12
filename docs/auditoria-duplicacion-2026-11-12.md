# Auditoría de duplicación y refactor de servicios

## Alcance

Se revisaron los módulos Python de `app/`, con atención a los servicios y
herramientas de agenda, hábitos, objetivos y recordatorios. El rastreo AST
buscó cuerpos idénticos en funciones y métodos; la revisión manual contrastó
también comprobaciones equivalentes, usos y contratos cubiertos por los tests.
La auditoría se hizo el 12 de noviembre de 2026, antes del refactor descrito
abajo.

## Duplicación encontrada

Las líneas de esta tabla corresponden a la versión anterior al cambio.

| Patrón | Archivo y función | Líneas |
|---|---|---:|
| Comprobar usuario existente | `app/services/agenda.py`, `_exigir_usuario` | 195 |
| Idem | `app/services/habitos.py`, `_exigir_usuario` | 215 |
| Idem | `app/services/objetivos.py`, `_exigir_usuario` | 187 |
| Idem | `app/services/recordatorios.py`, `_exigir_usuario` | 177 |
| Idem | `app/services/conversaciones.py`, `_exigir_usuario` | 195 |
| Idem, expuesto como operación pública | `app/services/usuarios.py`, `obtener` | 38 |
| Comprobar que la entidad existe y pertenece al usuario | `app/services/agenda.py`, `obtener_evento` | 82 |
| Idem | `app/services/habitos.py`, `_obtener` | 208 |
| Idem | `app/services/objetivos.py`, `_obtener` | 180 |
| Idem | `app/services/recordatorios.py`, `_obtener` | 170 |
| Idem | `app/services/conversaciones.py`, `_obtener` | 188 |
| Resolver un nombre exacto, normalizarlo y construir candidatos | `app/tools/resolucion.py`, `resolver_por_nombre` | 19–46 |
| Elegir UUID o resolver título | `app/tools/agenda.py`, `evento_id` | 12 |
| Elegir UUID o resolver nombre | `app/tools/habitos.py`, `habito_id` | 17 |
| Idem | `app/tools/objetivos.py`, `objetivo_id` | 17 |
| Elegir UUID o resolver mensaje | `app/tools/recordatorios.py`, `recordatorio_id` | 19 |

También se encontraron repeticiones menores que no duplicaban reglas:

- Seis validadores Pydantic `exigir_un_selector` en
  `app/tools/esquemas.py` delegaban en `_validar_selector` (línea 177).
- Los normalizadores de `app/domain/lenguaje_fechas.py` (línea 284) y
  `app/agents/reglas.py` (línea 449) comparten el tratamiento de mayúsculas,
  tildes y espacios, pero difieren al recortar puntuación. No se unificaron
  para no alterar la interpretación de expresiones naturales.
- Varios repositorios repiten constructores que guardan la conexión; son
  asignaciones de una línea sin reglas de negocio. Los tests también repiten
  fixtures locales de fecha y conexión. No se introdujeron abstracciones para
  estas repeticiones de bajo coste.

## Refactor aplicado

| Archivo | Cambio |
|---|---|
| `app/services/errores.py` | Añade `exigir_usuario`, `obtener_entidad_de_usuario` y `ErrorResolucionNombre`; el error conserva la lista de candidatos. |
| `app/services/resolucion.py` | Centraliza la normalización y la selección por nombre exacto, incluyendo el error por cero o múltiples coincidencias. |
| `app/services/usuarios.py` | Delega la consulta de un usuario en `exigir_usuario`. |
| `app/services/agenda.py`, `habitos.py`, `objetivos.py`, `recordatorios.py`, `conversaciones.py` | Reutilizan las comprobaciones comunes de usuario y propiedad. Agenda, hábitos, objetivos y recordatorios resuelven selectores desde el servicio, limitados al usuario solicitante. |
| `app/tools/agenda.py`, `habitos.py`, `objetivos.py`, `recordatorios.py` | Conservan la traducción de UUID/nombre a argumentos de servicio; dejan de listar entidades y resolver coincidencias por su cuenta. |
| `app/tools/base.py` | Importa `ErrorResolucionNombre` desde servicios y sigue serializando sus candidatos. |
| `app/tools/errores.py`, `app/tools/resolucion.py` | Se eliminan tras mover sus responsabilidades a `app/services/`. |
| `docs/arquitectura.md`, `docs/servicios.md` | Documentan la frontera entre servicios y herramientas y los helpers comunes. |

La búsqueda mantiene el contrato previo: coincidencia exacta, ignorando
mayúsculas, tildes y espacios exteriores; solo se buscan elementos del usuario
actual. Si hay cero o varias coincidencias, la respuesta conserva el texto de
error y la lista de candidatos. Las herramientas siguen validando la forma de
los argumentos mediante Pydantic. `ErrorResolucionNombre` hereda tanto de
`ErrorDeServicio` como de `ValueError`, por lo que conserva la compatibilidad
de captura anterior al traslado.

## Validación

La suite completa se ejecutó con:

```text
.\.venv\Scripts\python.exe -m pytest -q
772 passed, 2 skipped
```

`git diff --check` terminó sin errores. Los tests existentes de servicios,
herramientas e importaciones cubren permisos por usuario, nombres con
mayúsculas/tildes, coincidencias ambiguas, candidatos y selectores inválidos;
se añadió además una comprobación de que el error trasladado conserva su
compatibilidad con `ValueError` y `ErrorDeServicio`.
