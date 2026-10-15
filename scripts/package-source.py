"""Package source only. Does not include databases, secrets, wheels or node_modules."""
from pathlib import Path
import argparse
import hashlib
import zipfile

ROOT = Path(__file__).resolve().parents[1]
ROOT_FILES = {
    'README.md', '.env.example', '.env.production.example', '.gitignore', '.dockerignore',
    'install.bat', 'run-local.bat', 'run-docker.bat', 'stop-docker.bat', 'reset-demo-data.bat',
    'docker-compose.yml', 'docker-compose.dev.yml',
}
BACKEND_FILES = {'Dockerfile', '.dockerignore', 'pyproject.toml', 'alembic.ini', 'requirements.txt', 'requirements.in', 'requirements-dev.txt', 'requirements-dev.in'}
FRONTEND_FILES = {'package.json', 'package-lock.json', 'Dockerfile', 'index.html', 'tsconfig.json', 'vite.config.ts', 'playwright.config.ts', 'postcss.config.js', 'tailwind.config.js', 'eslint.config.js'}
IGNORED = {'__pycache__', 'node_modules', 'dist', '.pytest_cache', '.ruff_cache', '.mypy_cache', 'data', 'storage', 'test-results', 'playwright-report'}


def included(path):
    parts = path.relative_to(ROOT).parts
    if any(part in IGNORED for part in parts) or path.suffix in {'.pyc', '.log', '.db', '.zip'}:
        return False
    if len(parts) == 1:
        return parts[0] in ROOT_FILES
    if parts[0] == 'backend':
        return parts[1] in {'app', 'tests', 'alembic'} or (len(parts) == 2 and parts[1] in BACKEND_FILES)
    if parts[0] == 'frontend':
        return parts[1] in {'src', 'e2e', 'public'} or (len(parts) == 2 and parts[1] in FRONTEND_FILES)
    return parts[0] in {'docs', 'scripts', 'nginx', '.github'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    target = Path(args.output).resolve()
    if target.exists():
        raise SystemExit('Output exists; choose a new filename to preserve existing archives')
    target.parent.mkdir(parents=True, exist_ok=True)
    manifest = []
    with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(ROOT.rglob('*')):
            if path.is_file() and included(path):
                relative = path.relative_to(ROOT).as_posix()
                archive.write(path, 'learnsphere-enterprise/' + relative)
                manifest.append(hashlib.sha256(path.read_bytes()).hexdigest() + '  ' + relative)
        archive.writestr('learnsphere-enterprise/MANIFEST.sha256', '\n'.join(manifest) + '\n')
    with zipfile.ZipFile(target) as archive:
        assert archive.testzip() is None
        assert 'learnsphere-enterprise/README.md' in archive.namelist()
        assert 'learnsphere-enterprise/frontend/package-lock.json' in archive.namelist()
        assert all(not name.endswith('/.env') for name in archive.namelist())
    print(f'{target}\n{len(manifest)} source files; {target.stat().st_size} bytes; ZIP integrity verified')


if __name__ == '__main__':
    main()
