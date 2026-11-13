# Mejoras de agenda - Heimdall

## Estado actual

- Crear, cancelar, completar y reprogramar eventos.
- Consultar por día, rango (semana, mes), próximo evento y huecos libres.
- Menú de conflictos: 1 = otra hora, 2 = mover el existente, 3 = cancelar y crear.
- Lugar y notas en los eventos.
- Eventos recurrentes: varios días a la misma hora.
- Recordatorios con fecha y hora explícitas.
- Cancelar recordatorio con confirmación.
- Agendado paso a paso: si falta título, día, hora o duración, el agente pregunta de uno en uno.
- Recordatorio automático al crear cita: al crear un evento se genera un aviso para su inicio.
- Eventos de todo el día: al crear un evento con `todo_el_dia=True`, se ajusta al día completo.
- Repeticiones semanales/mensuales: campo `repeticion` con valores `semanal` o `mensual`, y método `siguiente_ocurrencia()` para calcular la próxima fecha.
- Cancelar/reprogramar por título: `ServicioAgendaPorTitulo` permite cancelar o reprogramar un evento usando su título en vez de su ID.
- Recordatorios recurrentes: campo `repeticion` en `Recordatorio` con valores `semanal` o `mensual`, y método `siguiente_ocurrencia()` para calcular la próxima fecha.
- Avisos previos configurables: `ServicioAvisosPrevios` permite programar un aviso X minutos antes del inicio de un evento.
- Búsqueda por rango con filtro: `ServicioBusquedaEventos` permite consultar eventos entre dos fechas y filtrar por estado, lugar o texto.

## Flujo de agendado actual

1. "Quiero agendar dentista" -> pregunta título si falta.
2. "mañana" -> pregunta hora.
3. "a las 10" -> pregunta duración.
4. "1 hora" -> crea el evento y genera el recordatorio automático.
5. Si el mensaje ya trae todo, las reglas lo crean de una vez.

## Roadmap de mejoras

| # | Mejora | Estado |
|---|--------|--------|
| 1 | Agendar paso a paso | Hecha |
| 2 | Recordatorio automático al crear cita | Hecha |
| 3 | Eventos de todo el día | Hecha |
| 4 | Repeticiones semanales/mensuales | Hecha |
| 5 | Cancelar/reprogramar por título | Hecha |
| 6 | Recordatorios recurrentes | Hecha |
| 7 | Avisos previos configurables | Hecha |
| 8 | Búsqueda por rango con filtro | Hecha |

## Documentación de mejoras

### 1. Agendar paso a paso

**Qué hace:** permite crear una cita mediante una conversación guiada. Si falta el título, el día, la hora o la duración, el asistente solicita únicamente el dato que falta antes de crear el evento.

**Archivos implicados:**

- `app/services/agenda.py`: lógica de creación y validación de eventos.
- `app/agentes/reglas.py`: reglas conversacionales para extraer datos y decidir cuándo crear la cita.
- `tests/test_agenda_paso_a_paso.py`: verifica el flujo de preguntas y la creación cuando faltan datos.
- `tests/test_agente_reglas.py`: cubre la interpretación de mensajes y reglas del agente.

**Tests asociados:** `tests/test_agenda_paso_a_paso.py` y `tests/test_agente_reglas.py`.

### 2. Recordatorio automático al crear cita

**Qué hace:** al crear un evento de agenda, se genera automáticamente un recordatorio asociado a la fecha y hora de inicio de ese evento.

**Archivos implicados:**

- `app/services/agenda.py`: crea el evento y enlaza la generación del recordatorio.
- `app/services/recordatorios.py`: gestiona la creación y persistencia de recordatorios.
- `tests/test_mejora_2_recordatorio_automatico.py`: comprueba que crear una cita genera el recordatorio correspondiente.
- `tests/test_recordatorio_evento.py`: valida la relación entre eventos y recordatorios.

**Tests asociados:** `tests/test_mejora_2_recordatorio_automatico.py` y `tests/test_recordatorio_evento.py`.

### 3. Eventos de todo el día

**Qué hace:** permite marcar un evento como `todo_el_dia=True`. El sistema ajusta las horas de inicio y fin para representar correctamente un evento que ocupa el día completo.

**Archivos implicados:**

- `app/models/evento.py`: modelo de evento y campo `todo_el_dia`.
- `app/services/agenda.py`: normalización de horas para eventos de todo el día.
- `tests/test_mejora_3_todo_el_dia.py`: verifica la creación y el ajuste temporal del evento.

**Tests asociados:** `tests/test_mejora_3_todo_el_dia.py`.

### 4. Repeticiones semanales y mensuales

**Qué hace:** añade el campo `repeticion` a los eventos, con los valores `semanal` y `mensual`. El método `siguiente_ocurrencia()` calcula la siguiente fecha en la que debe repetirse el evento.

**Archivos implicados:**

- `app/models/evento.py`: campo `repeticion` y método `siguiente_ocurrencia()`.
- `app/services/agenda.py`: integración de la repetición en la gestión de eventos.
- `tests/test_mejora_4_repeticiones.py`: cubre repeticiones semanales, mensuales y el cálculo de la próxima ocurrencia.
- `tests/test_eventos_recurrentes.py`: cubre eventos recurrentes existentes.

**Tests asociados:** `tests/test_mejora_4_repeticiones.py` y `tests/test_eventos_recurrentes.py`.

### 5. Cancelar y reprogramar por título

