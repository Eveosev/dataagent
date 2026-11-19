"""Restricted deterministic conversions and evidence-preserving materialization."""
from dataclasses import dataclass
from datetime import date,datetime
from decimal import Decimal,localcontext
from zoneinfo import ZoneInfo
from dataagent_contracts.ontology import Assertion,EntityInstance,RelationFact,RoleBinding,FieldBinding,RelationDefinition
from .identity import canonical,digest,entity_key
from .facts import relation_key


@dataclass
class Materialized:
    instances: list[EntityInstance]
    assertions: list[Assertion]
    facts: list[RelationFact]
    issues: list[dict]


def _date_only(parsed):
    """A datetime can back a date only when its time part is exactly midnight."""
    if (parsed.hour,parsed.minute,parsed.second,parsed.microsecond)!=(0,0,0,0):
        raise ValueError('时间不是零点，不能按日期保存')
    return parsed.date().isoformat()


def convert(binding,record):
    if not isinstance(binding,FieldBinding):binding=FieldBinding.model_validate(binding)
    value=record.get(binding.source_field)
    options=binding.options
    if binding.transform=='combine':
        fields=options.get('fields',[binding.source_field])
        if any(record.get(k) is None for k in fields):return None
        return str(options.get('separator',' ')).join(str(record[k]) for k in fields)
    if binding.transform=='choose':
        allowed={'when_field','equals','then_field','else_field'}
        if set(options)!=allowed:raise ValueError('choose needs explicit equality and two source fields')
        field=options['then_field'] if record.get(options['when_field'])==options['equals'] else options['else_field']
        return record.get(field)
    if value is None:return None
    if binding.transform in {'decimal','minor_to_major','integer'}:
        raw=str(value)
        if options.get('strip_commas'):raw=raw.replace(',','')
        with localcontext() as ctx:
            ctx.prec=max(50,len(raw)+10)
            number=Decimal(raw)
            if not number.is_finite():raise ValueError('nonfinite number')
            if binding.transform=='minor_to_major':return number/Decimal(100)
            if binding.transform=='integer':
                if number!=number.to_integral_value():raise ValueError('non-integral value')
                return int(number)
            return number
    if binding.transform=='date':
        if 'format' in options:
            return _date_only(datetime.strptime(str(value),options['format']))
        text=str(value).strip()
        try:
            return date.fromisoformat(text).isoformat()
        except ValueError:
            # The Excel reader hands midnight date cells over as
            # ``YYYY-MM-DDTHH:MM:SS``.  A date binding without an explicit
            # format must still accept that ISO form; otherwise the column the
            # evidence inferred as ``date`` cannot be mapped at all.  A
            # non-midnight time is refused instead of being truncated.
            try:
                parsed=datetime.fromisoformat(text)
            except ValueError:
                raise ValueError('date value is not ISO 8601') from None
            return _date_only(parsed)
    if binding.transform=='datetime':
        parsed=datetime.strptime(str(value),options['format']) if 'format' in options else datetime.fromisoformat(str(value))
        if parsed.tzinfo is None:
            if 'timezone' not in options:raise ValueError('timezone required for naive datetime')
            parsed=parsed.replace(tzinfo=ZoneInfo(options['timezone']))
        return parsed.isoformat()
    if binding.transform=='enum':
        values=options.get('values',{})
        if str(value) not in values:raise ValueError('unknown enum value')
        return values[str(value)]
    if isinstance(value,(dict,list)):raise ValueError('nested value needs an explicit scalar mapping')
    return value


def _typed(value,kind):
    # String targets store text verbatim.  Date formatting belongs to the
    # explicit ``date`` transform; text that happens to look like a sheet
    # date (including identity fields) is never shortened by guesswork.
    if value is None:return None
    if kind=='string':return str(value)
    if kind=='reference':return str(value)
    if kind=='decimal':return convert(FieldBinding(source_field='x',transform='decimal'),{'x':value})
    if kind=='integer':return convert(FieldBinding(source_field='x',transform='integer'),{'x':value})
    if kind=='boolean':
        if isinstance(value,bool):return value
        if value in ('true','false'):return value=='true'
        raise ValueError('boolean must be true or false')
    if kind in {'date','datetime'}:return convert(FieldBinding(source_field='x',transform=kind),{'x':value})
    raise ValueError('unsupported target type')


