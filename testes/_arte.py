"""Ajuda dos testes que olham a ARTE dos cosméticos (CSS/JS por texto). Os temas novos vivem em vários arquivos: cosmeticos.css/js, cosm_base.css,
cosm_temas.css/js e um par cosm_<categoria>.css/js GERADO por tools/cosm/gerar.js. Aqui se lê tudo junto, por padrão de nome."""
import glob, json, os, re, shutil, subprocess

RAIZ = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
ESTATICO = os.path.join(RAIZ, 'app', 'static')


def _ler(caminho):
    with open(caminho, encoding='utf-8') as f:
        return f.read()


def css_todo():
    """cosmeticos.css + todo cosm_*.css (base, temas à mão e os gerados)."""
    arqs = [os.path.join(ESTATICO, 'css', 'cosmeticos.css')] + sorted(glob.glob(os.path.join(ESTATICO, 'css', 'cosm_*.css')))
    return '\n'.join(_ler(a) for a in arqs)


def js_temas():
    """cosm_temas.js (os temas feitos à mão: Simbionte...). Os gerados são lidos por ids_registrados_gerados()."""
    return _ler(os.path.join(ESTATICO, 'js', 'cosm_temas.js'))


def js_cosm():
    return _ler(os.path.join(ESTATICO, 'js', 'cosmeticos.js'))


def gerado():
    """O app/cosm_gen.json (temas e itens que o gerador escreveu)."""
    caminho = os.path.join(RAIZ, 'app', 'cosm_gen.json')
    return json.loads(_ler(caminho)) if os.path.isfile(caminho) else {'arquivos': [], 'temas': [], 'itens': []}


def ids_registrados_gerados():
    """{'avatar': {ids}, 'perfil': {ids}, 'fala': {...}, ...} lido dos cosm_<cat>.js gerados (cada um traz um comentário /*IDS {...} */)."""
    saida = {}
    for a in sorted(glob.glob(os.path.join(ESTATICO, 'js', 'cosm_*.js'))):
        m = re.search(r'/\*IDS (\{.*?\}) \*/', _ler(a))
        if not m:
            continue
        for k, v in json.loads(m.group(1)).items():
            saida.setdefault(k, set()).update(v)
    return saida


def gerador_atualizado():
    """None se não dá pra conferir (sem node); senão (True/False, mensagem). Roda `node tools/cosm/gerar.js --check`."""
    node = shutil.which('node')
    if not node:
        return None
    r = subprocess.run([node, os.path.join(RAIZ, 'tools', 'cosm', 'gerar.js'), '--check'], capture_output=True, text=True, cwd=RAIZ)
    return r.returncode == 0, (r.stderr or r.stdout).strip()
