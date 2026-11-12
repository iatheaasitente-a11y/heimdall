from contextlib import nullcontext
from types import SimpleNamespace
from uuid import uuid4

from app import chatbot
from app.llm.ollama import MotorOllama


def test_chatbot_calienta_ollama_al_arrancar(monkeypatch):
    usuario_id = uuid4()
    motor = MotorOllama()
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
    motor = MotorOllama()
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
        lambda _ruta: nullcontext(SimpleNamespace(commit=lambda: None)),
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
