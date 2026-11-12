# Servicios de aplicación (`app/services/`)

Capa entre los agentes y los repositorios. Cada servicio es un caso de uso:
valida con los esquemas, aplica las reglas del dominio y guarda con los repositorios.

## Reglas
- Reciben los repositorios (interfaces) por el constructor; no conocen SQL.
- Lanzan errores propios (`app/services/errores.py`), no errores de base de datos.
- No hacen `commit`: lo hace quien abre la conexión (`sesion_sqlite`).

## Servicios
| Servicio | Casos de uso |
|---|---|
| `ServicioUsuarios` | registrar, obtener, cambiar zona horaria, desactivar |
| `ServicioAgenda` | crear, cancelar, completar y reprogramar eventos; eventos y celdas del día |
| `ServicioRecordatorios` | programar avisos libres o de un evento, cancelar, marcar enviado, pendientes del día y vencidos |
| `ServicioHabitos` | crear, listar y desactivar hábitos; registrar y borrar progreso; progreso del día y racha |

## Coherencia entre agenda y recordatorios
Si `ServicioAgenda` recibe el repositorio de recordatorios:
- Al cancelar o completar un evento se cancelan sus avisos pendientes.
- Al reprogramarlo, sus avisos pendientes se desplazan lo mismo que se movió el evento.
- Los avisos ya enviados no se tocan.

## Transiciones de estado
El dominio solo permite Evento PROGRAMADO a COMPLETADO o CANCELADO, y Recordatorio PENDIENTE a ENVIADO o CANCELADO. Los servicios convierten el error del dominio en `CambioDeEstadoNoPermitido`. `reprogramar_evento` rechaza los eventos que no estén programados (`EventoNoActivo`). El programador de avisos debe capturar `CambioDeEstadoNoPermitido` en `marcar_enviado`, por si el aviso se canceló entre listarlo y enviarlo.

## Permisos por usuario
Toda operación sobre un evento o recordatorio concreto recibe el `usuario_id` de quien la pide
y solo actúa si el elemento es suyo. Si es de otro usuario, responde igual que si no existiera
(`EventoNoEncontrado` o `RecordatorioNoEncontrado`), para no revelar que existe.
`marcar_enviado` y `vencidos` son operaciones internas del programador de avisos y no se
ofrecerán como herramientas del chatbot.

## Errores
| Error | Cuándo |
|---|---|
| `UsuarioNoEncontrado` | El usuario no existe |
| `EventoNoEncontrado` | El evento no existe |
| `ConflictoDeHorario` | El evento choca con otro activo del mismo usuario |
| `RecordatorioNoEncontrado` | El recordatorio no existe |
| `RecordatorioEnElPasado` | La hora del aviso ya ha pasado |
| `EventoNoActivo` | El evento está cancelado o completado y no admite avisos ni cambios de hora |
| `CambioDeEstadoNoPermitido` | Cambio de estado que las reglas no permiten, por ejemplo cancelar un evento ya completado |
| `HabitoNoEncontrado` | El hábito no existe o es de otro usuario |
| `HabitoInactivo` | El hábito está desactivado y no admite registros |
| `RegistroNoEncontrado` | El registro no existe o no es del hábito indicado |

Los datos mal formados (nombre vacío, zona inexistente, fechas sin zona) siguen
lanzando `pydantic.ValidationError` o `ValueError`.

## Ejemplo de uso

    with sesion_sqlite() as conexion:
        usuarios = RepositorioUsuariosSQLite(conexion)
        eventos = RepositorioEventosSQLite(conexion)
        agenda = ServicioAgenda(usuarios, eventos)
        agenda.crear_evento(usuario_id, "Gimnasio", comienza, termina)
