import pytest
from dataagent_runtime.adapters.workbench_sqlite import SqliteWorkbenchStore
from dataagent_runtime.ports.workbench_store import ChangeSet, Write, VersionConflict


def test_restart_retains_session(tmp_path):
    path=tmp_path/'workbench.sqlite3'
    store=SqliteWorkbenchStore(path)
    receipt=store.commit(ChangeSet(writes=[Write('session','s','tenant',{'phase':'queued'})],
        events=[{'session_id':'s','type':'created'}]))
    assert receipt.revisions['session:s']=='1'
    again=SqliteWorkbenchStore(path)
    assert again.current('session','s',scope='tenant')['body']['phase']=='queued'
    assert again.current('session','s',scope='other') is None
    assert again.events('s',0,scope='tenant')['items'][0]['type']=='created'


def test_concurrent_edit_returns_version_conflict(tmp_path):
    store=SqliteWorkbenchStore(tmp_path/'db')
    store.commit(ChangeSet(writes=[Write('session','s','tenant',{'v':1})]))
    store.commit(ChangeSet(writes=[Write('session','s','tenant',{'v':2},'1')]))
    with pytest.raises(VersionConflict):
        store.commit(ChangeSet(writes=[Write('job','j','tenant',{'state':'bad'}),
            Write('session','s','tenant',{'v':3},'1')],events=[{'session_id':'s','type':'bad'}]))
    assert store.current('job','j',scope='tenant') is None
    assert store.get('session','s','1',scope='tenant')['body']['v']==1
    assert store.current('session','s',scope='tenant')['body']['v']==2
    assert store.events('s',0,scope='tenant')['items']==[]


def test_outbox_and_record_are_atomic_and_request_keys_are_unique(tmp_path):
    store=SqliteWorkbenchStore(tmp_path/'db')
    cs=ChangeSet(writes=[Write('session','s','tenant',{})],
        outbox=[{'request_key':'submit-1','scope':'tenant','payload':{'v':1}}])
    store.commit(cs)
    with pytest.raises(VersionConflict):
        store.commit(ChangeSet(writes=[Write('session','s','tenant',{'v':2},'1')],outbox=cs.outbox))
    assert store.current('session','s',scope='tenant')['revision']=='1'


def test_event_pagination_is_scoped_and_ordered(tmp_path):
    store=SqliteWorkbenchStore(tmp_path/'db')
    store.commit(ChangeSet(writes=[Write('session','a','A',{}), Write('session','b','B',{})],
        events=[{'session_id':'a','type':'one'},{'session_id':'b','type':'secret'},
                {'session_id':'a','type':'two'}]))
    first=store.events('a',0,scope='A',limit=1)
    assert [e['type'] for e in first['items']]==['one']
    assert first['has_more']
    assert [e['type'] for e in store.events('a',first['cursor'],scope='A')['items']]==['two']
    assert store.events('b',0,scope='A')['items']==[]
