# Agenda de Heimdall

## Crear eventos

```text
crea un evento dentista manana a las 10 durante 1 hora
```

```text
crea un evento dentista manana a las 10 durante 1 hora
en la clinica sonrisa, llevar tarjeta
```

El bot propone el evento y pide confirmacion con `si` o `no`.

## Consultar

```text
que tengo hoy?
que tengo esta semana?
cual es mi proxima cita?
cuando tengo el dentista?
huecos libres el viernes de 10 a 18
```

## Reprogramar

```text
mueve el evento dentista al viernes a las 16
```

Conserva la duracion original del evento.

## Cancelar y completar

```text
cancela el evento dentista
completa el evento dentista
```

Ambas acciones piden confirmacion.

## Eventos recurrentes

```text
gimnasio lunes, miercoles y viernes a las 15 durante 1 hora
```

## Recordatorios

```text
recuerdame llamar a mama manana a las 10
cancela el recordatorio llamar a mama
```

## Conflictos de horario

Si dos eventos se solapan, el bot ofrece:

```text
1. Elegir otra hora para el nuevo evento
2. Mover el evento existente
3. Cancelar el existente y crear el nuevo
```

Responde `1`, `2` o `3`.
