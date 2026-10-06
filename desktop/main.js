// Casca desktop do Panteão: uma janela que carrega o site, mais o que o navegador não faz
// (login pelo navegador do sistema, tray, captura de tela, auto-update). Nada do chat.html mora aqui.
const {
  app, BrowserWindow, Tray, Menu, shell, ipcMain, session, desktopCapturer, nativeImage, net, dialog,
} = require('electron');
const path = require('path');
const fs = require('fs');
const crypto = require('crypto');

// ---------------------------------------------------------------- configuração
function lerConfig() {
  let cfg = {};
  try { cfg = JSON.parse(fs.readFileSync(path.join(__dirname, 'config.json'), 'utf8')); } catch (_) {}
  const servidor = (process.env.PANTEAO_URL || cfg.servidor || 'http://localhost:5000').replace(/\/+$/, '');
  // Chave da Geolocation API do Google (opcional). Vai dentro do instalador, então precisa ser RESTRITA à
  // Geolocation API no Google Cloud (ver CLAUDE.md, Rodada 7). Pode vir de config.json ou da variável GOOGLE_API_KEY.
  const googleApiKey = String(process.env.GOOGLE_API_KEY || cfg.googleApiKey || '').trim();
  return { servidor, googleApiKey };
}
const { servidor: SERVIDOR, googleApiKey: CHAVE_GOOGLE } = lerConfig();
console.log(`[desktop] servidor: ${SERVIDOR}${process.env.PANTEAO_URL ? ' (vem da variável PANTEAO_URL)' : ''}`);
const ORIGEM = new URL(SERVIDOR).origin;
const PROTOCOLO = 'panteao';

let janela = null;
let tray = null;
let atualizarMenuTray = () => {};
let saindo = false;
let verificadorPendente = null;   // PKCE: o hash vai pro navegador, o original fica só aqui

// ---------------------------------------------------------------- preferências DESTE aparelho (Configurações > Geral)
// Ficam num arquivo em userData, não na conta: "iniciar com o Windows" e "como achar a localização" mudam de PC pra PC.
// Windows/Google são lidos ANTES do app ficar pronto (flag do Chromium / variável de ambiente), então mudar exige reiniciar.
const PREFS_PADRAO = { fecharNaBandeja: true, locWindows: true, locGoogle: true };
const arquivoPrefs = () => path.join(app.getPath('userData'), 'prefs.json');

function lerPrefs() {
  try { return { ...PREFS_PADRAO, ...JSON.parse(fs.readFileSync(arquivoPrefs(), 'utf8')) }; } catch (_) { return { ...PREFS_PADRAO }; }
}
function gravarPrefs(p) {
  try { fs.writeFileSync(arquivoPrefs(), JSON.stringify(p)); } catch (err) { console.warn('[prefs]', err.message); }
}
let prefs = lerPrefs();
let precisaReiniciar = false;

// Geolocalização: o Electron não tem o provedor de rede do Google de graça (exige chave de API), então sem nenhum dos
// dois abaixo navigator.geolocation estoura o tempo (code 3) e o app cai na reserva por IP.
//  - Windows: usa o serviço de localização do sistema; só funciona com o serviço "Geolocalização" (lfsvc) ativo.
//  - Google: com a chave, o Chromium consulta o Google com os Wi-Fi ao redor (a variável precisa existir antes do ready).
if (prefs.locWindows) app.commandLine.appendSwitch('enable-features', 'WinrtGeolocationImplementation');
if (prefs.locGoogle && CHAVE_GOOGLE) process.env.GOOGLE_API_KEY = CHAVE_GOOGLE;

// ---------------------------------------------------------------- instância única + deep link
if (process.defaultApp && process.argv.length >= 2) {
  app.setAsDefaultProtocolClient(PROTOCOLO, process.execPath, [path.resolve(process.argv[1])]);
} else {
  app.setAsDefaultProtocolClient(PROTOCOLO);
}

if (!app.requestSingleInstanceLock()) {
  app.quit();
} else {
  app.on('second-instance', (_e, argv) => {
    mostrarJanela();
    const link = argv.find((a) => a.startsWith(PROTOCOLO + '://'));
    if (link) tratarLink(link);
  });
}

function tratarLink(url) {
  let u;
  try { u = new URL(url); } catch (_) { return; }
  if (u.protocol !== PROTOCOLO + ':' || u.hostname !== 'auth') return;
  const codigo = u.searchParams.get('codigo') || '';
  if (!/^[A-Za-z0-9_-]{20,80}$/.test(codigo)) return;
  if (!verificadorPendente) return;            // ninguém pediu login: ignora link solto
  const verificador = verificadorPendente;
  verificadorPendente = null;                  // uso único
  mostrarJanela();
  janela.loadURL(`${SERVIDOR}/auth/desktop/trocar?codigo=${encodeURIComponent(codigo)}&verificador=${verificador}`);
}

