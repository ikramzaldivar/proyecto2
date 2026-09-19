import { existsSync, readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

/**
 * La rúbrica evalúa el arranque siguiendo el README LITERALMENTE. Estas
 * pruebas fijan lo que un lector necesita encontrar ahí y que nada de lo que
 * se documenta apunte a algo que ya no existe (un refactor que mueve
 * archivos tiene que mover también la documentación en el mismo commit).
 */

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..');
const read = (relativePath: string): string =>
  readFileSync(path.join(repoRoot, relativePath), 'utf-8');
const exists = (relativePath: string): boolean => existsSync(path.join(repoRoot, relativePath));

/** Enlaces markdown `[texto](ruta)` que apuntan a un archivo del repo. */
function relativeLinks(markdown: string): string[] {
  return [...markdown.matchAll(/\]\(([^)\s]+)\)/g)]
    .map((match) => match[1] ?? '')
    .filter((target) => !/^(https?:|mailto:|#)/.test(target))
    .map((target) => target.split('#')[0] ?? '')
    .filter((target) => target.length > 0);
}

/** Destinos de `cd <ruta>` escritos como ruta relativa a la raíz del repo. */
function cdTargets(markdown: string): string[] {
  return [...markdown.matchAll(/^\s*cd\s+([A-Za-z][\w./-]*)\s*$/gm)].map(
    (match) => match[1] ?? '',
  );
}

const QUALITY_ROUTES = [
  '/overview',
  '/analyzers',
  '/analytics',
  '/splits',
  '/versions',
  '/settings',
  '/copilot',
];

describe('C-01 — el README describe el proyecto que se construyó', () => {
  const readme = read('README.md');
  const firstScreen = readme.split('\n').slice(0, 45).join('\n');

  it('el antecedente del portal MP1 se conserva en docs/portal-mp1.md', () => {
    expect(exists('docs/portal-mp1.md')).toBe(true);
    expect(read('docs/portal-mp1.md')).toMatch(/Portal de anotación/i);
    expect(readme).toContain('](docs/portal-mp1.md)');
  });

  it('la primera pantalla dice qué es el proyecto y no un portal de anotación', () => {
    expect(firstScreen).toMatch(/dataset COCO versionado/i);
    expect(readme.split('\n')[0]).not.toMatch(/Portal de anotación/i);
  });

  it('la primera pantalla nombra los cinco tiers', () => {
    for (const tier of ['Ingesta', 'Analizadores', 'Compuerta', 'Split', 'DVC']) {
      expect(firstScreen).toContain(tier);
    }
  });

  it('la primera pantalla trae el comando para levantar todo', () => {
    expect(firstScreen).toContain('make up');
  });

  it('menciona el pipeline de calidad lo bastante para que un lector lo encuentre', () => {
    const matching = readme
      .split('\n')
      .filter((line) => /dvc|quality gate|copilot|mcp|terraform/i.test(line));

    expect(matching.length).toBeGreaterThanOrEqual(10);
  });
});

describe('C-01 — «Arranque desde cero» es una secuencia sin pasos implícitos', () => {
  const readme = read('README.md');
  const section = readme.split(/^## /m).find((part) => part.startsWith('Arranque desde cero'));

  it('existe la sección', () => {
    expect(section).toBeTruthy();
  });

  it.each([
    'git clone https://github.com/ikramzaldivar/proyecto2.git',
    'cp .env.example .env',
    'pip install -e "quality/[dev]"',
    'npm --prefix backend ci',
    'dvc pull -r prod',
    'dvc repro',
    'docker compose up --build',
  ])('incluye el comando: %s', (command) => {
    expect(section ?? '').toContain(command);
  });

  it('explica por qué hay que correr el pipeline antes de levantar la app', () => {
    expect(section ?? '').toMatch(/salidas del pipeline|no (son|van en) (la )?fuente|no van en git/i);
  });

  it('ofrece una salida para quien no tiene acceso a los remotos de DVC', () => {
    expect(section ?? '').toContain('make demo');
  });
});

describe('C-01 — la tabla de rutas coincide con las rutas reales de la app', () => {
  const readme = read('README.md');
  const appRoutes = [...read('frontend/src/App.tsx').matchAll(/path="(\/[a-z]+)"/g)].map(
    (match) => match[1],
  );

  it.each(QUALITY_ROUTES)('la ruta %s existe en App.tsx y está documentada', (route) => {
    expect(appRoutes).toContain(route);
    expect(readme).toContain(`\`${route}\``);
  });

  it('documenta el puerto donde se sirve el frontend', () => {
    expect(readme).toContain('http://localhost:8080');
  });
});

describe('C-01 — Copilot y servidor MCP', () => {
  const readme = read('README.md');
  const scripts = (JSON.parse(read('backend/package.json')) as { scripts: Record<string, string> })
    .scripts;
  const envExample = read('.env.example');

  it.each(['copilot:demo', 'mcp'])('documenta `npm run %s` y el script existe', (script) => {
    expect(scripts[script]).toBeTruthy();
    expect(readme).toContain(`npm run ${script}`);
  });

  it.each(['COPILOT_PROVIDER', 'COPILOT_API_KEY', 'COPILOT_MODEL'])(
    'documenta %s, está en .env.example y el compose se la pasa al backend',
    (variable) => {
      expect(readme).toContain(variable);
      expect(envExample).toContain(variable);
      expect(read('docker-compose.yml')).toContain(`${variable}: \${${variable}:-`);
    },
  );
});

describe('C-01 — los documentos que existen no quedan huérfanos', () => {
  const readme = read('README.md');

  it.each([
    'DEPLOY.md',
    'infra/terraform/README.md',
    'docs/frente3-quality-api.md',
    'docs/portal-mp1.md',
  ])('el README enlaza %s', (target) => {
    expect(readme).toContain(`](${target})`);
    expect(exists(target)).toBe(true);
  });

  it.each(['README.md', 'DEPLOY.md', 'docs/portal-mp1.md', 'infra/terraform/README.md'])(
    'todos los enlaces relativos de %s apuntan a algo que existe',
    (file) => {
      const baseDir = path.dirname(file);
      for (const target of relativeLinks(read(file))) {
        expect(exists(path.join(baseDir, target)), `${file} -> ${target}`).toBe(true);
      }
    },
  );
});

describe('C-02 — DEPLOY.md apunta a la raíz de Terraform que existe', () => {
  const deploy = read('DEPLOY.md');

  it('el paso 2 entra a infra/terraform/envs/prod', () => {
    expect(deploy).toMatch(/^cd infra\/terraform\/envs\/prod$/m);
    expect(deploy).not.toMatch(/^cd infra\/terraform$/m);
  });

  it('todas las rutas de `cd` de DEPLOY.md y del README existen', () => {
    for (const file of ['DEPLOY.md', 'README.md']) {
      for (const target of cdTargets(read(file))) {
        expect(exists(target), `${file}: cd ${target}`).toBe(true);
      }
    }
  });

  it('los archivos que el procedimiento usa existen en la raíz de prod', () => {
    for (const file of ['backend.hcl.example', 'terraform.tfvars.example', 'outputs.tf']) {
      expect(exists(`infra/terraform/envs/prod/${file}`), file).toBe(true);
    }
    expect(read('infra/terraform/envs/prod/outputs.tf')).toContain('application_url');
  });

  it('avisa que hay dos raíces y que solo prod está aplicada', () => {
    expect(deploy).toMatch(/envs\/dev/);
    expect(deploy).toMatch(/solo\s+`?prod`?\s+está aplicad/i);
  });
});

describe('C-03 — un solo comando y una salida sin acceso a los remotos', () => {
  const makefile = read('Makefile');

  function recipe(target: string): string[] {
    const lines = (makefile.split(new RegExp(`^${target}:.*$`, 'm'))[1] ?? '')
      .replace(/\r/g, '')
      .split('\n')
      .slice(1);
    const steps: string[] = [];
    for (const line of lines) {
      if (!line.startsWith('\t')) break;
      steps.push(line.trim());
    }
    return steps;
  }

  it('`make up` encadena dvc pull, dvc repro y docker compose up, en ese orden', () => {
    const steps = recipe('up');
    const order = ['dvc pull -r prod', 'dvc repro', 'docker compose up --build'].map((command) =>
      steps.findIndex((step) => step.startsWith(command)),
    );

    expect(order.every((index) => index >= 0)).toBe(true);
    expect([...order].sort((a, b) => a - b)).toEqual(order);
  });

  it('`make demo` genera los artefactos a partir del dataset sintético y levanta la app', () => {
    const steps = recipe('demo').join('\n');

    expect(steps).toContain('make_demo_dataset.py');
    expect(makefile).toContain('DEMO_POLICY = quality/quality.demo.yaml');
    expect(steps).toContain('--config $(DEMO_POLICY)');
    expect(steps).toContain('docker compose up --build');
  });

  it('el compose permite apuntar a otra carpeta de artefactos y a otra política', () => {
    const compose = read('docker-compose.yml');

    expect(compose).toContain('${QUALITY_REPORTS_DIR:-./reports}:/artifacts:ro');
    expect(compose).toContain('${QUALITY_CONFIG_FILE:-./quality/quality.yaml}:/config/quality.yaml');
  });

  it('el Makefile se queda con saltos de línea LF en cualquier checkout (make falla con CRLF)', () => {
    expect(read('.gitattributes')).toMatch(/^Makefile\s+text\s+eol=lf$/m);
  });

  it('la carpeta demo/ no se versiona (la rúbrica penaliza imágenes en git)', () => {
    expect(read('.gitignore').split(/\r?\n/)).toContain('demo/');
  });

  it('la política de la demo no reemplaza a la real', () => {
    const real = read('quality/quality.yaml');
    const demo = read('quality/quality.demo.yaml');

    expect(real).toMatch(/threshold: 300/);
    expect(demo).toMatch(/SOLO DEMO/i);
    expect(demo).not.toMatch(/threshold: 300/);
  });
});
