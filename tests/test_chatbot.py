import json
import sqlite3
from contextlib import nullcontext
from datetime import UTC, datetime
from threading import Thread, local
from types import SimpleNamespace
from uuid import uuid4

from app import chatbot
from app.composicion import crear_composicion
from app.llm import MotorFalso, RespuestaEstructurada
from app.llm.ollama import MotorOllama


def test_chatbot_calienta_ollama_al_arrancar(monkeypatch):
    usuario_id = uuid4()
    motor = MotorOllama(modelo="modelo-prueba")
    usuario = SimpleNamespace(id=usuario_id)
    aplicacion = SimpleNamespace(
        usuarios=SimpleNamespace(obtener=lambda _usuario_id: usuario),
        conversaciones=SimpleNamespace(
            iniciar_conversacion=lambda _usuario_id, _titulo: SimpleNamespace(
                id=uuid4()
            )
        ),
        router=SimpleNamespace(procesar=lambda *_args: None),
    )
    llamadas = []

    monkeypatch.setattr(
        "sys.argv",
        ["chatbot", "--usuario-id", str(usuario_id)],
    )
    monkeypatch.setattr(chatbot, "inicializar_base_datos", lambda _ruta: None)
    monkeypatch.setattr(chatbot, "sesion_sqlite", lambda _ruta: nullcontext(object()))
    monkeypatch.setattr(chatbot, "crear_motor", lambda: motor)
    monkeypatch.setattr(
        chatbot,
        "crear_composicion",
        lambda _conexion, **_kwargs: aplicacion,
    )
    monkeypatch.setattr(motor, "calentar", lambda: llamadas.append("calentar"))
    monkeypatch.setattr("builtins.input", lambda _prompt: "/salir")

    chatbot.main()

    assert llamadas == ["calentar"]


def test_chatbot_avisa_si_ollama_no_calienta_y_sigue_con_reglas(
    monkeypatch,
    capsys,
):
    usuario_id = uuid4()
    motor = MotorOllama(modelo="modelo-prueba")
    usuario = SimpleNamespace(id=usuario_id)
    llamadas = []

    def procesar(_usuario_id, _conversacion_id, texto, _historial):
        llamadas.append(texto)
        return {"ok": True, "datos": {"dia": "2026-11-12"}}

    aplicacion = SimpleNamespace(
        usuarios=SimpleNamespace(obtener=lambda _usuario_id: usuario),
        conversaciones=SimpleNamespace(
            iniciar_conversacion=lambda _usuario_id, _titulo: SimpleNamespace(
                id=uuid4()
            ),
            agregar_mensaje=lambda *_args, **_kwargs: None,
            historial_para_modelo=lambda *_args: [],
        ),
        router=SimpleNamespace(procesar=procesar),
    )
    monkeypatch.setattr(
        "sys.argv",
        ["chatbot", "--usuario-id", str(usuario_id)],
    )
    monkeypatch.setattr(chatbot, "inicializar_base_datos", lambda _ruta: None)
    monkeypatch.setattr(
        chatbot,
        "sesion_sqlite",
        lambda _ruta: nullcontext(
            SimpleNamespace(
                commit=lambda: None,
                execute=lambda *_args: None,
                rollback=lambda: None,
            )
        ),
    )
    monkeypatch.setattr(chatbot, "crear_motor", lambda: motor)
    monkeypatch.setattr(
        chatbot,
        "crear_composicion",
        lambda _conexion, **_kwargs: aplicacion,
    )
    monkeypatch.setattr(
        motor,
        "calentar",
        lambda: (_ for _ in ()).throw(OSError("servidor apagado")),
    )
    entrada = iter(["¿Qué tengo hoy?", "/salir"])
    monkeypatch.setattr("builtins.input", lambda _prompt: next(entrada))

    chatbot.main()

    assert llamadas == ["¿Qué tengo hoy?"]
    assert "no se pudo precalentar Ollama" in capsys.readouterr().err


def test_chatbot_guarda_el_mensaje_antes_de_un_fallo_del_router(
    monkeypatch,
    caplog,
    capsys,
):
    usuario_id = uuid4()
    conversacion_id = uuid4()
    eventos = []

    def agregar_mensaje(_usuario_id, _conversacion_id, rol, contenido, *_args):
        eventos.append(("mensaje", rol.value, contenido))

    def procesar(*_args):
        eventos.append(("router",))
        raise sqlite3.OperationalError("base bloqueada")

    def historial(*_args):
        eventos.append(("historial",))
        return []

    aplicacion = SimpleNamespace(
        usuarios=SimpleNamespace(
            obtener=lambda _usuario_id: SimpleNamespace(id=usuario_id)
        ),
        conversaciones=SimpleNamespace(
            iniciar_conversacion=lambda *_args: SimpleNamespace(id=conversacion_id),
            agregar_mensaje=agregar_mensaje,
            historial_para_modelo=historial,
        ),
        router=SimpleNamespace(procesar=procesar),
    )

    def ejecutar(sql):
        eventos.append(("transaccion", sql))

    conexion = SimpleNamespace(
        commit=lambda: eventos.append(("commit",)),
        execute=ejecutar,
        rollback=lambda: eventos.append(("rollback",)),
    )
    monkeypatch.setattr(
        "sys.argv",
        ["chatbot", "--usuario-id", str(usuario_id)],
    )
    monkeypatch.setattr(chatbot, "inicializar_base_datos", lambda _ruta: None)
    monkeypatch.setattr(chatbot, "sesion_sqlite", lambda _ruta: nullcontext(conexion))
    monkeypatch.setattr(chatbot, "crear_motor", lambda: None)
    monkeypatch.setattr(
        chatbot,
        "crear_composicion",
        lambda _conexion, **_kwargs: aplicacion,
    )
    entrada = iter(["¿Qué tengo hoy?", "/salir"])
    monkeypatch.setattr("builtins.input", lambda _prompt: next(entrada))

    chatbot.main()

    salida = capsys.readouterr().out
    assert [evento[0] for evento in eventos] == [
        "mensaje",
        "commit",
        "transaccion",
        "historial",
        "router",
        "rollback",
        "mensaje",
        "commit",
    ]
    assert eventos[2] == ("transaccion", "BEGIN IMMEDIATE")
    assert eventos[0][2] == "¿Qué tengo hoy?"
    assert eventos[6][1] == "asistente"
    assert json.loads(eventos[6][2]) == {
        "ok": False,
        "error": "No se pudo completar la solicitud por un error interno.",
    }
    assert "error interno" in salida
    assert "Fallo inesperado al procesar un turno." in caplog.text


