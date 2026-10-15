"""Create a coordinated Docker PostgreSQL/files backup without overwriting existing backups.
Run from the project root: python scripts/postgres-backup.py --output backups/2026-10-14
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    destination = Path(args.output).resolve()
    destination.mkdir(parents=True, exist_ok=False)
    compose = ['docker', 'compose', '--env-file', str(ROOT / '.env.production'), '-f', str(ROOT / 'docker-compose.yml')]
    container = 'learnsphere-backup-' + uuid4().hex[:12]
    temporary_dump = '/tmp/' + container + '.dump'

    def run(command, **kwargs):
        return subprocess.run(command, cwd=ROOT, check=True, **kwargs)

    running = run(compose + ['ps', '--services', '--status', 'running'], capture_output=True, text=True).stdout.splitlines()
    writers = [s for s in ['backend', 'worker'] if s in running]
    try:
        if writers:
            run(compose + ['stop', *writers])
        dump_script = 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc -f ' + temporary_dump
        run(compose + ['exec', '-T', 'db', 'sh', '-c', dump_script])
        run(compose + ['cp', 'db:' + temporary_dump, str(destination / 'database.dump')])
        archive = "import tarfile; t=tarfile.open('/app/files-backup.tar.gz','w:gz'); t.add('/app/storage',arcname='storage'); t.close()"
        run(compose + ['run', '--name', container, '--no-deps', '--entrypoint', 'python', 'backend', '-c', archive])
        run(['docker', 'cp', container + ':/app/files-backup.tar.gz', str(destination / 'files.tar.gz')])
        manifest = {}
        for name in ['database.dump', 'files.tar.gz']:
            path = destination / name
            with path.open('rb') as handle:
                digest = hashlib.file_digest(handle, 'sha256').hexdigest()
            manifest[name] = {'size': path.stat().st_size, 'sha256': digest}
        (destination / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
        print('Backup created:', destination)
        print('Test restoration in an isolated environment and store encryption secrets separately.')
    finally:
        subprocess.run(['docker', 'rm', container], cwd=ROOT, check=False, stdout=subprocess.DEVNULL)
        subprocess.run(compose + ['exec', '-T', 'db', 'rm', '-f', temporary_dump], cwd=ROOT, check=False)
        if writers:
            run(compose + ['start', *writers])


if __name__ == '__main__':
    main()