def _validate_mapping(ontology, mapping, scope):
    if mapping.ontology_revision!=f'{ontology.id}@{ontology.revision}':raise ValueError('ontology revision mismatch')
    if mapping.scope not in {'workspace',scope}:raise ValueError('mapping scope mismatch')
    concept_name,concept=ontology.resolve_concept(mapping.concept)
    unknown=set(mapping.bindings)-concept.properties.keys()
    if unknown:raise ValueError('unknown ontology properties: '+','.join(sorted(unknown)))
    if set(mapping.relation_bindings)-ontology.relations.keys():raise ValueError('unknown ontology relation')
    for relation in mapping.relation_bindings:
        definition=ontology.relations[relation]
        if isinstance(definition,RelationDefinition) and definition.subject_concept!=concept_name:
            raise ValueError('relation subject must be the mapped concept')
    return concept_name,concept


def _disposition_index(dispositions):
    """Index audited source dispositions by source id.

    Only the two source-shaping actions change materialization:
    ``partition_not_applicable`` acknowledges a partition reported as an
    incomplete-read gap, and ``exclude_record`` removes one source record
    before mapping.  The audit entry keeps who/when/why; mapping only needs
    the action keys.
    """

    index={}
    for item in dispositions or []:
        if not isinstance(item,dict):continue
        source_id=item.get('source_id')
        if not source_id:continue
        entry=index.setdefault(source_id,{'excluded_rows':set(),'partitions':set()})
        if item.get('action')=='exclude_record':
            record=item.get('record')
            if isinstance(record,int) and not isinstance(record,bool):entry['excluded_rows'].add(record)
        elif item.get('action')=='partition_not_applicable':
            entry['partitions'].add(item.get('partition'))
    return index


def _coverage_gaps(source, partitions):
    """Gaps that still make a source incomplete after audited dispositions.

    A ``key_missing`` gap records an identity-unresolved record, not an unread
    partition: it is surfaced as a candidate and must not make the whole source
    look truncated.  A partition marked not applicable (for example a blank PDF
    page) is likewise acknowledged.
    """

    return [gap for gap in source.gaps
            if gap.code!='key_missing' and gap.partition not in partitions]


def _incomplete_source(source, partitions):
    gaps=_coverage_gaps(source,partitions)
    if gaps:return True
    if source.sampled:return True
    total=source.total_partitions
    if total is None:return source.coverage!='full'
    completed=set(source.completed_partitions)
    # Database partitions are table names, not integers.  Any audited
    # not-applicable partition counts as acknowledged coverage, whatever its
    # stable partition key type is.
    completed.update(partition for partition in partitions if partition is not None)
    return len(completed)<total