def test_confirmacion_concurrente_se_ejecuta_una_sola_vez(tmp_path, monkeypatch):
    ruta = tmp_path / "confirmaciones.sqlite3"
    chatbot.inicializar_base_datos(ruta)
    reloj = lambda: datetime(2026, 11, 12, 12, tzinfo=UTC)
    with chatbot.sesion_sqlite(ruta) as conexion:
        aplicacion = crear_composicion(conexion, reloj, MotorFalso([]))
        usuario_id = aplicacion.usuarios.registrar("Usuario").id
        conversacion = aplicacion.conversaciones.iniciar_conversacion(
            usuario_id,
            "Confirmación concurrente",
        )
        creado = aplicacion.herramientas.obtener("agenda_crear_evento").ejecutar(
            usuario_id,
            {
                "titulo": "Cita",
                "comienza": "2026-11-15T12:00:00+00:00",
                "termina": "2026-11-15T13:00:00+00:00",
            },
        )
        evento_id = creado["datos"]["id"]
        propuesta = {
            "ok": False,
            "error": "Confirma la cancelación.",
            "confirmacion_pendiente": {
                "usuario_id": str(usuario_id),
                "conversacion_id": str(conversacion.id),
                "herramienta": "agenda_cancelar_evento",
                "campos": {"evento_id": evento_id, "titulo": None},
                "requiere_reconfirmacion": False,
            },
        }
        aplicacion.conversaciones.agregar_mensaje(
            usuario_id,
            conversacion.id,
            "asistente",
            json.dumps(propuesta),
        )
        conexion.execute(
            "CREATE TABLE confirmacion_ejecuciones (cantidad INTEGER NOT NULL)"
        )
        conexion.execute("INSERT INTO confirmacion_ejecuciones VALUES (0)")

    estado_hilo = local()
    errores = []
    monkeypatch.setattr(chatbot, "inicializar_base_datos", lambda _ruta: None)
    monkeypatch.setattr(
        "sys.argv",
        ["chatbot", "--database", str(ruta), "--usuario-id", str(usuario_id)],
    )
    monkeypatch.setattr(
        "builtins.input",
        lambda _prompt: _entrada_confirmacion(estado_hilo),
    )
    monkeypatch.setattr(chatbot, "crear_motor", lambda: MotorFalso([]))

    def crear_aplicacion(conexion, **_argumentos):
        aplicacion = crear_composicion(
            conexion,
            reloj,
            MotorFalso(
                [RespuestaEstructurada("herramienta_inexistente", {}, 0.9)]
            ),
        )
        aplicacion.conversaciones.iniciar_conversacion = (
            lambda *_args: conversacion
        )
        herramienta = aplicacion.herramientas.obtener("agenda_cancelar_evento")
        ejecutar = herramienta._ejecutar

        def contar_y_ejecutar(usuario, campos):
            conexion.execute(
                "UPDATE confirmacion_ejecuciones SET cantidad = cantidad + 1"
            )
            return ejecutar(usuario, campos)

        herramienta._ejecutar = contar_y_ejecutar
        return aplicacion

    monkeypatch.setattr(chatbot, "crear_composicion", crear_aplicacion)

    def ejecutar_chatbot():
        try:
            chatbot.main()
        except Exception as error:
            errores.append(error)

    hilos = [Thread(target=ejecutar_chatbot) for _ in range(2)]
    for hilo in hilos:
        hilo.start()
    for hilo in hilos:
        hilo.join(timeout=10)

    assert all(not hilo.is_alive() for hilo in hilos)
    assert errores == []
    with sqlite3.connect(ruta) as conexion:
        cantidad = conexion.execute(
            "SELECT cantidad FROM confirmacion_ejecuciones"
        ).fetchone()[0]
        estado = conexion.execute(
            "SELECT estado FROM eventos WHERE id = ?",
            (evento_id,),
        ).fetchone()[0]
    assert cantidad == 1
    assert estado == "cancelado"


def _entrada_confirmacion(estado_hilo):
    """Entrega una confirmación y después termina cada chat de prueba."""
    indice = getattr(estado_hilo, "indice", 0)
    estado_hilo.indice = indice + 1
    return ("sí", "/salir")[indice]
