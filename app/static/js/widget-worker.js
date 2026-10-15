/**
 * Web Worker for Ampliagro Widgets
 * Handles heavy calculations outside the main thread to keep UI responsive.
 */

self.addEventListener('message', function (e) {
  var data = e.data;
  if (!data || !data.id) return;

  var id = data.id;
  var type = data.type;
  var payload = data.payload;

  try {
    var result = processTask(type, payload);
    self.postMessage({ id: id, success: true, result: result });
  } catch (err) {
    self.postMessage({ id: id, success: false, error: err.message || String(err) });
  }
});

function processTask(type, payload) {
  // Placeholder for future heavy calculations
  switch (type) {
    case 'ping':
      return 'pong';
    default:
      console.warn('Unknown worker task type:', type);
      return null;
  }
}
