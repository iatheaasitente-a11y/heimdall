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