def materialize(ontology,mapping,observations,*,scope,source_mappings=None,dispositions=None):
    concept_name,concept=_validate_mapping(ontology, mapping, scope)
    disposed=_disposition_index(dispositions)
    issues=[]
    instances,assertions,facts={},[],{}
    for source in observations:
        if source_mappings is not None:
            mapping = source_mappings[source.source_id]
            concept_name,concept=_validate_mapping(ontology, mapping, scope)
        required={k for k,v in concept.properties.items() if v.required}
        source_disposition=disposed.get(source.source_id,{})
        excluded_rows=source_disposition.get('excluded_rows',set())
        not_applicable=source_disposition.get('partitions',set())
        issues.extend({'code':'ontology.required_binding_missing','target':k,'source_id':source.source_id}
                      for k in sorted(required-mapping.bindings.keys()))
        if mapping.source_fingerprint!=source.metadata.get('structure_fingerprint'):
            raise ValueError('source structure mismatch')
        if _incomplete_source(source,not_applicable):
            gaps=_coverage_gaps(source,not_applicable)
            issues.append({'code':'ontology.incomplete_source','source_id':source.source_id,
                           'coverage':source.coverage,
                           'partitions':[gap.partition for gap in gaps]})
        for rownum,row in enumerate(source.records):
            if rownum in excluded_rows:continue
            values,field_anchors,row_issues={},{},[]
            for target,binding in mapping.bindings.items():
                try:
                    value=_typed(convert(binding,row),concept.properties[target].value_type)
                    if value is not None:values[target]=value
                    fields=binding.options.get('fields',[binding.source_field])
                    field_anchors[target]=[a for f in fields for a in source.anchors.get(f'{rownum}.{f}',[])]
                    if value is not None and not field_anchors[target]:
                        row_issues.append({'code':'ontology.evidence_missing','target':target,'row':rownum})
                except (ValueError,ArithmeticError,KeyError) as exc:
                    row_issues.append({'code':'ontology.conversion_failed','target':target,'row':rownum,'detail':str(exc)})
            missing=sorted(required-values.keys())
            row_issues.extend({'code':'ontology.required_value_missing','target':target,'row':rownum}
                              for target in missing)
            keys=[(k,values.get(k)) for k in concept.identity_fields]
            unresolved_keys=any(v is None or v=='' for _,v in keys)
            eid=('candidate:'+digest([scope,source.source_id,source.source_revision,rownum]) if unresolved_keys
                else entity_key(scope,concept.entity_type,mapping.identity_strategy,keys))
            for issue in row_issues:
                issue['entity_id']=eid
                issue['source_id']=source.source_id
            issues.extend(row_issues)
            if unresolved_keys:
                issues.append({'code':'ontology.identity_unresolved','entity_id':eid,
                               'source_id':source.source_id,'row':rownum})
            extras={k:row.get(k) for k,disposition in mapping.unmapped.items() if disposition=='extension' and k in row}
            instance=instances.get(eid)
            if instance is None:
                instance=EntityInstance(id=eid,scope=scope,entity_type=concept.entity_type,values=values.copy(),source_anchors=field_anchors,
                    unresolved=missing,extensions={'source.unmapped':extras} if extras and source_mappings is None else None)
                instances[eid]=instance
            else:
                for k,v in values.items():
                    if k in instance.values and instance.values[k]!=v:
                        instance.values[k]=None
                        if k not in instance.unresolved:instance.unresolved.append(k)
                        issues.append({'code':'ontology.conflicting_values','entity_id':eid,
                                       'target':k,'source_id':source.source_id,'row':rownum})
                    elif k not in instance.values:instance.values[k]=v
                    instance.source_anchors.setdefault(k,[]).extend(field_anchors.get(k,[]))
            if extras and source_mappings is not None:
                if instance.extensions is None:
                    instance.extensions = {}
                by_source = instance.extensions.setdefault('source.unmapped_by_source', {})
                if source.source_id in by_source and by_source[source.source_id] != extras:
                    instance.extensions.setdefault('source.unmapped_additional_rows', []).append({
                        'source_id': source.source_id, 'row': rownum, 'values': extras,
                    })
                else:
                    by_source[source.source_id] = extras
            def assertion(relation,roles,evidence):
                if not evidence:return
                fid=relation_key(scope,relation,roles)
                aid='assertion:'+digest([fid,source.source_id,source.source_revision,rownum,f'{mapping.id}@{mapping.revision}'])
                a=Assertion(id=aid,scope=scope,ontology_revision=mapping.ontology_revision,relation=relation,
                    role_bindings=roles,source_anchors=evidence,mapping_revision=f'{mapping.id}@{mapping.revision}',
                    extractor_version=source.metadata.get('extractor_version','unknown'))
                assertions.append(a)
                if fid not in facts:facts[fid]=RelationFact(id=fid,relation=relation,role_bindings=roles,assertion_refs=[])
                if aid not in facts[fid].assertion_refs:facts[fid].assertion_refs.append(aid)
            for target,value in values.items():
                assertion(target,[RoleBinding(role='subject',value=eid,value_type='reference'),
                    RoleBinding(role='value',value=value,value_type=concept.properties[target].value_type)],field_anchors[target])
            for relation,bindings in mapping.relation_bindings.items():
                order=ontology.relation_roles(relation)
                if set(bindings)!=set(order):raise ValueError('relation role mismatch')
                roles,evidence=[],[]
                try:
                    for role in order:
                        binding=bindings[role]
                        value=eid if binding.source_field=='$entity' else convert(binding,row)
                        if value is None:raise ValueError('relation role has no value')
                        kind='reference' if binding.source_field=='$entity' else ('decimal' if isinstance(value,Decimal) else 'string')
                        roles.append(RoleBinding(role=role,value=value,value_type=kind))
                        evidence.extend(source.anchors.get(f'{rownum}.{binding.source_field}',[]))
                    assertion(relation,roles,evidence)
                except ValueError as exc:issues.append({'code':'ontology.relation_unresolved','target':relation,
                    'row':rownum,'entity_id':eid,'source_id':source.source_id,'detail':str(exc)})
    return Materialized(list(instances.values()),assertions,list(facts.values()),issues)
