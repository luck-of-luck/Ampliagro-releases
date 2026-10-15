/**
 * Ampliagro Sync Module - Background synchronization
 * Handles: mutation queue, conflict resolution, progress tracking
 */
class SyncManager {
  constructor(offlineDB) {
    this.offlineDB = offlineDB;
    this.syncing = false;
    this.listeners = new Set();
    this.lastSync = null;
    this.syncInterval = null;
  }

  // Register for sync updates
  onSyncUpdate(callback) {
    this.listeners.add(callback);
    return () => this.listeners.delete(callback);
  }

  notifyListeners(data) {
    this.listeners.forEach((cb) => cb(data));
  }

  async syncAll() {
    if (this.syncing) return { success: false, error: 'Sync already in progress' };

    this.syncing = true;
    this.notifyListeners({ status: 'started', timestamp: Date.now() });

    try {
      // 1. Sync mutations (offline mutations queue)
      await this.syncMutations();

      // 2. Sync field notes
      await this.syncFieldNotes();

      // 3. Sync photos
      await this.syncPhotos();

      // 4. Sync observations
      await this.syncObservations();

      // 5. Sync tasks
      await this.syncTasks();

      // 6. Sync experiments
      await this.syncExperiments();

      // 7. Sync voice recordings
      await this.syncVoiceRecordings();

      this.lastSync = Date.now();
      localStorage.setItem('lastSync', this.lastSync.toString());

      this.notifyListeners({
        status: 'completed',
        timestamp: Date.now(),
        lastSync: this.lastSync,
      });

      return { success: true, timestamp: this.lastSync };
    } catch (error) {
      console.error('[Sync] Error:', error);
      this.notifyListeners({ status: 'error', error: error.message, timestamp: Date.now() });
      return { success: false, error: error.message };
    } finally {
      this.syncing = false;
    }
  }

  async syncMutations() {
    const mutations = await window.OfflineDB.getPendingMutations();
    if (!mutations.length) return;

    for (const mutation of mutations) {
      try {
        const response = await fetch(mutation.url, {
          method: mutation.method,
          headers: mutation.headers,
          body: mutation.body,
        });

        if (response.ok) {
          await window.OfflineDB.removeMutation(mutation.id);
        } else if (response.status === 409) {
          // Conflict - notify for manual resolution
          this.notifyListeners({
            type: 'conflict',
            mutationId: mutation.id,
            serverResponse: await response.json(),
          });
        }
      } catch (error) {
        console.error('[Sync] Mutation failed:', mutation.id, error);
      }
    }
  }

