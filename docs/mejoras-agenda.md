# Mejoras de agenda — Heimdall

## Estado actual

- **817 tests en verde** (0 fallos).
- Rama: `refactor/unificar-duplicados`.
- Último commit: `39c9eba` — *feat: recordatorios ligados a citas, menu de conflictos y lugar/notas*.

## Funciones ya implementadas

- Crear, cancelar, completar y reprogramar eventos.
- Consultar por día, rango (semana, mes), próximo evento y huecos libres.
- Recordatorios ligados a citas: "recuérdame el dentista 30 minutos antes".
- Menú de conflictos: 1 = otra hora, 2 = mover el existente, 3 = cancelar y crear.
- Lugar y notas en los eventos: "en la clinica sonrisa, notas: llevar tarjeta".
- Eventos recurrentes: varios días a la misma hora.
- Recordatorios con fecha y hora explícitas.
- Cancelar recordatorio con confirmación.

## Flujo de agendado actual

1. "Crea un evento dentista mañana a las 10 durante 1 hora" → propuesta.
2. "sí" → se crea.
3. Si hay conflicto → menú de 3 opciones.
4. "recuérdame el dentista 30 minutos antes" → propuesta de recordatorio.
5. "sí" → se crea el recordatorio.

## Roadmap de mejoras

| # | Mejora | Estado |
|---|--------|--------|
| 1 | Agendar paso a paso (título → día → hora → duración) | Pendiente |
| 2 | Recordatorio automático al crear cita | Pendiente |
| 3 | Eventos de todo el día | Pendiente |
| 4 | Repeticiones semanales/mensuales | Pendiente |
| 5 | Cancelar/reprogramar por título | Pendiente |
| 6 | Recordatorios recurrentes | Pendiente |
| 7 | Avisos previos configurables | Pendiente |
| 8 | Búsqueda por rango con filtro | Pendiente |

## Próximo paso recomendado

**Mejora 1: agendar paso a paso.** Si falta algo, el agente pregunta de una en una: título → día → hora → duración. Mejora mucho la UX y encaja con lo que ya hay.
