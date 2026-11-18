"""Object page projections: values, evidence and drafts read from stored revisions.

Drafts stay drafts: an ontology proposal is surfaced as ``ontology_draft`` and never
registered as a new formal ontology revision until it is separately reviewed.

The object page also compares a retained correction with the value the current
mapping computes on its own.  That projection is read-only: it never rewrites a
correction or a mapping, so the page can offer an explicit adoption instead of
silently overriding either decision.
"""
import json

from dataagent_contracts.ontology import FieldBinding, MappingSpec
from dataagent_ontology.mapping import _typed, materialize
from pydantic_core import to_jsonable_python


def _binding_key(binding):
    if binding is None:
        return None
    try:
        return FieldBinding.model_validate(binding).model_dump(
            mode='json', exclude_defaults=True, exclude_none=True)
    except (TypeError, ValueError):
        return binding


class ViewService:
    def __init__(self, wb):
        self.wb = wb
        # A correction's origin mapping never changes once its preview is stored.
        self._origins = {}
        # Materialization is deterministic for one immutable preview revision.
        self._instances = {}

    def _preview(self, session):
        wb = self.wb
        if 'preview' not in session.selected_versions:
            return None
        id, rev = session.selected_versions['preview'].rsplit('@', 1)
        row = wb.store.get('preview', id, rev, scope=wb.scope)
        if row is None:
            raise ValueError('selected preview is missing')
        return row['body']

    def _mapping_instances(self, session, body):
        """Materialize the current mapping without corrections.

        The stored preview carries corrected values.  Recomputing the mapping
        alone recovers the value the revised mapping produces, which the page
        displays next to the retained correction.
        """
        mapping = (body or {}).get('mapping')
        if not mapping:
            return {}
        cache_key = session.selected_versions.get('preview')
        if cache_key in self._instances:
            return self._instances[cache_key]
        profiles = self.wb.intake._profiles(session)
        if not profiles:
            return {}
        try:
            ontology, _, _ = self.wb.intake._target(session)
            primary = MappingSpec.model_validate(mapping)
            extensions = body.get('extensions') or {}
            source_mappings = extensions.get('intake.source_mappings')
            dispositions = extensions.get('intake.dispositions')
            if source_mappings:
                result = materialize(
                    ontology, primary, profiles, scope=self.wb.scope,
                    source_mappings={key: MappingSpec.model_validate(value)
                                     for key, value in source_mappings.items()},
                    dispositions=dispositions)
            else:
                result = materialize(ontology, primary, profiles,
                                     scope=self.wb.scope, dispositions=dispositions)
        except (KeyError, TypeError, ValueError):
            # A projection must never break the page; without a comparable
            # value the page simply keeps showing the retained correction.
            return {}
        instances = {instance.id: instance for instance in result.instances}
        if cache_key is not None:
            self._instances[cache_key] = instances
        return instances

    def _origin_mapping(self, decision_ref):
        """Return the preview body active when a correction was first saved."""
        if not decision_ref:
            return None
        if decision_ref in self._origins and self._origins[decision_ref] is not None:
            return self._origins[decision_ref]
        found = None
        cursor = 0
        while True:
            rows = self.wb.store.query('preview', self.wb.scope, cursor=cursor, limit=500)
            for row in rows:
                body = row['body']
                if not any(item.get('decision_ref') == decision_ref
                           for item in body.get('corrections') or []):
                    continue
                mapping = body.get('mapping') or {}
                try:
                    revision = int(str(mapping.get('revision')))
                except (TypeError, ValueError):
                    continue
                if found is None or revision < found[0]:
                    found = (revision, body)
            if len(rows) < 500:
                break
            cursor += 500
        self._origins[decision_ref] = found[1] if found else None
        return self._origins[decision_ref]

    @staticmethod
    def _property_bindings(body, prop):
        """Canonical bindings that could provide one property in a preview."""
        mappings = [(body or {}).get('mapping') or {}]
        mappings.extend(((body or {}).get('extensions') or {})
                        .get('intake.source_mappings', {}).values())
        keys = []
        for mapping in mappings:
            key = _binding_key((mapping.get('bindings') or {}).get(prop))
            if key is not None:
                keys.append(json.dumps(key, sort_keys=True, ensure_ascii=False, default=str))
        return sorted(keys)

    def _mapping_changed(self, origin, current, prop):
        return self._property_bindings(origin, prop) != self._property_bindings(current, prop)

    def _correction_views(self, session, body):
        """Latest correction per object property that the mapping now contradicts."""
        corrections = (body or {}).get('corrections') or []
        if not corrections:
            return []
        latest = {}
        for correction in corrections:
            entity_id, prop = correction.get('entity_id'), correction.get('property')
            if entity_id is not None and prop is not None:
                latest[(entity_id, prop)] = correction
        instances = self._mapping_instances(session, body)
        if not instances:
            return []
        current = body.get('mapping') or {}
        _, _, concept = self.wb.intake._target(session)
        views = []
        for (entity_id, prop), correction in latest.items():
            definition = concept.properties.get(prop)
            instance = instances.get(entity_id)
            if definition is None or instance is None:
                continue
            mapping_value = instance.values.get(prop)
            if mapping_value is None:
                continue
            try:
                corrected = _typed(correction.get('value'), definition.value_type)
            except (TypeError, ValueError, ArithmeticError):
                continue
            if corrected == mapping_value:
                continue
            origin = self._origin_mapping(correction.get('decision_ref'))
            if origin is None or not self._mapping_changed(origin, body, prop):
                continue
            views.append({
                'decision_ref': correction.get('decision_ref'),
                'entity_id': entity_id,
                'property': prop,
                'value': to_jsonable_python(corrected),
                'mapping_value': to_jsonable_python(mapping_value),
                'mapping_revision': f"{current.get('id')}@{current.get('revision')}",
                'mapping_changed': True,
            })
        return views

    def correction_views(self, session_id, ctx):
        s = self.wb.sessions.get(session_id, ctx)
        return self._correction_views(s, self._preview(s))

    def mapping_value(self, session_id, entity_id, prop, ctx):
        """Value the current mapping computes for one object property."""
        s = self.wb.sessions.get(session_id, ctx)
        body = self._preview(s)
        if prop not in self.wb.intake._target(s)[2].properties:
            raise ValueError('unknown target property')
        instance = self._mapping_instances(s, body).get(entity_id)
        if instance is None:
            raise ValueError('correction target is not in the current preview')
        return instance.values.get(prop)

    def object_page(self, session_id, ctx):
        wb = self.wb
        s = wb.sessions.get(session_id, ctx)
        body = self._preview(s)
        profiles = wb.intake._profiles(s)
        names = {source.source_id: str(source.options.get('display_name') or source.locator_ref)
                 for source in s.sources}
        sources = [profile.model_dump(mode='json') | {'display_name': names.get(profile.source_id, profile.source_id)}
                   for profile in profiles]
        conflicts = wb.intake.conflict_details(s, body) if body else []
        conflicts_by_object = {}
        for item in conflicts:
            conflicts_by_object.setdefault(item['entity_id'], []).append(item)
        objects = []
        for instance in (body or {}).get('instances', []):
            evidence = {prop: [{'source_id': anchor['source_ref'], 'selector': anchor['selector']}
                               for anchor in anchors] for prop, anchors in (instance.get('source_anchors') or {}).items()}
            objects.append({'id': instance['id'], 'entity_type': instance.get('entity_type'),
                            'values': instance.get('values', {}), 'evidence': evidence,
                            'unresolved': instance.get('unresolved', []),
                            'conflicts': conflicts_by_object.get(instance['id'], []),
                            'extensions': instance.get('extensions')})
        draft = wb.store.current('ui_draft', s.id, scope=wb.scope)
        mapping = body.get('mapping') if body else None
        inheritance = body.get('inheritance') if body else None
        if body and inheritance is None:
            inheritance = wb.intake.inheritance_hint(s, body)
        ontology, concept_name, _ = wb.intake._target(s)
        return {'session': s.model_dump(mode='json'), 'ontology': ontology.model_dump(mode='json'),
                'ontology_revision': f'{ontology.id}@{ontology.revision}',
                'ontology_concept': concept_name,
                'ontology_draft': body.get('ontology_draft') if body else None,
                'sources': sources, 'objects': objects,
                'corrections': (body or {}).get('corrections', []),
                'correction_views': self._correction_views(s, body),
                'issues': (body or {}).get('issues') if body else list(s.issues),
                'conflicts': conflicts,
                'dispositions': wb.intake.disposition_entries(s),
                'disposition_options': wb.intake.disposition_options(s, body),
                'suspended': (body or {}).get('suspended', []),
                'unidentified_records': (body or {}).get('unidentified_records', []),
                'partial_save': (body or {}).get('partial_save', []),
                'inheritance': inheritance,
                'review_state': body.get('review_state') if body else None,
                'preview_ref': s.selected_versions.get('preview'),
                'mapping_revision': f"{mapping['id']}@{mapping['revision']}" if mapping else None,
                'draft': draft['body'] if draft else {}}