// ---------------------------------------------------------------- janela
const arquivoEstado = () => path.join(app.getPath('userData'), 'janela.json');

function lerEstadoJanela() {
  try { return JSON.parse(fs.readFileSync(arquivoEstado(), 'utf8')); } catch (_) { return {}; }
}

function guardarEstadoJanela() {
  if (!janela || janela.isDestroyed()) return;
  try {
    const maxim = janela.isMaximized();
    const b = maxim ? (lerEstadoJanela().bounds || janela.getBounds()) : janela.getBounds();
    fs.writeFileSync(arquivoEstado(), JSON.stringify({ bounds: b, maximizada: maxim }));
  } catch (_) {}
}

function mostrarLogin(extra = {}) {
  const query = {};
  if (extra.erro) query.erro = '1';
  if (extra.semSessao) query.sem = '1';   // o servidor acabou de recusar a sessão: não tentar entrar sozinho de novo
  janela.loadFile(path.join(__dirname, 'login.html'), { query });
}

function criarJanela() {
  const est = lerEstadoJanela();
  janela = new BrowserWindow({
    width: 1280, height: 800, minWidth: 900, minHeight: 600,
    ...(est.bounds || {}),
    backgroundColor: '#0b0c10',
    title: 'Panteão',
    icon: path.join(__dirname, 'assets', 'tray.png'),
    autoHideMenuBar: true,
    show: false,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      webSecurity: true,
    },
  });
  if (est.maximizada) janela.maximize();
  janela.removeMenu();
  janela.once('ready-to-show', () => janela.show());

  janela.on('resize', guardarEstadoJanela);
  janela.on('move', guardarEstadoJanela);
  // Fechar = esconder na bandeja (como o Discord); "Sair" no menu da bandeja encerra de verdade.
  janela.on('close', (e) => {
    if (saindo) return;
    if (prefs.fecharNaBandeja) { e.preventDefault(); janela.hide(); }
    else { saindo = true; app.quit(); }   // opção "Fechar a janela deixa o app na bandeja" desligada
  });

  // Links externos abrem no navegador do sistema; o app só navega dentro do próprio site.
  janela.webContents.setWindowOpenHandler(({ url }) => {
    abrirNoNavegador(url);
    return { action: 'deny' };
  });
  janela.webContents.on('will-navigate', (e, url) => {
    if (url.startsWith('file://') || new URL(url).origin === ORIGEM) return;
    e.preventDefault();
    abrirNoNavegador(url);
  });
  // Sessão inválida / logout: o servidor redireciona pra /entrar (ou /). Aqui isso vira a tela de login local.
  janela.webContents.on('will-redirect', (e, url) => {
    let u; try { u = new URL(url); } catch (_) { return; }
    if (u.origin === ORIGEM && (u.pathname === '/entrar' || u.pathname === '/')) {
      e.preventDefault();
      mostrarLogin({ erro: /desktop\/trocar/.test(janela.webContents.getURL()), semSessao: true });
    }
  });
  // Servidor fora do ar / sem internet: a tela local mostra o estado e tenta de novo.
  janela.webContents.on('did-fail-load', (_e, codigo, _desc, url, principal) => {
    if (principal && codigo !== -3 && url.startsWith(ORIGEM)) mostrarLogin();
  });

  // Renderer que morre deixa a janela em branco pra sempre: loga o motivo e recarrega a tela local.
  const quedas = [];
  janela.webContents.on('render-process-gone', (_e, d) => {
    console.error('[renderer caiu]', d.reason, d.exitCode);
    if (d.reason === 'clean-exit') return;
    const agora = Date.now();
    quedas.push(agora);
    while (quedas.length && agora - quedas[0] > 30000) quedas.shift();
    if (quedas.length >= 3) {      // caiu 3x em 30s: recarregar de novo só faria um loop
      dialog.showErrorBox('Panteão', 'A janela travou várias vezes seguidas. Feche e abra o app de novo; se continuar, avise o suporte.');
      return;
    }
    mostrarLogin();
  });

  mostrarLogin();
}

function mostrarJanela() {
  if (!janela || janela.isDestroyed()) criarJanela();
  if (janela.isMinimized()) janela.restore();
  janela.show();
  janela.focus();
}

function abrirNoNavegador(url) {
  try {
    const u = new URL(url);
    if (u.protocol === 'http:' || u.protocol === 'https:') shell.openExternal(url);
  } catch (_) {}
}

