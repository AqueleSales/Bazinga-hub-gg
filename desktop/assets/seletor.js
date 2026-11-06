// Seletor de tela do app: abas Telas (monitores) e Janelas, busca, miniaturas que se atualizam sozinhas.
// Só desenha com textContent/atributos (nunca innerHTML com o nome de uma janela: o título de uma janela é texto de terceiros).
let fontes = [], aba = 'tela', busca = '';
const grade = document.getElementById('grade');
const sinalizar = () => window.panteao.escolherFonte(null);
document.getElementById('cancelar').onclick = sinalizar;
window.addEventListener('keydown', (e) => { if (e.key === 'Escape') sinalizar(); });

function desenhar() {
  const lista = fontes.filter((f) => f.tipo === aba && (!busca || f.nome.toLowerCase().includes(busca)));
  document.querySelectorAll('[data-aba]').forEach((b) => {
    const n = fontes.filter((f) => f.tipo === b.dataset.aba).length;
    b.classList.toggle('on', b.dataset.aba === aba);
    b.querySelector('small').textContent = n ? String(n) : '';
  });
  document.getElementById('busca').style.display = aba === 'janela' ? '' : 'none';
  // reaproveita os botões já na tela (só troca a miniatura): nada de piscar a cada atualização
  const existentes = new Map([...grade.children].map((b) => [b.dataset.id, b]));
  const ordem = [];
  for (const f of lista) {
    let b = existentes.get(f.id);
    if (!b) {
      b = document.createElement('button'); b.className = 'fonte'; b.dataset.id = f.id;
      const img = document.createElement('img'); img.alt = '';
      const linha = document.createElement('div'); linha.className = 'linha';
      const ic = document.createElement('img'); ic.className = 'ic'; ic.alt = '';
      const nome = document.createElement('span');
      linha.append(ic, nome); b.append(img, linha);
      b.onclick = () => window.panteao.escolherFonte(f.id);
    }
    b.querySelector('img').src = f.miniatura;
    const ic = b.querySelector('.ic'); if (f.icone) { ic.src = f.icone; ic.style.display = ''; } else ic.style.display = 'none';
    b.querySelector('span').textContent = f.nome; b.title = f.nome;
    ordem.push(b); existentes.delete(f.id);
  }
  existentes.forEach((b) => b.remove());
  ordem.forEach((b) => grade.appendChild(b));
  document.getElementById('vazio').style.display = lista.length ? 'none' : '';
  document.getElementById('vazio').textContent = aba === 'tela' ? 'Nenhum monitor encontrado.' : (busca ? 'Nenhuma janela com esse nome.' : 'Nenhuma janela aberta.');
}
document.querySelectorAll('[data-aba]').forEach((b) => { b.onclick = () => { aba = b.dataset.aba; desenhar(); }; });
document.getElementById('busca').oninput = (e) => { busca = e.target.value.trim().toLowerCase(); desenhar(); };

window.panteao.fontesDeTela().then((f) => {
  fontes = f || [];
  // só tem janelas e nenhuma tela? começa por elas
  if (!fontes.some((x) => x.tipo === 'tela') && fontes.some((x) => x.tipo === 'janela')) aba = 'janela';
  desenhar();
});
setInterval(() => { window.panteao.atualizarFontes().then((f) => { if (f && f.length) { fontes = f; desenhar(); } }).catch(() => {}); }, 2500);
