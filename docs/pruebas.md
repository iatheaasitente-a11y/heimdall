# Pruebas

Se ejecutan con `pytest -q` (configuración en `pytest.ini`, `pythonpath = .`).
Instala las dependencias de desarrollo con `pip install -r requirements-dev.txt`;
`requirements.txt` contiene las dependencias de ejecución.
Esperado hoy: 272 tests en verde.

| Archivo | Tests |
|---|---|
| test_user.py | 4 |
| test_message.py | 3 |
| test_schedule.py | 6 |
| test_habit.py | 5 |
| test_goal.py | 5 (uno parametrizado) |
| test_reminder.py | 4 |
| test_extras.py | 9 |
| test_relations.py | 5 |
| test_schemas.py | 7 |
| test_schemas_resto.py | 15 |
| test_horario_usuarios.py | 2 |
| test_schemas_texto.py | 10 |
| test_database.py | 12 |
| test_fechas.py | 4 |
| test_repo_usuarios.py | 6 |
| test_repo_eventos.py | 9 |
| test_repo_habitos.py | 16 |
| test_repo_objetivos.py | 10 |
| test_repo_recordatorios.py | 14 |
| test_repo_conversaciones.py | 19 |
| test_servicios_usuarios.py | 9 |
| test_servicios_agenda.py | 25 |
| test_servicios_recordatorios.py | 19 |
| test_agenda_recordatorios.py | 6 |
| test_importaciones.py | 28 |
| test_transiciones.py | 18 |
| test_calidad.py | 2 |

## Convenciones
- Un archivo de test por módulo de dominio.
- Cada clase o función nueva entra con su test.
- Los datetimes de los tests llevan zona (UTC o Europe/Madrid).
- Se prueban casos de error con `pytest.raises`.
