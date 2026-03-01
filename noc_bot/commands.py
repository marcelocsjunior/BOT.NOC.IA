# -*- coding: utf-8 -*-
"""
Compatibility shim (V1 QUALITY):
Algumas partes do bot (ou versões antigas) importam `noc_bot.commands`.
A implementação atual vive em `noc_bot.handlers.commands`.

Este arquivo re-exporta o módulo correto para evitar divergência de UX/render.
"""
from .handlers.commands import *  # noqa: F401,F403
