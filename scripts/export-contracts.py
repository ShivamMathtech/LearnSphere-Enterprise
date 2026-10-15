"""Regenerate schema inventory, permission matrix, and OpenAPI snapshot from source."""
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT / 'backend')
sys.path.insert(0, str(ROOT / 'backend'))
from app.main import app
from app.db.base import Base
from app.security.permissions import ROLE_PERMISSIONS

doc = ROOT / 'docs'
(doc / 'openapi.json').write_text(json.dumps(app.openapi(), indent=2) + '\n', encoding='utf-8')
lines = ['# Relational schema inventory', '', 'Generated from the single SQLAlchemy model. UUID strings identify entities; UTC timestamps are normalized through `UTCDateTime`. Association tables use composite primary keys. Tenant-owned domain rows carry indexed `institution_id`; child joins inherit scope through validated parents.', '', '| Table | Columns | References |', '| --- | --- | --- |']
for table in Base.metadata.sorted_tables:
    columns = ', '.join('`' + c.name + '`' + (' PK' if c.primary_key else '') + ('?' if c.nullable else '') for c in table.columns)
    refs = ', '.join(sorted({f'{f.parent.name} → {f.target_fullname} ({f.ondelete or "restrict"})' for f in table.foreign_keys})) or '—'
    lines.append(f'| `{table.name}` | {columns} | {refs} |')
lines += ['', f'{len(Base.metadata.tables)} tables. `?` marks nullable fields. Course tags are a bounded JSON list; options, attachments, progress, role mappings, rubrics and grades have dedicated relational entities.', '', '## Unique constraints', '', '| Table | Unique fields |', '| --- | --- |']
from sqlalchemy import UniqueConstraint
for table in Base.metadata.sorted_tables:
    for constraint in table.constraints:
        if isinstance(constraint, UniqueConstraint):
            lines.append(f'| `{table.name}` | ' + ', '.join(c.name for c in constraint.columns) + ' |')
(doc / 'SCHEMA.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
roles = list(ROLE_PERMISSIONS)
lines = ['# Permission registry', '', 'Assignment/ownership and tenant policy still apply when a permission is granted. This is a role mapping, not a blanket authorization to every resource.', '', '| Permission | ' + ' | '.join(roles) + ' |', '| --- | ' + ' | '.join(['---'] * len(roles)) + ' |']
for permission in sorted(set.union(*ROLE_PERMISSIONS.values())):
    lines.append('| `' + permission + '` | ' + ' | '.join('Yes' if permission in ROLE_PERMISSIONS[r] else '—' for r in roles) + ' |')
(doc / 'PERMISSIONS.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
print(json.dumps({'tables': len(Base.metadata.tables), 'paths': len(app.openapi()['paths']), 'operations': sum(len(v) for v in app.openapi()['paths'].values()), 'roles': len(roles)}))