  async syncFieldNotes() {
    const notes = await window.OfflineDB.getFieldNotes();
    const unsynced = notes.filter((n) => !n.synced);

    for (const note of unsynced) {
      try {
        const response = await fetch('/api/caderno/notas/', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': this.getCSRFToken(),
          },
          body: JSON.stringify({
            talhao_id: note.talhao_id,
            cultura_id: note.cultura_id,
            conteudo: note.conteudo,
            tipo: note.tipo || 'observacao',
            latitude: note.latitude,
            longitude: note.longitude,
            offline_id: note.id,
            // A hora a que o produtor escreveu, nao a que o servidor
            // recebeu. `saveFieldNote` grava `created_at` no IndexedDB
            // (indexeddb.js:198) e o payload descartava-o: uma nota das
            // 06:00 sincronizada as 18:00 ficava datada das 18:00. Numa
            // nota de campo isso e' a diferença entre "antes ou depois do
            //odio" e "depois da pulverizacao" — e o servidor passava a
            // assumir `now()`, que e' inventar a hora de uma observacao.
            registada_em: note.created_at || note.timestamp || null,
          }),
        });

        if (response.ok) {
          await window.OfflineDB.markNoteSynced(note.id);
        }
      } catch (error) {
        console.error('[Sync] Note sync failed:', error);
      }
    }
  }

  async syncPhotos() {
    const notes = await window.OfflineDB.getFieldNotes();
    for (const note of notes) {
      const photos = await window.OfflineDB.getPhotos(note.id);
      const unsynced = photos.filter((p) => !p.synced);

      for (const photo of unsynced) {
        try {
          const formData = new FormData();
          formData.append('note_id', note.id);
          formData.append('image', photo.blob, photo.filename);
          formData.append('caption', photo.caption || '');

          const response = await fetch('/api/caderno/fotos/', {
            method: 'POST',
            headers: {
              'X-CSRFToken': this.getCSRFToken(),
            },
            body: formData,
          });

          if (response.ok) {
            // Update photo as synced
            const photoRecord = await window.OfflineDB.get('photos', photo.id);
            if (photoRecord) {
              photoRecord.synced = true;
              photoRecord.synced_at = new Date().toISOString();
              await window.OfflineDB.put('photos', photoRecord);
            }
          }
        } catch (error) {
          console.error('[Sync] Photo sync failed:', error);
        }
      }
    }
  }

  async syncObservations() {
    // Similar to notes sync
    // Implementation similar to syncFieldNotes
  }

  async syncTasks() {
    const tasks = await window.OfflineDB.getTasks();
    const unsynced = tasks.filter((t) => !t.synced);

    for (const task of unsynced) {
      try {
        const response = await fetch('/api/tarefas-estagio/', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': this.getCSRFToken(),
          },
          body: JSON.stringify({
            estagio: task.estagio_id,
            descricao: task.descricao,
            cargo_alvo: task.cargo_alvo,
            setor: task.setor,
            prioridade: task.prioridade,
            data_limite: task.data_limite,
            status: task.status || 'pendente',
          }),
        });

        if (response.ok) {
          const taskRecord = await window.OfflineDB.get('offline_tasks', task.id);
          if (taskRecord) {
            taskRecord.synced = true;
            taskRecord.synced_at = new Date().toISOString();
            await window.OfflineDB.put('offline_tasks', taskRecord);
          }
        }
      } catch (error) {
        console.error('[Sync] Task sync failed:', error);
      }
    }
  }

  async syncExperiments() {
    // Endpoint /api/experimentos/ ainda não implementado no backend.
    // Falha alto em vez de fingir sucesso: não marca como synced.
    const experiments = await window.OfflineDB.getAll('experiments');
    const unsynced = experiments.filter((e) => !e.synced);
    if (unsynced.length) {
      console.error(
        '[Sync] /api/experimentos/ não implementado — ' +
          unsynced.length +
          ' experimento(s) pendente(s) não sincronizados.'
      );
    }
  }

  async syncVoiceRecordings() {
    // Endpoint /api/caderno/voice/ ainda não implementado no backend.
    // Falha alto em vez de fingir sucesso: não marca como synced.
    const recordings = await window.OfflineDB.getAll('voice_recordings');
    const unsynced = recordings.filter((r) => !r.synced);
    if (unsynced.length) {
      console.error(
        '[Sync] /api/caderno/voice/ não implementado — ' +
          unsynced.length +
          ' gravação(ões) pendente(s) não sincronizadas.'
      );
    }
  }

  getCSRFToken() {
    return (
      document.querySelector('[name=csrfmiddlewaretoken]')?.value ||
      document.cookie.match(/csrftoken=([^;]+)/)?.[1] ||
      ''
    );
  }

  // Periodic sync
  startPeriodicSync(intervalMinutes = 5) {
    if (this.syncInterval) {
      clearInterval(this.syncInterval);
    }
    this.syncInterval = setInterval(
      () => {
        if (navigator.onLine) {
          this.syncAll();
        }
      },
      intervalMinutes * 60 * 1000
    );

    // Initial sync
    if (navigator.onLine) {
      this.syncAll();
    }
  }

  stopPeriodicSync() {
    if (this.syncInterval) {
      clearInterval(this.syncInterval);
      this.syncInterval = null;
    }
  }

  getLastSync() {
    return this.lastSync || parseInt(localStorage.getItem('lastSync') || '0');
  }

  isOnline() {
    return navigator.onLine;
  }

  // Get sync status for UI
  async getSyncStatus() {
    const mutations = await window.OfflineDB.getPendingMutations();
    const notes = await window.OfflineDB.getFieldNotes();
    const unsyncedNotes = notes.filter((n) => !n.synced).length;
    const tasks = await window.OfflineDB.getTasks();
    const unsyncedTasks = tasks.filter((t) => !t.synced).length;

    return {
      online: navigator.onLine,
      syncing: this.syncing,
      lastSync: this.lastSync,
      pendingMutations: mutations.length,
      unsyncedNotes,
      unsyncedTasks,
      totalPending: mutations.length + unsyncedNotes + unsyncedTasks,
    };
  }
}

// Auto-start sync when online
window.addEventListener('online', () => {
  if (window.SyncManager) {
    window.SyncManager.syncAll();
  }
});

window.addEventListener('offline', () => {
  console.log('[Sync] Gone offline, mutations will queue');
});

// Export
window.SyncManager = new SyncManager(window.OfflineDB);

// Auto-start periodic sync
document.addEventListener('DOMContentLoaded', () => {
  if (window.SyncManager) {
    window.SyncManager.startPeriodicSync(5); // Every 5 minutes
  }
});

if (typeof module !== 'undefined' && module.exports) {
  module.exports = SyncManager;
}