// ---------------------------------------------------------------- IPC (só a tela local confia)
function vemDaTelaLocal(e) {
  const url = e.senderFrame ? e.senderFrame.url : '';
  return url.startsWith('file://');
}

// As telas de Configurações do SITE também chamam isto (window.panteao.prefs*): vale pra página do próprio servidor do app.
function vemDoApp(e) {
  const url = e.senderFrame ? e.senderFrame.url : '';
  if (url.startsWith('file://')) return true;
  try { return new URL(url).origin === ORIGEM; } catch (_) { return false; }
}

function estadoPrefs() {
  return {
    iniciarComWindows: app.getLoginItemSettings().openAtLogin,
    fecharNaBandeja: prefs.fecharNaBandeja,
    locWindows: prefs.locWindows,
    locGoogle: prefs.locGoogle,
    temChaveGoogle: !!CHAVE_GOOGLE,
    precisaReiniciar,
    versao: app.getVersion(),
  };
}

ipcMain.handle('prefs:get', (e) => (vemDoApp(e) ? estadoPrefs() : null));

ipcMain.handle('prefs:set', (e, chave, valor) => {
  if (!vemDoApp(e) || typeof valor !== 'boolean') return null;
  if (chave === 'iniciarComWindows') {
    // em desenvolvimento isso registraria o electron.exe puro (abriria a tela padrão do Electron no boot)
    if (!app.isPackaged) return { ...estadoPrefs(), aviso: 'Só funciona no app instalado (não no npm start).' };
    app.setLoginItemSettings({ openAtLogin: valor });
    atualizarMenuTray();
  } else if (chave === 'fecharNaBandeja') {
    prefs.fecharNaBandeja = valor;
    gravarPrefs(prefs);
  } else if (chave === 'locWindows' || chave === 'locGoogle') {
    prefs[chave] = valor;
    gravarPrefs(prefs);
    precisaReiniciar = true;     // flag/variável do Chromium só valem na próxima abertura
  }
  return estadoPrefs();
});

ipcMain.handle('sistema:abrir-privacidade-localizacao', (e) => {
  if (!vemDoApp(e)) return;
  shell.openExternal('ms-settings:privacy-location');   // texto fixo: nada vindo da página entra aqui
});

ipcMain.handle('sistema:reiniciar', (e) => {
  if (!vemDoApp(e)) return;
  saindo = true;
  app.relaunch();
  app.exit(0);
});

ipcMain.handle('app:info', async (e) => {
  if (!vemDaTelaLocal(e)) return null;
  const cookies = await session.defaultSession.cookies.get({ url: SERVIDOR, name: 'session' });
  return { servidor: SERVIDOR, versao: app.getVersion(), temSessao: cookies.length > 0 };
});

ipcMain.handle('app:ping', async (e) => {
  if (!vemDaTelaLocal(e)) return false;
  try {
    // manifesto: leve, sem banco, então responde mesmo com o Neon dormindo
    // timeout: servidor acordando pode segurar a requisição por um minuto; sem isso o laço da tela trava nela
    const r = await net.fetch(`${SERVIDOR}/manifest.webmanifest`, {
      method: 'GET', cache: 'no-store', signal: AbortSignal.timeout(8000),
    });
    return r.ok;
  } catch (err) {
    console.warn('[ping]', err && err.message);
    return false;
  }
});

ipcMain.handle('app:abrir-chat', (e) => {
  if (!vemDaTelaLocal(e)) return;
  janela.loadURL(`${SERVIDOR}/chat`);
});

ipcMain.handle('login:iniciar', (e) => {
  if (!vemDaTelaLocal(e)) return false;
  verificadorPendente = crypto.randomBytes(24).toString('hex');
  const desafio = crypto.createHash('sha256').update(verificadorPendente).digest('hex');
  shell.openExternal(`${SERVIDOR}/entrar?desktop=1&desafio=${desafio}`);
  return true;
});

