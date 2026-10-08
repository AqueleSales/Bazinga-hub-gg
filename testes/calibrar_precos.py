"""Calibra os preços do Armazém: quanto DRC cada perfil de uso junta por dia, e em quantos dias compra cada faixa de preço.

    python testes/calibrar_precos.py        # sai com código 1 se alguma "regra de ouro" abaixo quebrar

NÃO é um teste de banco: é uma conta em cima das constantes reais de `app/utils.py` (XP por mensagem, tempo ativo, bônus diário,
missões, curva de nível e moedas por nível) e dos preços de `app/cosmeticos.py` (`PRECOS`). Rode de novo sempre que mudar uma dessas coisas.
Os perfis (casual/regular/intenso) são SUPOSIÇÕES de uso, não medição: troque por números reais quando houver (ver BACKLOG).
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from app import utils as u
from app import cosmeticos as cos

SALDO_INICIAL = 500            # Person.bazinga_coins nasce com 500
DIAS = 90

# o que cada perfil faz num DIA em que abre o app. `dias_semana` = quantos dias por semana ele aparece.
PERFIS = {
    'casual':  dict(dias_semana=4, mensagem=10,  minutos=15, call_minutos=0,  dm=2,  reacao=3,  nota=0, plantar=0),
    'regular': dict(dias_semana=6, mensagem=40,  minutos=45, call_minutos=10, dm=8,  reacao=8,  nota=1, plantar=0),
    'intenso': dict(dias_semana=7, mensagem=120, minutos=60, call_minutos=30, dm=25, reacao=25, nota=1, plantar=1),
}


def _cumpre(p, m, dias_na_semana=1):
    """O perfil consegue cumprir a missão `m`? (diária: num dia; semanal: somando os dias ativos da semana)."""
    if m['evento'] == 'login':
        return dias_na_semana >= m['meta']
    return p.get(m['evento'], 0) * dias_na_semana >= m['meta']


def missoes_do_dia(p, dias_ativos_na_semana, xp_por_missao=True, drc_diaria=0, drc_semanal=0):
    """Esperado por dia ativo: média sobre o pool (cada pessoa recebe 3 sorteadas de N), contando só as missões que o perfil CONSEGUE cumprir.
    Devolve (xp, drc)."""
    dia = [m for m in u.MISSOES.values() if m['periodo'] == 'diaria']
    sem = [m for m in u.MISSOES.values() if m['periodo'] == 'semanal']
    k = u.QTD_POR_PERIODO
    xp = k * sum(m['xp'] for m in dia if _cumpre(p, m)) / len(dia) + k * sum(m['xp'] for m in sem if _cumpre(p, m, dias_ativos_na_semana)) / len(sem) / max(dias_ativos_na_semana, 1)
    drc = k * sum(1 for m in dia if _cumpre(p, m)) / len(dia) * drc_diaria + k * sum(1 for m in sem if _cumpre(p, m, dias_ativos_na_semana)) / len(sem) / max(dias_ativos_na_semana, 1) * drc_semanal
    return xp, drc


def simular(p, drc_missao=None):
    """`drc_missao` = (DRC por diária, DRC por semanal); sem ele vale o que o app paga de verdade (`DRC_POR_MISSAO`)."""
    if drc_missao is None:
        drc_missao = (u.DRC_POR_MISSAO['diaria'], u.DRC_POR_MISSAO['semanal'])
    xp, drc, seq, linhas = 0, float(SALDO_INICIAL), 0, []
    ativos = p['dias_semana']
    m_xp, m_drc = missoes_do_dia(p, ativos, drc_diaria=drc_missao[0], drc_semanal=drc_missao[1])
    for dia in range(1, DIAS + 1):
        if ((dia - 1) % 7) < ativos:                       # abre o app (os dias ativos vêm no começo da semana: simplificação)
            seq = seq + 1 if ((dia - 1) % 7) else 1
            ganho = (p['mensagem'] * u.XP_POR_MENSAGEM + min(p['minutos'], u.MINUTOS_ATIVOS_MAX_POR_DIA) * u.XP_POR_MINUTO_ATIVO
                     + u.XP_BONUS_DIARIO + u.XP_BONUS_SEQUENCIA * (min(seq, u.SEQUENCIA_MAXIMA) - 1) + m_xp)
            antes = u.nivel_da_pessoa(xp)
            xp += ganho
            depois = u.nivel_da_pessoa(xp)
            drc += sum(u.recompensa_do_nivel(n)['coins'] for n in range(antes + 1, depois + 1)) + m_drc
        linhas.append((dia, int(xp), u.nivel_da_pessoa(xp), int(drc)))
    return linhas


def dia_em_que_junta(linhas, valor):
    for dia, _, _, drc in linhas:
        if drc >= valor:
            return dia
    return None


def main():
    pacotes = [d for d in cos.CATALOGO.values() if d.get('pacote_loja')]
    avulsos = [d for d in cos.CATALOGO.values() if d.get('preco') and d['tipo'] != 'pacote']
    # pacote "normal" = os temas de raridade rara (4 itens); pacote "premium" = os temas épicos com efeitos (11 itens)
    pacote = max(d['preco'] for d in pacotes if d['raridade'] == 'raro')
    epico = max(d['preco'] for d in pacotes if d['raridade'] == 'epico')
    barato = min(d['preco'] for d in avulsos) if avulsos else 250
    print(f'Itens avulsos: {sorted({d["preco"] for d in avulsos})} DRC · pacotes: {sorted({d["preco"] for d in pacotes})} DRC ({len(pacotes)} temas)\n')

    dias_mostrados = (1, 3, 7, 14, 30, 60, 90)
    print(f"{'perfil':9}" + ''.join(f'{"dia " + str(d):>14}' for d in dias_mostrados) + '    (nível / DRC acumulado, já com os 500 iniciais)')
    r = {}
    for nome, p in PERFIS.items():
        r[nome] = simular(p)
        print(f'{nome:9}' + ''.join(f'{str(r[nome][d - 1][2]) + " / " + str(r[nome][d - 1][3]):>14}' for d in dias_mostrados))

    print('\nEm quantos DIAS cada perfil junta (sem gastar nada antes) o valor de:')
    degraus = [(f'1 item barato ({barato})', barato), ('2 itens avulsos (900)', 900), (f'1 pacote ({pacote})', pacote), (f'2 pacotes ({2 * pacote})', 2 * pacote), (f'pacote premium ({epico})', epico)]
    print(f"{'':26}" + ''.join(f'{n:>10}' for n in PERFIS))
    for rot, valor in degraus:
        print(f'{rot:26}' + ''.join(f'{(dia_em_que_junta(r[n], valor) or ">90"):>10}' for n in PERFIS))

    print('\nREGRAS DE OURO desta tabela de preços (ajuste `PRECOS` em cosmeticos.py se alguma quebrar):')
    todas = []

    def regra(txt, ok):
        print(f"  [{'OK' if ok else 'REVER'}] {txt}")
        todas.append(ok)

    d_barato = dia_em_que_junta(r['casual'], barato)
    regra(f'1 item barato ({barato}) já no 1º dia pra qualquer um (os {SALDO_INICIAL} iniciais pagam): dia {d_barato}', d_barato == 1)
    d_reg = dia_em_que_junta(r['regular'], pacote)
    regra(f'1º pacote ({pacote}) NÃO no 1º dia pra quem joga normal, e em até 2 semanas: dia {d_reg}', bool(d_reg) and 4 <= d_reg <= 14)
    d_int = dia_em_que_junta(r['intenso'], pacote)
    regra(f'... nem pro intenso antes do dia 3: dia {d_int}', bool(d_int) and d_int >= 3)
    d_cas = dia_em_que_junta(r['casual'], pacote)
    regra(f'... e em até ~2 meses pra quem entra pouco: dia {d_cas or ">90"}', bool(d_cas) and d_cas <= 60)
    d_prem = dia_em_que_junta(r['regular'], epico)
    regra(f'pacote premium ({epico}) não vira rotina: o regular só junta no dia {d_prem or ">90"} (precisa de >= 25: é o prêmio de quem já tem um bom tempo de casa)', d_prem is None or d_prem >= 25)

    print(f'\nColeção completa ({len(pacotes)} pacotes x {pacote} = {len(pacotes) * pacote} DRC), sem gastar em mais nada:')
    for nome in PERFIS:
        tot = r[nome][-1][3]
        print(f'  {nome:8} junta {tot} DRC em {DIAS} dias = {tot // pacote} pacote(s)')

    print('\nO DRC vem dos níveis (que custam cada vez mais XP) E das missões (valor fixo por missão: é o que segura a renda depois do 1º mês).')
    print('Comparativo, DRC no dia 30 / dia 90:')
    print(f"  {'':40}" + ''.join(f'{n:>16}' for n in PERFIS))
    sem_missao = {n: simular(p, (0, 0)) for n, p in PERFIS.items()}
    print(f"  {'só níveis (missão não pagaria DRC)':40}" + ''.join(f'{str(sem_missao[n][29][3]) + " / " + str(sem_missao[n][89][3]):>16}' for n in PERFIS))
    atual = f"{u.DRC_POR_MISSAO['diaria']} DRC/diária + {u.DRC_POR_MISSAO['semanal']} DRC/semanal (HOJE)"
    print(f"  {atual:40}" + ''.join(f'{str(r[n][29][3]) + " / " + str(r[n][89][3]):>16}' for n in PERFIS))
    ls = {n: simular(p, (20, 80)) for n, p in PERFIS.items()}
    print(f"  {'20 DRC/diária + 80 DRC/semanal (se subir)':40}" + ''.join(f'{str(ls[n][29][3]) + " / " + str(ls[n][89][3]):>16}' for n in PERFIS))
    return all(todas)


if __name__ == '__main__':
    sys.exit(0 if main() else 1)
