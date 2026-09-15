"""Use real SQLAlchemy queries to test owner/source isolation, including legacy rows."""
import json
import sys
import types

import pytest
from sqlalchemy import Column, String, Text, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from controllers.query.query_retrieval import expand_owned_dependencies
from controllers.query.query_validation import QueryValidationError


def catalog(monkeypatch):
    engine = create_engine('sqlite://')
    session = sessionmaker(bind=engine)()
    base = declarative_base()
    class Query:
        def __get__(self, instance, owner):
            return session.query(owner)
    class Card(base):
        __tablename__ = 'cards'
        query = Query()
        doc_id = Column(String, primary_key=True)
        user_id = Column(String)
        datasource_id = Column(String)
        table_name = Column(String)
        card_data = Column(Text)
    class Schema(base):
        __tablename__ = 'schemas'
        query = Query()
        id = Column(String, primary_key=True)
        user_id = Column(String)
        table_name = Column(String)
        schema_name = Column(String)
        database_name = Column(String)
        db_type = Column(String)
    class Source(base):
        __tablename__ = 'sources'
        query = Query()
        id = Column(String, primary_key=True)
        user_id = Column(String)
        connect_name = Column(String)
    base.metadata.create_all(engine)
    for module, name, value in [
        ('models.datacards_datasource', 'DataCardDataSource', Card),
        ('models.user_datasource_schema', 'UserDatasourceSchema', Schema),
        ('models.datasource_infos', 'DatasourceInfo', Source),
        ('extensions.ext_database', 'db', types.SimpleNamespace(session=session))]:
        stub = types.ModuleType(module)
        setattr(stub, name, value)
        monkeypatch.setitem(sys.modules, module, stub)
    session.add_all([Source(id='ds1', user_id='owner', connect_name='selected'),
                     Source(id='ds2', user_id='owner', connect_name='unselected'),
                     Source(id='ds3', user_id='other', connect_name='foreign')])
    def card(doc, owner, ds, conn, table, ref=None, legacy=False, schema=None):
        value = {'DocInfo': {'connect_name': conn}, 'SQLMeta': {'table': table, 'foreign_keys': [{'ref_table': ref}] if ref else []}}
        session.add(Schema(id=doc, user_id=owner, table_name=table, schema_name=schema,
                           database_name='fixture', db_type='postgresql'))
        session.add(Card(doc_id=doc, user_id=None if legacy else owner,
                         datasource_id=None if legacy else ds, table_name=table, card_data=json.dumps(value)))
        return value
    return session, card, Source


def test_dependency_lookup_respects_owner_source_and_case(monkeypatch):
    session, card, _ = catalog(monkeypatch)
    initial = card('team', 'owner', 'ds1', 'selected', 'Team', 'People')
    allowed = card('people', 'owner', 'ds1', 'selected', 'People', legacy=True)
    foreign = card('foreign', 'other', 'ds3', 'foreign', 'People', legacy=True)
    unselected = card('unselected', 'owner', 'ds2', 'unselected', 'People')
    session.commit()
    result = {'doc_ids': ['team', 'foreign', 'unselected'], 'data_card_results': [initial, foreign, unselected]}
    expand_owned_dependencies(result, 'owner', ['ds1'])
    assert result['doc_ids'] == ['team', 'people']
    assert result['data_card_results'] == [initial, allowed]


@pytest.mark.parametrize('qualified', [True, False])
def test_same_table_in_different_schemas_requires_exact_reference(monkeypatch, qualified):
    session, card, _ = catalog(monkeypatch)
    initial = card('team', 'owner', 'ds1', 'selected', 'team', 'hr.people' if qualified else 'people')
    if qualified:
        initial['SQLMeta']['foreign_keys'].append({'ref_table': 'crm.people'})
    card('hr', 'owner', 'ds1', 'selected', 'people', schema='hr')
    card('crm', 'owner', 'ds1', 'selected', 'people', schema='crm')
    session.commit()
    result = {'doc_ids': ['team'], 'data_card_results': [initial]}
    if qualified:
        expand_owned_dependencies(result, 'owner', ['ds1'])
        assert set(result['doc_ids']) == {'team', 'hr', 'crm'}
    else:
        with pytest.raises(QueryValidationError, match='歧义'):
            expand_owned_dependencies(result, 'owner', ['ds1'])


def test_duplicate_connection_names_cannot_select_an_unselected_connection(monkeypatch):
    session, card, source = catalog(monkeypatch)
    initial = card('team', 'owner', 'ds1', 'selected', 'team', 'people')
    session.add(source(id='duplicate', user_id='owner', connect_name='selected'))
    session.commit()
    with pytest.raises(QueryValidationError, match='连接名称重复'):
        expand_owned_dependencies({'doc_ids': ['team'], 'data_card_results': [initial]}, 'owner', ['ds1'])


def test_empty_retrieval_does_not_expand_arbitrary_tables(monkeypatch):
    # Empty result has no relationship roots. Use the same graph closure without ORM.
    from controllers.query.query_retrieval import expand_dependencies
    def load(*args):
        raise AssertionError('No lookup should occur without a recalled card')
    result = {'doc_ids': [], 'data_card_results': []}
    expand_dependencies(result, load)
    assert result['doc_ids'] == []
