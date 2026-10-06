const $ = (id) => document.getElementById(id);
const params = new URLSearchParams(location.search);
if (params.get('erro')) $('erro').hidden = false;

let esperandoLogin = false;
let tentativas = 0;

function mostrarBotao() {
  $('barra').hidden = true;
  $('btn-entrar').hidden = false;
  $('nota').hidden = false;
  $('msg').textContent = 'Chat, mapa e eventos. Entre com a sua conta do Google.';
}

async function conectar() {
  const info = await window.panteao.info();
  $('rodape').textContent = 'v' + info.versao;
  for (;;) {
    if (await window.panteao.ping()) break;
    tentativas++;
    // O servidor gratuito dorme; depois de alguns segundos a gente avisa em vez de parecer travado.
    $('msg').textContent = tentativas < 3
      ? 'Conectando ao servidor…'
      : 'Acordando o servidor… isso pode levar até um minuto na primeira vez.';
    await new Promise((r) => setTimeout(r, 3000));
  }
  // ?sem=1: o servidor acabou de recusar a sessão (logout/expirou). O cookie existir não prova nada.
  if (info.temSessao && !params.get('sem')) {
    $('msg').textContent = 'Entrando…';
    window.panteao.abrirChat();
  } else {
    mostrarBotao();
  }
}

$('btn-entrar').addEventListener('click', async () => {
  await window.panteao.entrarComGoogle();
  esperandoLogin = true;
  $('erro').hidden = true;
  $('btn-entrar').hidden = true;
  $('nota').hidden = true;
  $('barra').hidden = false;
  $('msg').textContent = 'Termine o login no navegador. Esta janela entra sozinha quando você voltar.';
  // se a pessoa fechar a aba sem concluir, deixa tentar de novo
  setTimeout(() => { if (esperandoLogin) { $('btn-entrar').hidden = false; $('nota').hidden = false; $('barra').hidden = true; $('msg').textContent = 'Não terminou o login? Clique de novo para tentar.'; } }, 120000);
});

conectar().catch(() => { $('msg').textContent = 'Não consegui iniciar. Feche e abra o app de novo.'; });