**Qué hace:** permite cancelar o reprogramar un evento utilizando su título en lugar de su identificador interno. `ServicioAgendaPorTitulo` localiza el evento por título y ejecuta la operación solicitada.

**Archivos implicados:**

- `app/services/agenda_por_titulo.py`: servicio de búsqueda y modificación de eventos por título.
- `app/services/agenda.py`: operaciones de cancelación y reprogramación.
- `tests/test_mejora_5_cancelar_por_titulo.py`: verifica la cancelación y reprogramación mediante título.
- `tests/test_reprogramar.py`: cubre la reprogramación de eventos.

**Tests asociados:** `tests/test_mejora_5_cancelar_por_titulo.py` y `tests/test_reprogramar.py`.

### 6. Recordatorios recurrentes

**Qué hace:** añade el campo `repeticion` a los recordatorios, con los valores `semanal` y `mensual`. El método `siguiente_ocurrencia()` determina cuándo debe mostrarse o enviarse el siguiente aviso.

**Archivos implicados:**

- `app/models/recordatorio.py`: campo `repeticion` y método `siguiente_ocurrencia()`.
- `app/services/recordatorios.py`: creación y gestión de recordatorios recurrentes.
- `tests/test_mejora_6_recordatorios_recurrentes.py`: valida recordatorios semanales, mensuales y el cálculo de la siguiente ocurrencia.
- `tests/test_recordatorios_envio.py`: cubre el envío o procesamiento de recordatorios.

**Tests asociados:** `tests/test_mejora_6_recordatorios_recurrentes.py` y `tests/test_recordatorios_envio.py`.

### 7. Avisos previos configurables

**Qué hace:** permite programar un aviso un número configurable de minutos antes del inicio de un evento. `ServicioAvisosPrevios` calcula la fecha y hora del aviso a partir del evento y del intervalo indicado.

**Archivos implicados:**

- `app/services/avisos_previos.py`: cálculo y creación de avisos previos.
- `app/services/agenda.py`: acceso a los datos del evento necesario para programar el aviso.
- `tests/test_mejora_7_avisos_previos.py`: verifica la creación del aviso y el cálculo de la hora previa.

**Tests asociados:** `tests/test_mejora_7_avisos_previos.py`.

### 8. Búsqueda por rango con filtro

**Qué hace:** permite buscar eventos dentro de un intervalo de fechas y aplicar filtros adicionales. `ServicioBusquedaEventos` recibe una fecha inicial, una fecha final y filtros opcionales para devolver únicamente los eventos que cumplen los criterios.

**Filtros disponibles:**

- Rango de fechas: fecha inicial y fecha final.
- Estado del evento.
- Lugar del evento.
- Texto contenido en el evento.

**Archivos implicados:**

- `app/services/busqueda_eventos.py`: servicio `ServicioBusquedaEventos`, responsable de aplicar el rango y los filtros.
- `app/services/agenda.py`: fuente de eventos y operaciones relacionadas con la agenda.
- `tests/test_mejora_8_busqueda_rango.py`: cubre la búsqueda por rango, los filtros y los casos sin resultados.

**Tests asociados:** `tests/test_mejora_8_busqueda_rango.py`.

## Archivos creados o modificados

| Archivo | Tipo de cambio | Cambio realizado |
|---|---|---|
| `app/services/agenda.py` | Modificado | Integración del agendado paso a paso, recordatorio automático, eventos de todo el día, repeticiones, cancelación/reprogramación y avisos previos. |
| `app/services/recordatorios.py` | Modificado | Soporte para recordatorios automáticos y recurrentes. |
| `app/services/agenda_por_titulo.py` | Creado o modificado | Servicio para cancelar y reprogramar eventos por título. |
| `app/services/avisos_previos.py` | Creado o modificado | Servicio para programar avisos previos configurables. |
| `app/services/busqueda_eventos.py` | Creado | Servicio `ServicioBusquedaEventos` para buscar eventos por rango de fechas y filtros. |
| `app/models/evento.py` | Modificado | Campos y lógica para eventos de todo el día y repeticiones semanales/mensuales. |
| `app/models/recordatorio.py` | Modificado | Campo `repeticion` y método `siguiente_ocurrencia()` para recordatorios recurrentes. |
| `tests/test_agenda_paso_a_paso.py` | Creado o modificado | Tests del agendado guiado. |
| `tests/test_mejora_2_recordatorio_automatico.py` | Creado | Tests del recordatorio automático al crear una cita. |
| `tests/test_mejora_3_todo_el_dia.py` | Creado | Tests de eventos de todo el día. |
| `tests/test_mejora_4_repeticiones.py` | Creado | Tests de repeticiones semanales y mensuales. |
| `tests/test_mejora_5_cancelar_por_titulo.py` | Creado | Tests de cancelación y reprogramación por título. |
| `tests/test_mejora_6_recordatorios_recurrentes.py` | Creado | Tests de recordatorios recurrentes. |
| `tests/test_mejora_7_avisos_previos.py` | Creado | Tests de avisos previos configurables. |
| `tests/test_mejora_8_busqueda_rango.py` | Creado | Tests de búsqueda por rango con filtros. |
| `docs/mejoras-agenda.md` | Modificado | Estado de las mejoras 1–8 actualizado a "Hecha" y documentación completa añadida. |

## Próximo paso recomendado

Las mejoras 1 a 8 están implementadas, documentadas y cubiertas por tests. El siguiente paso es revisar el pull request hacia `main`, ejecutar la suite de tests y fusionar cuando las comprobaciones sean correctas.
