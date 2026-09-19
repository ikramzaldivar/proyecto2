import { readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { parse } from 'dotenv';
import { afterEach, describe, expect, it, vi } from 'vitest';

/**
 * El primer paso del README es `cp .env.example .env`. Si el esquema de
 * variables rechaza la plantilla tal cual, el backend no arranca para quien
 * siga el README al pie de la letra. Con `COPILOT_API_KEY=` (vacía a
 * propósito: sin clave el Copilot responde en modo anclado) el esquema exigía
 * al menos un carácter y fallaba.
 */

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..');
const template = parse(readFileSync(path.join(repoRoot, '.env.example'), 'utf-8'));

async function loadEnvWith(values: Record<string, string>) {
  vi.resetModules();
  for (const [key, value] of Object.entries(values)) vi.stubEnv(key, value);
  return (await import('../src/config/env.js')).env;
}

afterEach(() => {
  vi.unstubAllEnvs();
});

describe('.env.example es una configuración válida tal cual', () => {
  it('el esquema de variables acepta la plantilla sin editar nada', async () => {
    const env = await loadEnvWith(template);

    expect(env.COPILOT_PROVIDER).toBe('none');
  });

  it('una clave o modelo vacíos significan "sin configurar", no un error', async () => {
    const env = await loadEnvWith({ ...template, COPILOT_API_KEY: '', COPILOT_MODEL: '' });

    expect(env.COPILOT_API_KEY).toBeUndefined();
    expect(env.COPILOT_MODEL).toBeUndefined();
  });

  it('una clave real sí se conserva', async () => {
    const env = await loadEnvWith({
      ...template,
      COPILOT_PROVIDER: 'mistral',
      COPILOT_API_KEY: 'clave-de-prueba',
    });

    expect(env.COPILOT_API_KEY).toBe('clave-de-prueba');
  });
});
