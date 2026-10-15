/**
 * Ampliagro IndexedDB Wrapper - Offline-first data layer
 * Handles: mutations queue, notes, photos, observations, tasks
 *
 * ── SCHEMA DUPLICADO — ver aviso no bloco onupgradeneeded ──────────────────
 * `app/static/js/pwa/sw.js` (openOfflineDB) abre ESTE MESMO banco com a MESMA
 * versão e por isso tem de declarar EXACTAMENTE o mesmo conjunto de object
 * stores com os mesmos indices. Um `onupgradeneeded` só corre quando o banco
 * é criado ou quando a versão SOBE — nunca os dois. Se os dois handlers
 * declarassem conjuntos diferentes, o vencedor seria decidido por qual deles
 * acordasse primeiro (o Service Worker acorda em background sync antes do JS
 * da página), e o Caderno de Campo offline passaria a lancer NotFoundError em
 * `field_notes`/`offline_tasks`/`experiments`/`voice_recordings`.
 *
 * Portanto: as DUAS listas precisam mudar juntas. A de cá é a fonte de
 * verdade dos indices; a do sw.js é a cópia.
 */
const AMPLIA_DB_NAME = 'ampliagro-offline';
const AMPLIA_DB_VERSION = 2;

class OfflineDB {
  constructor() {
    this.db = null;
    this.dbName = AMPLIA_DB_NAME;
    this.version = AMPLIA_DB_VERSION;
  }

  async init() {
    return new Promise((resolve, reject) => {
      // A versão vem da constante, não de um literal repetido aqui: era
      // exactamente essa duplicação que deixou os dois números divergirem
      // sem ninguém dar por isso.
      const request = indexedDB.open(AMPLIA_DB_NAME, AMPLIA_DB_VERSION);

      request.onupgradeneeded = (event) => {
        const db = event.target.result;

        // 7 stores, sempre os mesmos, sempre com estes indices.
        // Cada guarda `contains` torna o upgrade idempotente e impede que um
        // store ja existente (com dados offline do produtor no aparelho) seja
        // apagado ou recriado. NAO remover estas guardas.

        // Mutations queue for background sync
        if (!db.objectStoreNames.contains('mutations')) {
          const store = db.createObjectStore('mutations', { keyPath: 'id', autoIncrement: true });
          store.createIndex('url', 'url', { unique: false });
          store.createIndex('timestamp', 'timestamp', { unique: false });
        }

        // Caderno de Campo notes
        if (!db.objectStoreNames.contains('field_notes')) {
          const store = db.createObjectStore('field_notes', { keyPath: 'id', autoIncrement: true });
          store.createIndex('talhao_id', 'talhao_id', { unique: false });
          store.createIndex('cultura_id', 'cultura_id', { unique: false });
          store.createIndex('created_at', 'created_at', { unique: false });
          store.createIndex('synced', 'synced', { unique: false });
        }

        // Photos
        if (!db.objectStoreNames.contains('photos')) {
          const store = db.createObjectStore('photos', { keyPath: 'id', autoIncrement: true });
          store.createIndex('note_id', 'note_id', { unique: false });
          store.createIndex('synced', 'synced', { unique: false });
        }

        // Observations
        if (!db.objectStoreNames.contains('observations')) {
          const store = db.createObjectStore('observations', {
            keyPath: 'id',
            autoIncrement: true,
          });
          store.createIndex('talhao_id', 'talhao_id', { unique: false });
          store.createIndex('created_at', 'created_at', { unique: false });
          store.createIndex('synced', 'synced', { unique: false });
        }

        // Tasks (for offline task creation)
        if (!db.objectStoreNames.contains('offline_tasks')) {
          const store = db.createObjectStore('offline_tasks', {
            keyPath: 'id',
            autoIncrement: true,
          });
          store.createIndex('talhao_id', 'talhao_id', { unique: false });
          store.createIndex('cargo_alvo', 'cargo_alvo', { unique: false });
          store.createIndex('synced', 'synced', { unique: false });
        }

        // Experiment data (A/B tests)
        if (!db.objectStoreNames.contains('experiments')) {
          const store = db.createObjectStore('experiments', { keyPath: 'id', autoIncrement: true });
          store.createIndex('talhao_a', 'talhao_a', { unique: false });
          store.createIndex('talhao_b', 'talhao_b', { unique: false });
          store.createIndex('status', 'status', { unique: false });
        }

        // Voice recordings metadata
        if (!db.objectStoreNames.contains('voice_recordings')) {
          const store = db.createObjectStore('voice_recordings', {
            keyPath: 'id',
            autoIncrement: true,
          });
          store.createIndex('note_id', 'note_id', { unique: false });
          store.createIndex('synced', 'synced', { unique: false });
        }
      };

      request.onsuccess = () => {
        this.db = request.result;
        resolve(this.db);
      };

      request.onerror = () => reject(request.error);
    });
  }

  getDB() {
    return this.db;
  }

  // Generic CRUD
  async add(storeName, data) {
    const db = await this.ensureDB();
    return new Promise((resolve, reject) => {
      const tx = this.db.transaction(storeName, 'readwrite');
      const store = tx.objectStore(storeName);
      const request = store.add({ ...data, created_at: new Date().toISOString(), synced: false });
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });
  }

