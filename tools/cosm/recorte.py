"""Recorte das DUAS imagens que os shaders de página desenham no canvas (Rodada 40): os ゴゴゴ do JoJo e a Lança de Longinus.
Todo o resto da arte dos temas é desenhado por código (tools/cosm/arte.js e arte_b.js): o dono pediu pra tirar as imagens recortadas.

Uso (da raiz do repo):   python tools/cosm/recorte.py
Originais de terceiros em docs/refs/jojo/gogogo_roxo.png e docs/refs/eva/lanca_longinus.png; a saída vai em app/static/img/cosm/ (RGBA, fundo transparente).
Se o projeto um dia ficar público, apague app/static/img/cosm/: os shaders caem num desenho de reserva por código (ゴ em texto e uma linha vermelha).
Precisa de numpy e Pillow."""
import os

import numpy as np
from PIL import Image

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
REFS = os.path.join(RAIZ, 'docs', 'refs')
SAIDA = os.path.join(RAIZ, 'app', 'static', 'img', 'cosm')


def alfa_de_branco(im, tol=18, suave=40):
    a = np.asarray(im.convert('RGB')).astype(np.float32)
    return np.clip(((255 - a.min(axis=2)) - tol) / suave, 0, 1)


def com_alfa(im, alfa):
    out = im.convert('RGBA')
    out.putalpha(Image.fromarray((np.clip(alfa, 0, 1) * 255).astype(np.uint8)))
    return out


def salvar(im, tema, nome, lado):
    im = im.convert('RGBA')
    caixa = im.getchannel('A').point(lambda v: 255 if v > 8 else 0).getbbox()
    if caixa:
        im = im.crop(caixa)
    if max(im.size) > lado:
        k = lado / max(im.size)
        im = im.resize((max(1, round(im.width * k)), max(1, round(im.height * k))), Image.LANCZOS)
    pasta = os.path.join(SAIDA, tema)
    os.makedirs(pasta, exist_ok=True)
    caminho = os.path.join(pasta, f'{nome}.png')
    im.save(caminho, 'PNG', optimize=True)
    print(f'  {tema}/{nome}.png  {im.width}x{im.height}  {os.path.getsize(caminho) // 1024} KB')


def gogogo():
    im = Image.open(os.path.join(REFS, 'jojo', 'gogogo_roxo.png')).convert('RGB')
    salvar(com_alfa(im, alfa_de_branco(im, 8, 60)), 'jojo', 'gogogo', 420)


def lanca():
    l = Image.open(os.path.join(REFS, 'eva', 'lanca_longinus.png')).convert('RGBA')
    rgb = l.convert('RGB')
    alfa = np.asarray(l.getchannel('A')).astype(np.float32) / 255
    if alfa.min() > 0.99:
        alfa = alfa_de_branco(rgb, 18, 40)
    l = com_alfa(rgb, alfa)
    ys, xs = np.nonzero(alfa > .3)
    vals, vecs = np.linalg.eigh(np.cov(np.vstack([xs, ys])))
    ang = np.degrees(np.arctan2(vecs[1, 1], vecs[0, 1]))
    girada = l.rotate(ang, expand=True, resample=Image.BICUBIC)            # na horizontal, com o GARFO (a ponta larga) à direita
    a2 = np.asarray(girada.getchannel('A')).astype(np.float32) / 255
    cols = np.nonzero((a2 > .3).any(axis=0))[0]
    esq, dir_ = cols[0], cols[-1]
    n = max(8, (dir_ - esq) // 8)
    if (a2[:, esq:esq + n] > .3).any(axis=1).sum() > (a2[:, dir_ - n:dir_] > .3).any(axis=1).sum():
        girada = girada.rotate(180, expand=True)
    salvar(girada, 'eva', 'lanca', 700)
    # versão pra pin/ícone: a lança na diagonal (ponta pra cima à direita) dentro de um quadrado transparente
    diag = girada.rotate(45, expand=True, resample=Image.BICUBIC)
    caixa = diag.getchannel('A').point(lambda v: 255 if v > 8 else 0).getbbox()
    if caixa:
        diag = diag.crop(caixa)
    lado = max(diag.size)
    quadro = Image.new('RGBA', (lado, lado), (0, 0, 0, 0))
    quadro.paste(diag, ((lado - diag.width) // 2, (lado - diag.height) // 2), diag)
    salvar(quadro, 'eva', 'lanca_pin', 160)


if __name__ == '__main__':
    gogogo()
    lanca()
