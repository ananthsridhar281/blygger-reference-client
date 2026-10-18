// Private all-versions canonical store, backed by IndexedDB (browser only).
// Mirrors publish/store.py: holds every version so edit/pin/withdraw work; never committed.
const DB_NAME = "blygger-web";
const DB_VERSION = 1;

function openDb() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION);
    req.onupgradeneeded = () => {
      const db = req.result;
      if (!db.objectStoreNames.contains("items")) db.createObjectStore("items", { keyPath: "id" });
      if (!db.objectStoreNames.contains("meta")) db.createObjectStore("meta");
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

function promise(req) {
  return new Promise((resolve, reject) => {
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

export class Store {
  async _db() {
    if (!this._handle) this._handle = await openDb();
    return this._handle;
  }

  async _objectStore(name, mode) {
    const db = await this._db();
    return db.transaction(name, mode).objectStore(name);
  }

  async getItem(id) {
    const os = await this._objectStore("items", "readonly");
    return (await promise(os.get(id))) || null;
  }

  async createItem(id, authoredKind, created) {
    if (await this.getItem(id)) return;
    const os = await this._objectStore("items", "readwrite");
    await promise(os.put({ id, authoredKind, created, versions: [] }));
  }

  async addVersion(id, record) {
    const rec = await this.getItem(id);
    if (record.pinned === undefined) record.pinned = false;
    rec.versions.push(record);
    const os = await this._objectStore("items", "readwrite");
    await promise(os.put(rec));
  }

  async setPinned(id, version) {
    const rec = await this.getItem(id);
    for (const v of rec.versions) if (v.version === version) v.pinned = true;
    const os = await this._objectStore("items", "readwrite");
    await promise(os.put(rec));
  }

  async allItemIds() {
    const os = await this._objectStore("items", "readonly");
    return promise(os.getAllKeys());
  }

  async allItems() {
    const os = await this._objectStore("items", "readonly");
    return promise(os.getAll());
  }

  async _meta(key, value) {
    if (value === undefined) {
      const os = await this._objectStore("meta", "readonly");
      return (await promise(os.get(key))) || null;
    }
    const os = await this._objectStore("meta", "readwrite");
    await promise(os.put(value, key));
  }

  async setManifestMeta(meta) { await this._meta("manifest", meta); }
  async getManifestMeta() { return (await this._meta("manifest")) || {}; }
  async setBlogroll(entries) { await this._meta("blogroll", entries); }
  async getBlogroll() { return (await this._meta("blogroll")) || []; }

  // Snapshot shaped for blyg/emit.js emit().
  async snapshot() {
    return {
      items: await this.allItems(),
      manifestMeta: await this.getManifestMeta(),
      blogroll: await this.getBlogroll(),
    };
  }
}
