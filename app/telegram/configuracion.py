"""Configuración de Telegram en la única frontera que lee el entorno."""

import logging
import os
import re
from collections.abc import Mapping
from dataclasses import dataclass, field

_LOG = logging.getLogger(__name__)
_ID_CHAT = re.compile(r"-?[1-9][0-9]*\Z")


@dataclass(frozen=True)
class ConfiguracionTelegram:
    """Credenciales y lista permitida de chats para el conector."""

    token: str | None = field(repr=False)
    chat_ids: frozenset[str]

    def __post_init__(self) -> None:
        """Normaliza credenciales y rechaza IDs de chat inválidos."""
        if self.token is not None and not isinstance(self.token, str):
            raise TypeError("La credencial de Telegram debe ser texto.")
        token = self.token.strip() if self.token is not None else None
        object.__setattr__(self, "token", token or None)
        ids = frozenset(normalizar_chat_id(chat_id) for chat_id in self.chat_ids)
        object.__setattr__(self, "chat_ids", ids)

    @property
    def habilitada(self) -> bool:
        """Indica si hay credencial y al menos un chat válido configurado."""
        return bool(self.token and self.chat_ids)

    @classmethod
    def desde_entorno(
        cls,
        entorno: Mapping[str, str] | None = None,
    ) -> "ConfiguracionTelegram":
        """Lee únicamente ``TELEGRAM_BOT_TOKEN`` y ``TELEGRAM_CHAT_ID``.

        Si no hay IDs válidos, el conector queda cerrado y se registra un error
        sin incluir credenciales.
        """
        valores = os.environ if entorno is None else entorno
        token = valores.get("TELEGRAM_BOT_TOKEN", "").strip() or None
        chat_ids = _parsear_chat_ids(valores.get("TELEGRAM_CHAT_ID", ""))
        if not chat_ids:
            _LOG.error("Telegram cerrado: no hay IDs de chat válidos.")
        elif not token:
            _LOG.error("Telegram cerrado: falta la credencial del bot.")
        return cls(token, chat_ids)


def _parsear_chat_ids(valor: str) -> frozenset[str]:
    """Devuelve los IDs numéricos válidos, normalizados y sin duplicados."""
    ids_validos: set[str] = set()
    for parte in valor.split(","):
        candidato = parte.strip()
        if not candidato or not _ID_CHAT.fullmatch(candidato):
            continue
        try:
            ids_validos.add(normalizar_chat_id(candidato))
        except ValueError:
            continue
    return frozenset(ids_validos)


def normalizar_chat_id(valor: str) -> str:
    """Valida y canonicaliza un identificador de chat numérico."""
    if not isinstance(valor, str) or not _ID_CHAT.fullmatch(valor.strip()):
        raise ValueError("La configuración contiene un ID de chat inválido.")
    return str(int(valor.strip()))