// ---------------------------------------------------------------- permissões e captura de tela
function configurarSessao() {
  const ses = session.defaultSession;
  ses.setUserAgent(`${ses.getUserAgent()} PanteaoDesktop/${app.getVersion()}`);
  // O service worker do site é só pro PWA no navegador. Aqui o Cache Storage derrubava o renderer
  // (Electron 44: "bad Mojo message ... CacheStorageCache"), e o cache HTTP do Chromium já cobre o estático.
  // Limpa o que uma versão anterior possa ter instalado.
  ses.clearStorageData({ storages: ['serviceworkers', 'cachestorage'] }).catch(() => {});

  const liberadas = new Set(['media', 'notifications', 'geolocation', 'clipboard-sanitized-write', 'fullscreen', 'display-capture']);
  const origemOk = (url) => { try { return new URL(url).origin === ORIGEM; } catch (_) { return false; } };
  ses.setPermissionRequestHandler((wc, permissao, ok, detalhes) => {
    ok(liberadas.has(permissao) && origemOk(detalhes.requestingUrl || wc.getURL()));
  });
  ses.setPermissionCheckHandler((_wc, permissao, origem) => liberadas.has(permissao) && origemOk(origem));

  // Sem isso o botão de compartilhar tela falha em silêncio no Electron.
  ses.setDisplayMediaRequestHandler(async (_req, responder) => {
    try {
      const fontes = await desktopCapturer.getSources({ types: ['screen', 'window'], thumbnailSize: { width: 320, height: 180 } });
      const escolhida = await escolherFonte(fontes);
      if (!escolhida) return responder({});          // cancelou
      responder({ video: escolhida, audio: 'loopback' });
    } catch (_) { responder({}); }
  });
}

let seletorAberto = null;
function escolherFonte(fontes) {
  return new Promise((resolve) => {
    const pai = janela && !janela.isDestroyed() ? janela : undefined;
    const sel = new BrowserWindow({
      width: 720, height: 520, parent: pai, modal: !!pai, resizable: false, minimizable: false,
      title: 'Compartilhar tela', autoHideMenuBar: true, backgroundColor: '#16171d',
      webPreferences: { preload: path.join(__dirname, 'preload.js'), contextIsolation: true, sandbox: true },
    });
    sel.removeMenu();
    seletorAberto = { fontes, resolve, janela: sel };
    sel.on('closed', () => { if (seletorAberto) { const r = seletorAberto.resolve; seletorAberto = null; r(null); } });
    sel.loadFile(path.join(__dirname, 'seletor.html'));
  });
}

ipcMain.handle('seletor:fontes', (e) => {
  if (!vemDaTelaLocal(e) || !seletorAberto) return [];
  return seletorAberto.fontes.map((f) => ({ id: f.id, nome: f.name, miniatura: f.thumbnail.toDataURL() }));
});

ipcMain.on('seletor:escolher', (e, id) => {
  if (!vemDaTelaLocal(e) || !seletorAberto) return;
  const { fontes, resolve, janela: sel } = seletorAberto;
  seletorAberto = null;
  resolve(typeof id === 'string' ? fontes.find((f) => f.id === id) || null : null);
  if (!sel.isDestroyed()) sel.close();
});

// ---------------------------------------------------------------- bandeja
function criarTray() {
  const icone = nativeImage.createFromPath(path.join(__dirname, 'assets', 'tray.png')).resize({ width: 16, height: 16 });
  tray = new Tray(icone);
  tray.setToolTip('Panteão');
  atualizarMenuTray = () => tray.setContextMenu(montarMenuTray());
  const montarMenuTray = () => Menu.buildFromTemplate([
    { label: 'Abrir Panteão', click: mostrarJanela },
    ...(atualizacaoBaixada ? [{ label: 'Reiniciar pra atualizar', click: instalarAtualizacao }] : []),
    ...(autoUpdater ? [{ label: 'Procurar atualizações', click: procurarAtualizacao }] : []),
    {
      label: 'Iniciar com o Windows', type: 'checkbox',
      checked: app.getLoginItemSettings().openAtLogin,
      click: (item) => app.setLoginItemSettings({ openAtLogin: item.checked }),
    },
    { type: 'separator' },
    { label: 'Sair', click: () => { saindo = true; app.quit(); } },
  ]);
  tray.setContextMenu(montarMenuTray());
  tray.on('click', mostrarJanela);
  tray.on('right-click', atualizarMenuTray);   // reflete o estado atual do "iniciar com o Windows"
}

// ---------------------------------------------------------------- atualização da casca
// Os instaladores ficam num repositório PÚBLICO só de binários (o código do app é privado).
// Ver "publish" no package.json e o passo a passo em CLAUDE.md (Rodada 7).
let autoUpdater = null;
let atualizacaoBaixada = false;

