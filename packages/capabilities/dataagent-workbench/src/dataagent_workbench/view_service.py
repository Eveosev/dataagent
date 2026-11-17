"""Object page projections: values, evidence and drafts read from stored revisions.

Drafts stay drafts: an ontology proposal is surfaced as ``ontology_draft`` and never
registered as a new formal ontology revision until it is separately reviewed.
"""


class ViewService:
    def __init__(self,wb):self.wb=wb

    def _preview(self,session):
        wb=self.wb
        if 'preview' not in session.selected_versions:return None
        id,rev=session.selected_versions['preview'].rsplit('@',1)
        row=wb.store.get('preview',id,rev,scope=wb.scope)
        if row is None:raise ValueError('selected preview is missing')
        return row['body']

    def object_page(self,session_id,ctx):
        wb=self.wb;s=wb.sessions.get(session_id,ctx)
        body=self._preview(s)
        profiles=wb.intake._profiles(s)
        names={source.source_id:str(source.options.get('display_name') or source.locator_ref)
            for source in s.sources}
        sources=[profile.model_dump(mode='json')|{'display_name':names.get(profile.source_id,profile.source_id)}
            for profile in profiles]
        objects=[]
        for instance in (body or {}).get('instances',[]):
            evidence={prop:[{'source_id':anchor['source_ref'],'selector':anchor['selector']}
                for anchor in anchors] for prop,anchors in (instance.get('source_anchors') or {}).items()}
            objects.append({'id':instance['id'],'entity_type':instance.get('entity_type'),
                'values':instance.get('values',{}),'evidence':evidence,
                'unresolved':instance.get('unresolved',[]),'extensions':instance.get('extensions')})
        draft=wb.store.current('ui_draft',s.id,scope=wb.scope)
        mapping=body.get('mapping') if body else None
        return {'session':s.model_dump(mode='json'),'ontology':wb.definition.model_dump(mode='json'),
            'ontology_revision':f'{wb.definition.id}@{wb.definition.revision}',
            'ontology_draft':body.get('ontology_draft') if body else None,
            'sources':sources,'objects':objects,
            'corrections':(body or {}).get('corrections',[]),
            'issues':(body or {}).get('issues') if body else list(s.issues),
            'review_state':body.get('review_state') if body else None,
            'preview_ref':s.selected_versions.get('preview'),
            'mapping_revision':f"{mapping['id']}@{mapping['revision']}" if mapping else None,
            'draft':draft['body'] if draft else {}}
