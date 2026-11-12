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
| 4 | Repeticiones semanales/mensuales | Pendiente |
| 5 | Cancelar/reprogramar por título | Pendiente |
| 6 | Recordatorios recurrentes | Pendiente |
| 7 | Avisos previos configurables | Pendiente |
| 8 | Búsqueda por rango con filtro | Pendiente |

## Próximo paso recomendado

Mejora 4: repeticiones semanales/mensuales.