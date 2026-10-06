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
  reiniciar: () => ipcRenderer.invoke('sistema:reiniciar'),
});
