// Ponte mínima entre as telas (login/seletor e o próprio site) e o processo principal.
// O main confere de onde veio cada chamada: login/seletor só de página file://, e as preferências
// também da página do servidor do app. Qualquer outro site recebe null/nada.
const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('panteao', {
  // telas locais
  info: () => ipcRenderer.invoke('app:info'),
  ping: () => ipcRenderer.invoke('app:ping'),
  abrirChat: () => ipcRenderer.invoke('app:abrir-chat'),
  entrarComGoogle: () => ipcRenderer.invoke('login:iniciar'),
  fontesDeTela: () => ipcRenderer.invoke('seletor:fontes'),
  escolherFonte: (id) => ipcRenderer.send('seletor:escolher', id),
  // Configurações > Geral (site)
  prefsGet: () => ipcRenderer.invoke('prefs:get'),
  prefsSet: (chave, valor) => ipcRenderer.invoke('prefs:set', chave, valor),
  abrirPrivacidadeLocalizacao: () => ipcRenderer.invoke('sistema:abrir-privacidade-localizacao'),
  localizacaoPeloNavegador: () => ipcRenderer.invoke('localizacao:navegador'),
  aoChegarLocalizacao: (cb) => {
    const f = (_e, pos) => cb(pos);
    ipcRenderer.on('localizacao:chegou', f);
    return () => ipcRenderer.removeListener('localizacao:chegou', f);
  },
  reiniciar: () => ipcRenderer.invoke('sistema:reiniciar'),
  // atualização do próprio app (instalador): estado, instalar, procurar e ouvir mudanças
  atualizacaoEstado: () => ipcRenderer.invoke('atualizacao:get'),
  atualizacaoInstalar: () => ipcRenderer.invoke('atualizacao:instalar'),
  atualizacaoProcurar: () => ipcRenderer.invoke('atualizacao:procurar'),
  aoMudarAtualizacao: (cb) => {
    const f = (_e, estado) => cb(estado);
    ipcRenderer.on('atualizacao:estado', f);
    return () => ipcRenderer.removeListener('atualizacao:estado', f);
  },
});
