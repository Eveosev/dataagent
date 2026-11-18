"""Revalidate user assertions without presenting corrected values as extracted text."""
from dataagent_contracts.core.refs import SourceAnchor
from dataagent_contracts.ontology import Assertion,RoleBinding
from .mapping import _typed
from .identity import digest,entity_key
from .facts import relation_key


def revalidate_corrections(body,ontology,scope):
    mapping=body['mapping'];corrections=body.get('corrections',[])
    if not corrections:raise ValueError('no instance correction to revalidate')
    _,concept=ontology.resolve_concept(mapping.get('concept','') if isinstance(mapping,dict) else '')
    touched={(c['entity_id'],c['property']) for c in corrections}
    # Original extraction assertions stay in the archive; only selected facts are replaced.
    selected=[f for f in body['facts'] if not (f['relation'] in concept.properties and
        any((r['value'],f['relation']) in touched for r in f['role_bindings'] if r['role']=='subject'))]
    for correction in corrections:
        target=next((i for i in body['instances'] if i['id']==correction['entity_id']),None)
        if target is None:raise ValueError('correction entity no longer exists')
        prop=correction['property'];value=_typed(correction['value'],concept.properties[prop].value_type)
        if value is None:raise ValueError('null corrections require an explicit unresolved decision')
        evidence=SourceAnchor(source_ref=correction['decision_ref'].rsplit('@',1)[0],source_revision='1',
            selector={'kind':'json_pointer','pointer':'/decision/changes/value'})
        eid=target['id']
        roles=[RoleBinding(role='subject',value=eid,value_type='reference'),
               RoleBinding(role='value',value=value,value_type=concept.properties[prop].value_type)]
        relations=[(prop,roles)]
        binding=mapping['bindings'].get(prop)
        for fact in list(selected):
            role_map=mapping.get('relation_bindings',{}).get(fact['relation'],{})
            changed_roles=[role for role,b in role_map.items() if b==binding]
            refers=any(r['value_type']=='reference' and r['value']==eid for r in fact['role_bindings'])
            if changed_roles and refers:
                roles=[RoleBinding.model_validate({**r,'value':value} if r['role'] in changed_roles else r) for r in fact['role_bindings']]
                relations.append((fact['relation'],roles));selected.remove(fact)
        for relation,roles in relations:
            fid=relation_key(scope,relation,roles);aid='assertion:'+digest([fid,correction['decision_ref']])
            assertion=Assertion(id=aid,scope=scope,ontology_revision=body['ontology_revision'],relation=relation,
                role_bindings=roles,source_anchors=[evidence],mapping_revision=mapping['id']+'@'+mapping['revision'],
                extractor_version='user_correction',extensions={'review.decision':correction['decision_ref']})
            body['assertions'].append(assertion.model_dump(mode='json'))
            selected=[f for f in selected if f['id']!=fid]
            selected.append({'id':fid,'relation':relation,'role_bindings':[r.model_dump(mode='json') for r in roles],'assertion_refs':[aid]})
        target.setdefault('source_anchors',{}).setdefault(prop,[]).append(evidence.model_dump(mode='json'))
        target['unresolved']=[p for p in target['unresolved'] if p!=prop]
    body['facts']=selected
    corrected_props={c['property'] for c in corrections}
    resolvable={'ontology.conflicting_values','ontology.required_value_missing','ontology.conversion_failed'}
    body['issues']=[i for i in body['issues'] if not (i['code'] in resolvable and i.get('target') in corrected_props)]
    for instance in body['instances']:
        for name,definition in concept.properties.items():
            value=instance['values'].get(name)
            if definition.required and value is None:raise ValueError('required property remains unresolved')
            if value is not None:_typed(value,definition.value_type)
        keys=[(k,_typed(instance['values'].get(k),concept.properties[k].value_type)) for k in concept.identity_fields]
        if any(v is None or v=='' for _,v in keys):raise ValueError('identity remains unresolved')
        new_id=entity_key(scope,concept.entity_type,mapping['identity_strategy'],keys)
        old_id=instance['id']
        if new_id!=old_id:
            # Rebase candidate references; original source assertions remain available separately.
            instance['id']=new_id
            for fact in body['facts']:
                changed=False
                for role in fact['role_bindings']:
                    if role['value_type']=='reference' and role['value']==old_id:role['value']=new_id;changed=True
                if changed:
                    roles=[RoleBinding.model_validate(r) for r in fact['role_bindings']]
                    fid=relation_key(scope,fact['relation'],roles)
                    derived=[]
                    for aid in fact['assertion_refs']:
                        original=next(a for a in body['assertions'] if a['id']==aid)
                        updated={**original,'id':'assertion:'+digest([aid,new_id]),'role_bindings':fact['role_bindings']}
                        body['assertions'].append(updated);derived.append(updated['id'])
                    fact['id']=fid;fact['assertion_refs']=derived
    if len({i['id'] for i in body['instances']})!=len(body['instances']):
        raise ValueError('identity correction would merge objects; resolve the mapping explicitly')
    content={k:body[k] for k in ['ontology_revision','mapping','source_revisions','instances','issues']}
    if body.get('extensions'):content['extensions']=body['extensions']
    body['digest']=digest(content)
    body['review_state']='unreviewed'
    return body
