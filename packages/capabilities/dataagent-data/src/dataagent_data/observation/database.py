"""Bounded database observations with typed keys and immutable sample evidence."""
from dataagent_contracts.core.refs import SourceAnchor
from dataagent_contracts.intake import SourceProfile, CoverageGap
from ..adapters.sources.base import digest, json_value, snapshot, typed_key


def probe_database(selection, ctx, *, workspace, budget_rows=200, credentials=None):
    return _probe(selection,ctx,workspace=workspace,budget_rows=budget_rows,credentials=credentials)


def _probe(selection, ctx, *, workspace, budget_rows=200, credentials=None, metadata_only=False):
    if selection.kind not in {'sqlite','postgres'} or isinstance(budget_rows,bool) or not isinstance(budget_rows,int) or not 1<=budget_rows<=10000:
        raise ValueError('database source and row budget 1..10000 required')
    allowed_options = {'timeout', 'sample_strategy'} if selection.kind == 'sqlite' else {'timeout'}
    if set(selection.options) - allowed_options or set(selection.requested_scope) - {'tables', 'schema'}:
        raise ValueError('unsupported database options; arbitrary SQL is prohibited')
    if selection.kind=='sqlite':
        if selection.options.get('sample_strategy', 'sequential') not in ('sequential', 'per_table'):
            raise ValueError('unsupported SQLite sample strategy')
        from ..adapters.sources.sqlite import collect
    else:
        from ..adapters.sources.postgres import collect
    tables,issues,raw_gaps=collect(selection,workspace,budget_rows,metadata_only=metadata_only,credentials=credentials)
    records=[];anchors={};record_keys=[];table_metadata=[];anchor_specs=[]
    binary_fields = {}
    for table in tables:
        name=table['name'];schema=table.get('schema');keys=table['primary_key'];rows=table['records']
        descriptor={k:v for k,v in table.items() if k not in {'records','sampled'}}
        descriptor.update({'rows_observed':len(rows),'sampled':table['sampled'],'uniqueness_scope':'not_checked' if metadata_only else 'sample' if table['sampled'] else 'full',
            'nulls':{c['name']:sum(row[c['name']] is None for row in rows) for c in table['columns']}})
        table_metadata.append(descriptor)
        if not keys: issues.append({'code':'stable_key_unavailable','table':name,'detail':'anchors use immutable snapshot row positions'})
        for ordinal,row in enumerate(rows):
            index=len(records);records.append(json_value(row))
            if selection.kind == 'sqlite':
                binary = [column for column, value in row.items() if isinstance(value, bytes)]
                if binary:
                    binary_fields[str(index)] = binary
            identity={'table':name,'keys':[typed_key(k,row[k]) for k in keys]}
            if schema: identity['schema']=schema
            record_keys.append(identity)
            anchor_keys={'table':name}
            if schema: anchor_keys['schema']=schema
            if keys and all(row[k] is not None for k in keys):
                anchor_keys['primary_key'] = json_value({k:row[k] for k in keys})
            else: anchor_keys['snapshot_row']=ordinal
            for field in row: anchor_specs.append((f'{index}.{field}',anchor_keys,field))
    storage_types = {'binary_fields': binary_fields} if binary_fields else {}
    revision,ref=snapshot(workspace,{'kind':selection.kind,'scope':selection.requested_scope,
                                    'tables':tables, **storage_types})
    for key,identity,field in anchor_specs:
        anchors[key]=[SourceAnchor(source_ref=selection.source_id,source_revision=revision,extraction_ref=ref,selector={'kind':'record_key','keys':identity,'field':field})]
    structure=[{k:v for k,v in table.items() if k not in {'records','sampled'}} for table in tables]
    sampled=any(table['sampled'] for table in tables)
    return SourceProfile(source_id=selection.source_id,source_revision=revision,kind=selection.kind,
        fields=list(dict.fromkeys(k for row in records for k in row)) or list(dict.fromkeys(c['name'] for t in tables for c in t['columns'])),
        records=records,anchors=anchors,total_partitions=None if metadata_only else len(tables)+len(raw_gaps),
        completed_partitions=[] if metadata_only else [((t.get('schema')+'.') if t.get('schema') else '')+t['name'] for t in tables],
        gaps=[CoverageGap(partition=p,code=c) for p,c in raw_gaps],sampled=sampled,issues=issues,
        metadata={'tables':table_metadata,'record_keys':record_keys,'snapshot_ref':ref,'structure_fingerprint':digest(structure),
            'completeness':'schema_only' if metadata_only else 'sampled' if sampled else 'partial' if raw_gaps else 'full',
            'statistics_scope':'schema_only' if metadata_only else 'observed_rows','extractor_version':'dataagent-database-probe@1',
            **storage_types})