  async put(storeName, data) {
    const db = await this.ensureDB();
    return new Promise((resolve, reject) => {
      const tx = this.db.transaction(storeName, 'readwrite');
      const store = tx.objectStore(storeName);
      const request = store.put({ ...data, updated_at: new Date().toISOString() });
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });
  }

  async get(storeName, id) {
    await this.ensureDB();
    return new Promise((resolve, reject) => {
      const tx = this.db.transaction(storeName, 'readonly');
      const store = tx.objectStore(storeName);
      const request = store.get(id);
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });
  }

  async getAll(storeName, indexName = null, indexValue = null) {
    await this.ensureDB();
    return new Promise((resolve, reject) => {
      const tx = this.db.transaction(storeName, 'readonly');
      const store = tx.objectStore(storeName);
      let request;
      if (indexName && indexValue !== null) {
        const index = store.index(indexName);
        request = index.getAll(indexValue);
      } else {
        request = store.getAll();
      }
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });
  }

  async delete(storeName, id) {
    await this.ensureDB();
    return new Promise((resolve, reject) => {
      const tx = this.db.transaction(storeName, 'readwrite');
      const store = tx.objectStore(storeName);
      const request = store.delete(id);
      request.onsuccess = () => resolve(true);
      request.onerror = () => reject(request.error);
    });
  }

  async clear(storeName) {
    await this.ensureDB();
    return new Promise((resolve, reject) => {
      const tx = this.db.transaction(storeName, 'readwrite');
      const store = tx.objectStore(storeName);
      const request = store.clear();
      request.onsuccess = () => resolve(true);
      request.onerror = () => reject(request.error);
    });
  }

  // Specific methods for Caderno de Campo
  async saveFieldNote(note) {
    return this.add('field_notes', {
      ...note,
      synced: false,
      created_at: new Date().toISOString(),
    });
  }

  async getFieldNotes(talhaoId = null, culturaId = null) {
    if (talhaoId) return this.getAll('field_notes', 'talhao_id', talhaoId);
    if (culturaId) return this.getAll('field_notes', 'cultura_id', culturaId);
    return this.getAll('field_notes');
  }

  async markNoteSynced(id) {
    const note = await this.get('field_notes', id);
    if (note) {
      note.synced = true;
      note.synced_at = new Date().toISOString();
      return this.put('field_notes', note);
    }
  }

  async savePhoto(photo) {
    return this.add('photos', {
      ...photo,
      synced: false,
      created_at: new Date().toISOString(),
    });
  }

  async getPhotos(noteId) {
    return this.getAll('photos', 'note_id', noteId);
  }

  async saveObservation(obs) {
    return this.add('observations', {
      ...obs,
      synced: false,
      created_at: new Date().toISOString(),
    });
  }

  async getObservations(talhaoId) {
    return this.getAll('observations', 'talhao_id', talhaoId);
  }

  async saveTask(task) {
    return this.add('offline_tasks', {
      ...task,
      synced: false,
      created_at: new Date().toISOString(),
    });
  }

  async getTasks(talhaoId = null, cargoAlvo = null) {
    if (talhaoId) return this.getAll('offline_tasks', 'talhao_id', talhaoId);
    if (cargoAlvo) return this.getAll('offline_tasks', 'cargo_alvo', cargoAlvo);
    return this.getAll('offline_tasks');
  }

  async saveExperiment(exp) {
    return this.add('experiments', {
      ...exp,
      created_at: new Date().toISOString(),
    });
  }

  async getExperiments(talhaoA = null, talhaoB = null) {
    // Simplified - in production would use compound index
    const all = await this.getAll('experiments');
    return all.filter(
      (e) => (!talhaoA || e.talhao_a === talhaoA) && (!talhaoB || e.talhao_b === talhaoB)
    );
  }

  async saveVoiceRecording(rec) {
    return this.add('voice_recordings', {
      ...rec,
      synced: false,
      created_at: new Date().toISOString(),
    });
  }

  // Get all pending mutations for sync
  async getPendingMutations() {
    return this.getAll('mutations');
  }

  async addMutation(mutation) {
    return this.add('mutations', {
      ...mutation,
      timestamp: Date.now(),
    });
  }

  async removeMutation(id) {
    return this.delete('mutations', id);
  }

  // Queue a mutation for background sync
  async queueMutation(url, method, headers, body) {
    return this.addMutation({
      url,
      method,
      headers,
      body,
      timestamp: Date.now(),
    });
  }

  // Get storage usage estimate
  async getStorageEstimate() {
    if ('storage' in navigator && 'estimate' in navigator.storage) {
      return navigator.storage.estimate();
    }
    return { usage: 0, quota: 0 };
  }

  async ensureDB() {
    if (!this.db) {
      await this.init();
    }
    return this.db;
  }

  close() {
    if (this.db) {
      this.db.close();
      this.db = null;
    }
  }
}

// Export singleton
window.OfflineDB = new OfflineDB();

// Auto-initialize
document.addEventListener('DOMContentLoaded', () => {
  window.OfflineDB.init().catch(console.error);
});

// Export for modules
if (typeof module !== 'undefined' && module.exports) {
  module.exports = OfflineDB;
}
