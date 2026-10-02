"""Gera app/static/emoji/pt.json (emojis em português, Emoji 17) no formato que o
emoji-picker-element lê. Rode de novo quando sair uma versão nova do Unicode:
    python gerar_emoji.py      (baixa emojibase-data@latest/pt)
"""
import json
import os

import requests

PASTA = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'app', 'static', 'emoji')
os.makedirs(PASTA, exist_ok=True)

dados = requests.get('https://cdn.jsdelivr.net/npm/emojibase-data@latest/pt/data.json', timeout=60).json()
saida = []
for e in dados:
    # group 2 = componentes (tons de pele soltos); sem grupo = indicadores regionais soltos
    if e.get('group') is None or e.get('group') == 2:
        continue
    item = {
        'annotation': e.get('label') or '',
        'emoji': e['emoji'],
        'tags': e.get('tags') or [],
        'group': e['group'],
        'order': e.get('order', 0),
        'version': e.get('version', 1),
    }
    if e.get('shortcodes'):
        item['shortcodes'] = e['shortcodes']
    emoticon = e.get('emoticon')
    if isinstance(emoticon, list):          # o picker espera texto, não lista
        emoticon = emoticon[0] if emoticon else None
    if isinstance(emoticon, str) and emoticon:
        item['emoticon'] = emoticon
    if e.get('skins'):
        item['skins'] = [{'tone': s.get('tone'), 'emoji': s['emoji'], 'version': s.get('version', 1)} for s in e['skins']]
    saida.append(item)

destino = os.path.join(PASTA, 'pt.json')
with open(destino, 'w', encoding='utf-8') as f:
    json.dump(saida, f, ensure_ascii=False, separators=(',', ':'))
print(len(saida), 'emojis;', os.path.getsize(destino) // 1024, 'KB')
