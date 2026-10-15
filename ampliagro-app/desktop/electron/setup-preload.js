'use strict';

const { contextBridge, ipcRenderer } = require('electron');

// Esta ponte só é carregada no arquivo local do assistente, nunca no site.
contextBridge.exposeInMainWorld(
  'ampliagroSetup',
  Object.freeze({
    read: () => ipcRenderer.invoke('setup:read'),
    save: (selection) => ipcRenderer.invoke('setup:save', selection),
    open: () => ipcRenderer.invoke('setup:open'),
  })
);
