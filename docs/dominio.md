# Dominio (app/domain)

Todas las clases son `dataclass`. Los identificadores son `UUID` (`uuid4`).
Los objetos se enlazan por `*_id`, no por anidación.

## user.py
`Usuario`: nombre, id, idioma (`es-ES`), zona_horaria (`Europe/Madrid`),
preferencias (dict), fecha_creacion (UTC), activo.
Métodos: `cambiar_preferencia`, `desactivar`, `zona()` (devuelve `ZoneInfo`).

## message.py
`RolMensaje`: usuario, asistente, sistema, herramienta.
`Conversacion`: usuario_id, titulo, id, fecha_creacion, activa.
`Mensaje`: conversacion_id, rol, contenido, id, fecha_creacion, metadatos.
Método: `esta_vacio()` (true si solo hay espacios).

## schedule.py
`EstadoEvento`: programado, completado, cancelado.
`Evento`: usuario_id, titulo, comienza, termina, id, descripcion, ubicacion, estado.
- `__post_init__` exige `termina > comienza` (`ValueError`).
- `cancelar` y `completar` solo valen desde PROGRAMADO (si no, `TransicionNoPermitida`); `restablecer()` es la corrección manual explícita.
- `esta_activo` (solo PROGRAMADO), `duracion`.
- `se_solapa_con(otro)`: solape estricto; 10–11 y 11–12 no chocan.

`Horario(eventos)`:
- `eventos_ordenados()`
- `eventos_del_dia(dia, zona)`: solo activos, día calculado en la zona dada.
- `hay_conflicto(nuevo)`: contra los eventos activos del mismo usuario.
- `celdas_del_dia(dia, zona, minutos=15)`: lista de booleanos (ocupado/libre). Se calcula, no se guarda. 96 celdas de 15 min; el día de cambio de hora tiene más o menos según el cambio.

## habit.py
`FrecuenciaHabito`: diaria, semanal, mensual.
`Habito`: usuario_id, nombre, frecuencia, id, descripcion, objetivo (1.0), unidad (`veces`), activo.
- `__post_init__` exige `objetivo > 0`.
- `cumple(valor)`: `valor >= objetivo`. `desactivar()`.

`RegistroHabito`: habito_id, valor, completado, id, fecha (UTC), notas.

## goal.py
`EstadoObjetivo`: activo, completado, pausado, cancelado.
`Objetivo`: usuario_id, nombre, id, descripcion, fecha_limite, progreso (0.0), estado.
- `actualizar_progreso(p)`: exige 0–100; con 100 exacto pasa a COMPLETADO.
- `pausar`, `cancelar`, `dias_restantes(hoy)` (None sin fecha), `esta_vencido(hoy)` (solo si está activo).

## reminder.py
`EstadoRecordatorio`: pendiente, enviado, cancelado.
`Recordatorio`: usuario_id, mensaje, programado_para, id, evento_id, habito_id, estado.
- `marcar_enviado` y `cancelar` solo valen desde PENDIENTE (si no, `TransicionNoPermitida`); `restablecer()` es la corrección manual explícita.
- `esta_vencido(ahora)` (pendiente y ya pasada su hora).

## relations.py (funciones puras)
| Función | Qué hace |
|---|---|
| `de_usuario(usuario, elementos)` | Filtra por `usuario_id` |
| `registros_de(habito, registros)` | Registros de un hábito |
| `recordatorios_de_evento(evento, recs)` | Recordatorios de un evento |
| `mensajes_de(conversacion, mensajes)` | Mensajes de una conversación, ordenados por fecha |
| `historial_para_modelo(mensajes, limite=20)` | Descarta vacíos, traduce roles a user/assistant/system/tool y conserva los últimos `limite` |
| `total_del_dia(habito, registros, dia, zona)` | Suma de `valor` ese día |
| `racha_diaria(habito, registros, hoy, zona)` | Días seguidos cumpliendo el objetivo |
| `resumen_del_dia(usuario, dia, eventos, habitos, registros, recordatorios)` | Diccionario con eventos, hábitos pendientes y recordatorios |

## lenguaje_fechas.py

Funciones puras para expresiones de fecha y hora en español. Las funciones de
resolución reciben un `datetime` con zona horaria en vez de leer el reloj
global. `resolver_fecha` y `resolver_fecha_hora` avanzan hacia el futuro; solo
entienden ayer y anteayer si se pasa `permitir_pasado=True`.
`resolver_hora` conserva la hora ambigua, pero marca `acotada=False` cuando no
se indicó una franja. Las expresiones no resolubles devuelven `None`.
`decir_fecha`, `decir_hora` y `decir_duracion` expresan valores en palabras.

## errores.py
`TransicionNoPermitida` (hereda de `ValueError`): cambio de estado que las reglas no permiten. Guarda `actual` y `destino`.
Transiciones válidas: Evento PROGRAMADO a COMPLETADO o CANCELADO; Recordatorio PENDIENTE a ENVIADO o CANCELADO.
