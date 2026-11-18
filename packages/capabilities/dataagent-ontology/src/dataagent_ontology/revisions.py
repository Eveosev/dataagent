"""Structural difference between two registered revisions of one ontology.

A published ontology may publish a new revision from a new discovery draft.
The human who confirms that revision sees exactly what changes against the
revision that is current now: concepts and properties added or deleted, a
property whose value type or requiredness changed, an identity definition that
moved, and relations added, deleted or re-pointed.  Deleting a property or
changing the identity fields is destructive: the old revision's published
objects stay on the old revision and are not migrated, so the confirmation
needs an explicit second acknowledgement.

The result is plain JSON so it can be stored in a candidate, a registry
history entry and a publication audit without a second schema.
"""
from __future__ import annotations

from dataagent_contracts.ontology import OntologyRevision, RelationDefinition


def _relation_shape(relation):
    if isinstance(relation, RelationDefinition):
        return {'roles': list(relation.roles),
                'subject_concept': relation.subject_concept,
                'object_concept': relation.object_concept}
    return {'roles': list(relation), 'subject_concept': '', 'object_concept': ''}


def _property_shape(definition):
    return {'value_type': definition.value_type,
            'required': bool(definition.required)}


def definition_diff(previous: OntologyRevision, current: OntologyRevision) -> dict:
    """What one revision changes against the revision that came before it."""
    before = previous.concepts
    after = current.concepts
    added_concepts = sorted(set(after) - set(before))
    removed_concepts = sorted(set(before) - set(after))
    changed_concepts = []
    added_properties = []
    removed_properties = []
    retyped_properties = []
    required_changes = []
    identity_changes = []

    for name in sorted(set(before) & set(after)):
        old, new = before[name], after[name]
        if old.entity_type != new.entity_type:
            changed_concepts.append({'concept': name,
                                     'before': old.entity_type,
                                     'after': new.entity_type})
        old_props, new_props = old.properties, new.properties
        for prop in sorted(set(new_props) - set(old_props)):
            added_properties.append({'concept': name, 'property': prop,
                                     'value_type': new_props[prop].value_type})
        for prop in sorted(set(old_props) - set(new_props)):
            removed_properties.append({'concept': name, 'property': prop,
                                       'value_type': old_props[prop].value_type})
        for prop in sorted(set(old_props) & set(new_props)):
            old_type = old_props[prop].value_type
            new_type = new_props[prop].value_type
            if old_type != new_type:
                retyped_properties.append({'concept': name, 'property': prop,
                                           'before': old_type, 'after': new_type})
            old_required = bool(old_props[prop].required)
            new_required = bool(new_props[prop].required)
            if old_required != new_required:
                required_changes.append({'concept': name, 'property': prop,
                                         'before': old_required,
                                         'after': new_required})
        old_identity = list(old.identity_fields)
        new_identity = list(new.identity_fields)
        if old_identity != new_identity:
            identity_changes.append({'concept': name,
                                     'before': old_identity,
                                     'after': new_identity})

    old_relations = {name: _relation_shape(relation)
                     for name, relation in previous.relations.items()}
    new_relations = {name: _relation_shape(relation)
                     for name, relation in current.relations.items()}
    added_relations = sorted(set(new_relations) - set(old_relations))
    removed_relations = sorted(set(old_relations) - set(new_relations))
    changed_relations = []
    for name in sorted(set(old_relations) & set(new_relations)):
        if old_relations[name] != new_relations[name]:
            changed_relations.append({'relation': name,
                                      'before': old_relations[name],
                                      'after': new_relations[name]})

    # A removed concept removes all its properties; identity changes
    # invalidate the keys old published objects were identified by.  Neither
    # is migrated, so both need the no-migration acknowledgement.
    destructive = bool(removed_concepts or removed_properties
                       or identity_changes)

    summary = []
    summary.extend('新增概念 %s' % name for name in added_concepts)
    summary.extend('删除概念 %s' % name for name in removed_concepts)
    summary.extend('概念 %s 实体类型 %s → %s'
                   % (item['concept'], item['before'], item['after'])
                   for item in changed_concepts)
    summary.extend('%s.%s 新增属性（%s）'
                   % (item['concept'], item['property'], item['value_type'])
                   for item in added_properties)
    summary.extend('%s.%s 删除属性（%s）'
                   % (item['concept'], item['property'], item['value_type'])
                   for item in removed_properties)
    summary.extend('%s.%s 值类型 %s → %s'
                   % (item['concept'], item['property'],
                      item['before'], item['after'])
                   for item in retyped_properties)
    summary.extend('%s.%s 必需性 %s → %s'
                   % (item['concept'], item['property'],
                      '必需' if item['before'] else '可选',
                      '必需' if item['after'] else '可选')
                   for item in required_changes)
    summary.extend('%s 身份字段 %s → %s'
                   % (item['concept'], ' + '.join(item['before']) or '（无）',
                      ' + '.join(item['after']) or '（无）')
                   for item in identity_changes)
    summary.extend('新增关系 %s' % name for name in added_relations)
    summary.extend('删除关系 %s' % name for name in removed_relations)
    summary.extend('关系 %s 端点或角色调整' % item['relation']
                   for item in changed_relations)

    return {
        'previous_revision': previous.revision,
        'revision': current.revision,
        'destructive': destructive,
        'summary': summary,
        'added_concepts': added_concepts,
        'removed_concepts': removed_concepts,
        'changed_concepts': changed_concepts,
        'added_properties': added_properties,
        'removed_properties': removed_properties,
        'retyped_properties': retyped_properties,
        'required_changes': required_changes,
        'identity_changes': identity_changes,
        'added_relations': added_relations,
        'removed_relations': removed_relations,
        'changed_relations': changed_relations,
    }
