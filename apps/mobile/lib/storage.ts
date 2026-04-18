import { MMKV } from 'react-native-mmkv';

export const storage = new MMKV({
  id: 'consensus-app-storage',
  encryptionKey: 'consensus-secure-key',
});

// Create a persister compatible with @tanstack/query-async-storage-persister
export const clientStorage = {
  setItem: (key: string, value: string) => {
    storage.set(key, value);
    return Promise.resolve();
  },
  getItem: (key: string) => {
    const value = storage.getString(key);
    return Promise.resolve(value ?? null);
  },
  removeItem: (key: string) => {
    storage.delete(key);
    return Promise.resolve();
  },
};
