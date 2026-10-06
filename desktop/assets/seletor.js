document.getElementById('cancelar').onclick = () => window.panteao.escolherFonte(null);
window.addEventListener('keydown', (e) => { if (e.key === 'Escape') window.panteao.escolherFonte(null); });
window.panteao.fontesDeTela().then((fontes) => {
  const grade = document.getElementById('grade');
  for (const f of fontes) {
    const b = document.createElement('button');
    b.className = 'fonte';
    const img = document.createElement('img'); img.src = f.miniatura;
    const nome = document.createElement('span'); nome.textContent = f.nome;
    b.append(img, nome);
    b.onclick = () => window.panteao.escolherFonte(f.id);
    grade.appendChild(b);
  }
});
