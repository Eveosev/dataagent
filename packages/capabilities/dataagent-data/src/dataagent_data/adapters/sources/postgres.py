"""PostgreSQL metadata and safely quoted bounded reads; never accepts user SQL."""
from urllib.parse import urlsplit, unquote
from .base import ReadOnlySource


def connection_parameters(selection, credentials):
    parsed=urlsplit(selection.locator_ref)
    if parsed.scheme not in {'postgres','postgresql'} or not parsed.hostname or not parsed.path.strip('/'):
        raise ValueError('PostgreSQL locator requires host and database')
    if parsed.username is not None or parsed.password is not None or parsed.query or parsed.fragment:
        raise ValueError('PostgreSQL locator cannot contain credentials or connection options')
    credentials=credentials or {}
    if set(credentials)-{'user','password','sslmode'}: raise ValueError('unsupported PostgreSQL credential configuration')
    params={'host':parsed.hostname,'port':parsed.port or 5432,'dbname':unquote(parsed.path[1:]),'connect_timeout':5,
        'options':'-c default_transaction_read_only=on -c statement_timeout=5000 -c lock_timeout=1000',
        'sslmode':credentials.get('sslmode','prefer')}
    for key in ['user','password']:
        if key in credentials: params[key]=credentials[key]
    return params


def collect(selection, workspace, budget_rows, *, metadata_only=False, credentials=None):
    params=connection_parameters(selection,credentials)
    import psycopg
    from psycopg import sql
    schema=selection.requested_scope.get('schema','public')
    if not isinstance(schema,str) or not schema: raise ValueError('schema must be a nonempty name')
    tables=[];issues=[];gaps=[]
    with psycopg.connect(**params) as conn:
        conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
        available=[row[0] for row in conn.execute("SELECT table_name FROM information_schema.tables WHERE table_schema=%s AND table_type='BASE TABLE' ORDER BY table_name LIMIT 101",(schema,))]
        if len(available)>100: raise ValueError('database schema exceeds 100 table probe limit')
        selected=selection.requested_scope.get('tables',available)
        if not isinstance(selected,list) or len(selected)>100 or any(not isinstance(x,str) for x in selected):
            raise ValueError('requested_scope.tables must be a list of at most 100 names')
        remaining=budget_rows
        for name in dict.fromkeys(selected):
            if name not in available:
                issues.append({'code':'table_not_found','table':name,'schema':schema});gaps.append((name,'table_not_found'));continue
            info=conn.execute('SELECT column_name,data_type,is_nullable FROM information_schema.columns WHERE table_schema=%s AND table_name=%s ORDER BY ordinal_position',(schema,name)).fetchall()
            columns=[{'name':col,'type':kind,'nullable':nullable=='YES'} for col,kind,nullable in info]
            keys=[row[0] for row in conn.execute('''SELECT kcu.column_name FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu ON tc.constraint_catalog=kcu.constraint_catalog
                AND tc.constraint_schema=kcu.constraint_schema AND tc.constraint_name=kcu.constraint_name AND tc.table_name=kcu.table_name
                WHERE tc.constraint_type='PRIMARY KEY' AND tc.table_schema=%s AND tc.table_name=%s ORDER BY kcu.ordinal_position''',(schema,name))]
            rows=[];sampled=False
            if not metadata_only:
                query=sql.SQL('SELECT {} FROM {}').format(sql.SQL(',').join(sql.Identifier(c['name']) for c in columns),sql.Identifier(schema,name))
                if keys: query+=sql.SQL(' ORDER BY {}').format(sql.SQL(',').join(sql.Identifier(k) for k in keys))
                query+=sql.SQL(' LIMIT %s')
                result=conn.execute(query,(remaining+1,)).fetchall();sampled=len(result)>remaining
                rows=[dict(zip([c['name'] for c in columns],row)) for row in result[:remaining]];remaining-=len(rows)
            tables.append({'name':name,'schema':schema,'columns':columns,'primary_key':keys,'records':rows,'sampled':sampled})
    return tables,issues,gaps


class PostgresSource(ReadOnlySource):
    def describe(self, ctx):
        from ...observation.database import _probe
        return _probe(self.selection,ctx,workspace=self.workspace,credentials=self.credentials,metadata_only=True)

    def read(self, ctx, *, budget_rows=200):
        from ...observation.database import probe_database
        return probe_database(self.selection,ctx,workspace=self.workspace,budget_rows=budget_rows,credentials=self.credentials)
