// Ponte mínima entre as telas locais (login/seletor) e o processo principal.
// O main confere que a chamada veio de uma página file:// — o site remoto, mesmo que
// chame isso, não consegue iniciar login nem ver as fontes de captura.
const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('panteao', {
  info: () => ipcRenderer.invoke('app:info'),
  ping: () => ipcRenderer.invoke('app:ping'),
  abrirChat: () => ipcRenderer.invoke('app:abrir-chat'),
  entrarComGoogle: () => ipcRenderer.invoke('login:iniciar'),
  fontesDeTela: () => ipcRenderer.invoke('seletor:fontes'),
  escolherFonte: (id) => ipcRenderer.send('seletor:escolher', id),
});
