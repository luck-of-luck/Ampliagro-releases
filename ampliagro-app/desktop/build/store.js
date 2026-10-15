'use strict';

// Identidade emitida no Partner Center. Não usar nomes ou certificados fictícios.
const base = require('../package.json').build;
function required(name) {
  const value = process.env[name]?.trim();
  if (!value) throw new Error(`Defina ${name} com o valor da identidade do aplicativo no Partner Center.`);
  return value;
}

module.exports = {
  ...base,
  win: { ...base.win, target: [{ target: 'appx', arch: ['x64'] }] },
  appx: {
    identityName: required('AMPLIAGRO_STORE_IDENTITY'),
    publisher: required('AMPLIAGRO_STORE_PUBLISHER'),
    publisherDisplayName: required('AMPLIAGRO_STORE_PUBLISHER_NAME'),
    applicationId: 'Ampliagro',
    displayName: 'Ampliagro',
    languages: ['pt-BR'],
    backgroundColor: '#109e76',
    addAutoLaunchExtension: false,
  },
};
