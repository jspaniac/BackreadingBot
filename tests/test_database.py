import pytest
import json
from copy import deepcopy

from typing import (
    Union
)
from tests.testing_constants import (
    TESTING_DATABASE, STANDARD_GUILD, STANDARD_GUILD_ID, STANDARD_GUILD_SAVED
)
from src.database import (
    Database
)


@pytest.fixture
def reset_db():
    with open(TESTING_DATABASE, 'w') as db_file:
        db_file.write(json.dumps({}))

@pytest.fixture
def simple_db():
    with open(TESTING_DATABASE, 'w') as db_file:
        db_file.write(json.dumps(STANDARD_GUILD_SAVED))

@pytest.fixture
def simple_db_with_thread():
    with open(TESTING_DATABASE, 'w') as db_file:
        db_file.write(json.dumps)

def test_create(reset_db):
    """
    Tests that the database is able to be created successfully
    """
    _ = Database(TESTING_DATABASE)
    assert True

def test_register_save(reset_db):
    """
    Tests that the database is able to register / save
    """
    db = Database(TESTING_DATABASE)
    db.register(STANDARD_GUILD_ID, STANDARD_GUILD)
    with open(TESTING_DATABASE, 'r') as db_file:
        assert db_file.readline() == json.dumps(STANDARD_GUILD_SAVED)

def test_load(simple_db):
    """
    Tests that the database is able to load from a file
    """
    db = Database(TESTING_DATABASE)
    with open(TESTING_DATABASE, 'w') as db_file:
        db_file.write(json.dumps({}))
    db.save()
    with open (TESTING_DATABASE, 'r') as db_file:
        assert db_file.readline() == json.dumps(STANDARD_GUILD_SAVED)

def test_contains(simple_db):
    """
    Tests the database contains method
    """
    assert STANDARD_GUILD_ID in Database(TESTING_DATABASE)

def test_guild_ids(simple_db):
    """
    Tests the database guild_ids method
    """
    db = Database(TESTING_DATABASE)
    assert db.guild_ids() == {str(STANDARD_GUILD_ID)}

def _test_get_methods(db: Database, method_name: str, guild_id: Union[int, str], field: str) -> bool:
    return getattr(db, method_name)(guild_id) == STANDARD_GUILD[field]

def test_get_admin(simple_db):
    """
    Tests the database get_admin method
    """
    assert _test_get_methods(Database(TESTING_DATABASE), 'get_admin', STANDARD_GUILD_ID, 'admin')

def test_get_channel(simple_db):
    """
    Tests the database get_channel method
    """
    assert _test_get_methods(Database(TESTING_DATABASE), 'get_channel', STANDARD_GUILD_ID, 'channel')

def test_get_token(simple_db):
    """
    Tests the database get_token method
    """
    assert _test_get_methods(Database(TESTING_DATABASE), 'get_token', STANDARD_GUILD_ID, 'token')

def test_get_course(simple_db):
    """
    Tests the database get_course method
    """
    assert _test_get_methods(Database(TESTING_DATABASE), 'get_course', STANDARD_GUILD_ID, 'course')

def test_get_role(simple_db):
    """
    Tests the database get_channel method
    """
    assert _test_get_methods(Database(TESTING_DATABASE), 'get_role', STANDARD_GUILD_ID, 'role')

def test_get_approval(simple_db):
    """
    Tests the database get_approval method
    """
    assert _test_get_methods(Database(TESTING_DATABASE), 'get_approval', STANDARD_GUILD_ID, 'approval')

def test_get_threads(simple_db):
    """
    Tests the database get_channel method
    """
    assert _test_get_methods(Database(TESTING_DATABASE), 'get_threads', STANDARD_GUILD_ID, 'threads')

def test_delete(simple_db):
    """
    Tests that the database is able to remove guild info
    """
    db = Database(TESTING_DATABASE)
    db.delete(STANDARD_GUILD_ID)
    with open(TESTING_DATABASE, 'r') as db_file:
        assert db_file.readline() == json.dumps({})

def _add_thread(db, guild_id, ed_id, discord_id):
    db.add_thread(guild_id, ed_id, discord_id)
    expected = deepcopy(STANDARD_GUILD_SAVED)
    expected[STANDARD_GUILD_ID]['threads']["0"] = 0
    return expected

def test_add_thread(simple_db):
    """
    Tests that the database can add a thread to a guild
    """
    db = Database(TESTING_DATABASE)
    expected = _add_thread(db, STANDARD_GUILD_ID, "0", 0)
    with open(TESTING_DATABASE, 'r') as db_file:
        assert db_file.readline() == json.dumps(expected)

def test_remove_thread(simple_db):
    """
    Tests that the database can remove a thread from a guild
    """
    db = Database(TESTING_DATABASE)
    expected = _add_thread(db, STANDARD_GUILD_ID, "0", 0)
    with open(TESTING_DATABASE, 'r') as db_file:
        assert db_file.readline() == json.dumps(expected)
    
    db.remove_thread(STANDARD_GUILD_ID, "0")
    with open(TESTING_DATABASE, 'r') as db_file:
        assert db_file.readline() == json.dumps(STANDARD_GUILD_SAVED)
