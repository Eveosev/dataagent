"""SQLite schema and samples from a workspace-contained read-only transaction."""
from contextlib import closing
from pathlib import Path
import sqlite3
import time
from .base import ReadOnlySource


def safe_database_path(workspace, locator):
    relative=Path(locator)
    if relative.is_absolute() or '..' in relative.parts or ':' in locator or '?' in locator or '#' in locator:
        raise PermissionError('SQLite locator must be a workspace-relative file path')
    root=Path(workspace).resolve();path=root
    for part in relative.parts:
        path=path/part
        if path.is_symlink(): raise PermissionError('SQLite source must not contain symlinks')
    resolved=path.resolve(strict=True)
    if not resolved.is_relative_to(root) or resolved.is_relative_to(root/'.mint') or not resolved.is_file():
        raise PermissionError('SQLite source is outside allowed workspace')
    return resolved


def quote(identifier):
    return '"'+identifier.replace('"','""')+'"'


def collect(selection, workspace, budget_rows, *, metadata_only=False, credentials=None):
    path=safe_database_path(workspace,selection.locator_ref)
    tables=[];issues=[];gaps=[]
    with closing(sqlite3.connect(path.as_uri()+'?mode=ro',uri=True,timeout=3)) as conn:
        conn.execute('PRAGMA query_only=ON');conn.execute('PRAGMA trusted_schema=OFF')
        deadline=time.monotonic()+5
        conn.set_progress_handler(lambda: int(time.monotonic()>deadline),1000)
        conn.execute('BEGIN')
        available=[row[0] for row in conn.execute("SELECT name FROM sqlite_schema WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name LIMIT 101")]
        if len(available)>100: raise ValueError('database schema exceeds 100 table probe limit; select a smaller database')
        selected=selection.requested_scope.get('tables',available)
        if not isinstance(selected,list) or any(not isinstance(x,str) for x in selected) or len(selected)>100:
            raise ValueError('requested_scope.tables must be a list of at most 100 names')
        remaining=budget_rows
        for name in dict.fromkeys(selected):
            if name not in available:
                issues.append({'code':'table_not_found','table':name});gaps.append((name,'table_not_found'));continue
            columns=[{'name':row[1],'type':row[2],'nullable':not bool(row[3]),'primary_key_position':row[5]} for row in conn.execute('PRAGMA table_info('+quote(name)+')')]
            keys=[col['name'] for col in sorted(columns,key=lambda c:c['primary_key_position']) if col['primary_key_position']]
            rows=[];sampled=False
            if not metadata_only:
                order=' ORDER BY '+','.join(quote(key) for key in keys) if keys else ''
                query='SELECT '+','.join(quote(col['name']) for col in columns)+' FROM '+quote(name)+order+' LIMIT ?'
                result=conn.execute(query,(remaining+1,)).fetchall()
                sampled=len(result)>remaining
                rows=[dict(zip([col['name'] for col in columns],row)) for row in result[:remaining]]
                remaining-=len(rows)
            tables.append({'name':name,'columns':columns,'primary_key':keys,'records':rows,'sampled':sampled})
        conn.rollback()
    return tables,issues,gaps


class SQLiteSource(ReadOnlySource):
    def describe(self, ctx):
        from ...observation.database import _probe
        return _probe(self.selection,ctx,workspace=self.workspace,credentials=self.credentials,metadata_only=True)

    def read(self, ctx, *, budget_rows=200):
        from ...observation.database import probe_database
        return probe_database(self.selection,ctx,workspace=self.workspace,budget_rows=budget_rows,credentials=self.credentials)
