import { readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';
import { parse } from 'yaml';
import {
  DEFAULT_QUALITY_ARTIFACTS_DIR,
  DEFAULT_QUALITY_CONFIG_PATH,
} from '../src/config/quality-paths.js';

/**
 * El portal solo lee los artefactos que escribe el pipeline de DVC. Estas
 * pruebas fijan el contrato entre los dos lados para que una ruta movida en
 * uno no deje al otro mostrando "sin datos" sin que ningún test lo note.
 */

const backendDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const repoRoot = path.resolve(backendDir, '..');

interface DvcFile {
  stages: Record<
    string,
    { outs?: Array<string | Record<string, unknown>>; params?: Array<Record<string, unknown>> }
  >;
}

interface ComposeFile {
  services: Record<string, { environment: Record<string, string>; volumes?: string[] }>;
}

function readYaml<T>(relativePath: string): T {
  return parse(readFileSync(path.join(repoRoot, relativePath), 'utf-8')) as T;
}

function outputDirOf(stage: string, artifact: string): string {
  const outs = readYaml<DvcFile>('dvc.yaml').stages[stage]?.outs ?? [];
  const paths = outs.map((out) => (typeof out === 'string' ? out : Object.keys(out)[0]));
  const found = paths.find((candidate) => candidate?.endsWith(artifact));
  if (!found) throw new Error(`La etapa ${stage} de dvc.yaml no declara ${artifact} en outs.`);
  return path.dirname(path.join(repoRoot, found));
}

describe('el directorio de artefactos del portal coincide con el que escribe el pipeline', () => {
  const portalDir = path.resolve(backendDir, DEFAULT_QUALITY_ARTIFACTS_DIR);

  it('release.json sale de la etapa release en ese mismo directorio', () => {
    expect(outputDirOf('release', 'release.json')).toBe(portalDir);
  });

  it('embeddings.json sale de la etapa embeddings en ese mismo directorio', () => {
    expect(outputDirOf('embeddings', 'embeddings.json')).toBe(portalDir);
  });

  it('versions.json vive en ese directorio y NO está ignorado por git (es el historial)', () => {
    const ignored = readFileSync(path.join(repoRoot, 'reports', '.gitignore'), 'utf-8')
      .split(/\r?\n/)
      .map((line) => line.trim());

    expect(ignored).not.toContain('/versions.json');
    expect(ignored).not.toContain('versions.json');
    expect(ignored).toContain('/embeddings.json');
    expect(path.join(repoRoot, 'reports')).toBe(portalDir);
  });

  it('.env.example declara el mismo directorio que el valor por defecto', () => {
    const example = readFileSync(path.join(repoRoot, '.env.example'), 'utf-8');

    expect(example).toMatch(
      new RegExp(`^QUALITY_ARTIFACTS_DIR=${DEFAULT_QUALITY_ARTIFACTS_DIR}$`, 'm'),
    );
  });
});

describe('la política que edita Settings es la misma que lee el pipeline', () => {
  it('la ruta por defecto apunta al quality.yaml que declara dvc.yaml como params', () => {
    const paramsFiles = (readYaml<DvcFile>('dvc.yaml').stages.analyze?.params ?? []).flatMap(
      (entry) => Object.keys(entry),
    );

    expect(paramsFiles).toContain('quality/quality.yaml');
    expect(path.resolve(backendDir, DEFAULT_QUALITY_CONFIG_PATH)).toBe(
      path.join(repoRoot, 'quality', 'quality.yaml'),
    );
  });
});

describe('docker-compose monta los artefactos y la política dentro del backend', () => {
  const backend = readYaml<ComposeFile>('docker-compose.yml').services.backend ?? {
    environment: {},
  };
  const volumes = backend.volumes ?? [];

  it('define las dos variables de ruta del portal', () => {
    expect(backend.environment.QUALITY_ARTIFACTS_DIR).toBeTruthy();
    expect(backend.environment.QUALITY_CONFIG_PATH).toBeTruthy();
  });

  it('monta ./reports en el directorio de artefactos, solo lectura', () => {
    const target = backend.environment.QUALITY_ARTIFACTS_DIR;

    expect(volumes).toContain(`./reports:${target}:ro`);
  });

  it('monta quality.yaml con escritura, porque Settings lo edita', () => {
    const target = backend.environment.QUALITY_CONFIG_PATH;

    expect(volumes).toContain(`./quality/quality.yaml:${target}`);
  });
});
