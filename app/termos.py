"""Termos de Uso e Política de Privacidade (LGPD): versão em vigor e quem precisa aceitar.

Subir `VERSAO` pede o aceite de todo mundo de novo (mudou o que é coletado ou como a segurança funciona). O aceite é gravado na conta
(`Person.termos_versao`, `termos_aceitos_em`). Enquanto não aceita, o /chat leva pra /termos e o socket não responde (`usuario_logado`).

Só é exigido em produção (Render) ou com EXIGIR_TERMOS=1; EXIGIR_TERMOS=0 desliga em qualquer lugar. Fora disso (desenvolvimento e a suíte de
testes) ninguém é barrado.
O texto da página (templates/termos.html) é um modelo honesto do que o app faz de fato: ele deve ser revisado por um advogado antes de a
loja virar comercial.
"""
import os

VERSAO = '2026-10-21'


def exigir():
    pedido = os.getenv('EXIGIR_TERMOS')
    if pedido == '1':
        return True
    if pedido == '0':
        return False
    return bool(os.getenv('RENDER'))


def aceitou(pessoa):
    return bool(pessoa) and (pessoa.termos_versao or '') == VERSAO


def barrada(pessoa):
    """True se a pessoa ainda precisa aceitar os termos pra usar o app."""
    return exigir() and not aceitou(pessoa)


def contato():
    return (os.getenv('CONTATO_PRIVACIDADE') or '').strip()
