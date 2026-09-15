import { beforeEach, describe, expect, it, vi } from 'vitest';

const state = vi.hoisted(() => ({ provider: 'minio' as 'minio' | 's3' }));
const minio = vi.hoisted(() => ({
  ensure: vi.fn(),
  put: vi.fn(),
  remove: vi.fn(),
  get: vi.fn(),
}));
const s3 = vi.hoisted(() => ({
  ensure: vi.fn(),
  put: vi.fn(),
  remove: vi.fn(),
  get: vi.fn(),
}));

vi.mock('../src/config/env.js', () => ({
  env: {
    get STORAGE_PROVIDER() {
      return state.provider;
    },
  },
}));

vi.mock('../src/data/storage/minio.storage.js', () => ({
  ensureMinioBucket: minio.ensure,
  uploadImageObject: minio.put,
  deleteImageObject: minio.remove,
  getImageObjectStream: minio.get,
}));

vi.mock('../src/data/storage/s3.storage.js', () => ({
  ensureS3Bucket: s3.ensure,
  putS3Image: s3.put,
  deleteS3Image: s3.remove,
  getS3ImageStream: s3.get,
}));

import {
  deleteImageObject,
  ensureObjectStorage,
  getImageObjectStream,
  uploadImageObject,
} from '../src/data/storage/object.storage.js';

describe('selección del proveedor de almacenamiento', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    state.provider = 'minio';
  });

  it('conserva MinIO como proveedor del stack local', async () => {
    await ensureObjectStorage();
    await uploadImageObject('images/a.jpg', Buffer.from('a'), 'image/jpeg');
    await deleteImageObject('images/a.jpg');
    await getImageObjectStream('images/a.jpg');

    expect(minio.ensure).toHaveBeenCalledOnce();
    expect(minio.put).toHaveBeenCalledOnce();
    expect(minio.remove).toHaveBeenCalledOnce();
    expect(minio.get).toHaveBeenCalledOnce();
    expect(s3.put).not.toHaveBeenCalled();
  });

  it('usa S3 en Fargate sin pasar credenciales estáticas', async () => {
    state.provider = 's3';

    await ensureObjectStorage();
    await uploadImageObject('images/a.jpg', Buffer.from('a'), 'image/jpeg');
    await deleteImageObject('images/a.jpg');
    await getImageObjectStream('images/a.jpg');

    expect(s3.ensure).toHaveBeenCalledOnce();
    expect(s3.put).toHaveBeenCalledOnce();
    expect(s3.remove).toHaveBeenCalledOnce();
    expect(s3.get).toHaveBeenCalledOnce();
    expect(minio.put).not.toHaveBeenCalled();
  });
});