function iniciarAtualizador() {
  if (!app.isPackaged) return;     // em desenvolvimento não existe release pra baixar
  try {
    ({ autoUpdater } = require('electron-updater'));
  } catch (err) { console.warn('[updater] indisponível:', err.message); return; }

  autoUpdater.autoDownload = true;
  autoUpdater.autoInstallOnAppQuit = true;      // o app vive na bandeja: quem fecha de verdade já instala
  autoUpdater.on('checking-for-update', () => mudarEstadoAtualizacao({ fase: 'procurando' }));
  autoUpdater.on('update-available', (info) => mudarEstadoAtualizacao({ fase: 'baixando', versao: info.version, percentual: 0 }));
  autoUpdater.on('update-not-available', () => mudarEstadoAtualizacao({ fase: 'atualizado', versao: null }));
  autoUpdater.on('download-progress', (p) => mudarEstadoAtualizacao({ fase: 'baixando', percentual: Math.round(p.percent || 0) }));
  autoUpdater.on('error', (err) => {
    console.warn('[updater]', err && err.message);
    // erro de rede ao procurar não vira aviso na cara da pessoa; só conta se estava baixando
    if (estadoAtualizacao.fase === 'baixando') mudarEstadoAtualizacao({ fase: 'erro' });
    else mudarEstadoAtualizacao({ fase: 'atualizado' });
  });
  autoUpdater.on('update-downloaded', (info) => {
    atualizacaoBaixada = true;
    mudarEstadoAtualizacao({ fase: 'pronta', versao: info.version, percentual: 100 });
    // O indicador dentro do app (a pílula) cuida de quem está olhando. Janela escondida na bandeja não tem
    // quem veja a pílula: aí vale a janelinha do sistema.
    if (!janela || janela.isDestroyed() || !janela.isVisible() || janela.isMinimized()) {
      dialog.showMessageBox({
        type: 'info', buttons: ['Reiniciar agora', 'Depois'], defaultId: 0, cancelId: 1,
        title: 'Atualização pronta',
        message: `O Panteão ${info.version} foi baixado.`,
        detail: 'Reinicie pra usar a versão nova. Se escolher "Depois", ela é instalada quando você sair do app.',
      }).then((r) => { if (r.response === 0) instalarAtualizacao(); });
    }
  });
  procurarAtualizacao();
  setInterval(procurarAtualizacao, 4 * 60 * 60 * 1000);   // o app fica aberto dias na bandeja
}

// Estado da atualização da casca, mostrado dentro do app (pílula) e na aba Geral. Fases:
// 'nenhuma' (ainda não procurou) | 'procurando' | 'atualizado' | 'baixando' | 'pronta' | 'erro' | 'dev' (npm start)
let estadoAtualizacao = { fase: 'nenhuma', versao: null, percentual: 0 };

function mudarEstadoAtualizacao(parcial) {
  estadoAtualizacao = { ...estadoAtualizacao, ...parcial };
  if (estadoAtualizacao.fase !== 'baixando' && estadoAtualizacao.fase !== 'pronta') estadoAtualizacao.percentual = 0;
  if (tray) tray.setToolTip(estadoAtualizacao.fase === 'pronta' ? `Panteão: atualização ${estadoAtualizacao.versao} pronta`
    : estadoAtualizacao.fase === 'baixando' ? `Panteão: baixando atualização ${estadoAtualizacao.percentual}%` : 'Panteão');
  atualizarMenuTray();
  if (janela && !janela.isDestroyed()) janela.webContents.send('atualizacao:estado', estadoAtualizacao);
}

function instalarAtualizacao() {
  if (!autoUpdater || !atualizacaoBaixada) return;
  saindo = true;
  autoUpdater.quitAndInstall();
}

ipcMain.handle('atualizacao:get', (e) => (vemDoApp(e) ? (app.isPackaged ? estadoAtualizacao : { fase: 'dev' }) : null));
ipcMain.handle('atualizacao:instalar', (e) => { if (vemDoApp(e)) instalarAtualizacao(); });
ipcMain.handle('atualizacao:procurar', (e) => {
  if (!vemDoApp(e)) return null;
  if (!app.isPackaged) return { fase: 'dev' };
  if (estadoAtualizacao.fase !== 'baixando' && estadoAtualizacao.fase !== 'pronta') procurarAtualizacao();
  return estadoAtualizacao;
});

function procurarAtualizacao() {
  if (!autoUpdater) return;
  autoUpdater.checkForUpdates().catch((err) => console.warn('[updater]', err && err.message));
}

// ---------------------------------------------------------------- ciclo de vida
app.on('before-quit', () => { saindo = true; });
app.on('child-process-gone', (_e, d) => console.error('[processo filho caiu]', d.type, d.reason, d.exitCode));

app.whenReady().then(() => {
  configurarSessao();
  criarJanela();
  criarTray();
  const link = process.argv.find((a) => a.startsWith(PROTOCOLO + '://'));
  if (link) tratarLink(link);
  iniciarAtualizador();
  app.on('activate', mostrarJanela);
});

// Mantém vivo na bandeja quando a janela some (só "Sair" encerra).
app.on('window-all-closed', () => {});
