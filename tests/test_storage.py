import pytest
from yasin_core.storage import get_storage, set_storage
from yasin_core.storage.base import BaseStorage
from yasin_core.storage.json_file import JSONFileStorage


def test_base_storage_abc():
    with pytest.raises(TypeError):
        # BaseStorage is abstract and shouldn't be instantiated
        BaseStorage()  # type: ignore


def test_json_file_storage_operations(tmp_path):
    storage_file = tmp_path / "test_store.json"
    store = JSONFileStorage(filepath=str(storage_file))

    # Basic Operations
    assert store.get("non_existent") is None
    assert store.get("non_existent", "fallback") == "fallback"
    assert store.exists("non_existent") is False

    store.set("user", {"name": "Yousef", "role": "admin"})
    assert store.get("user") == {"name": "Yousef", "role": "admin"}
    assert store.exists("user") is True

    store.set("count", 42)
    assert store.get("count") == 42

    # Listing Keys
    keys = store.list_keys()
    assert len(keys) == 2
    assert "user" in keys
    assert "count" in keys

    # Deleting Key
    store.delete("count")
    assert store.get("count") is None
    assert store.exists("count") is False
    assert len(store.list_keys()) == 1

    # Clear
    store.clear()
    assert len(store.list_keys()) == 0


def test_json_file_storage_persistence(tmp_path):
    storage_file = tmp_path / "persist_store.json"
    store1 = JSONFileStorage(filepath=str(storage_file))

    store1.set("key1", "persisted_value")
    store1.set("key2", [1, 2, 3])

    # Instantiate another instance with the same file
    store2 = JSONFileStorage(filepath=str(storage_file))
    assert store2.get("key1") == "persisted_value"
    assert store2.get("key2") == [1, 2, 3]

    # Delete in one, check in another after reloading
    store1.delete("key1")

    store3 = JSONFileStorage(filepath=str(storage_file))
    assert store3.get("key1") is None
    assert store3.get("key2") == [1, 2, 3]


def test_global_storage_get_set(tmp_path):
    storage_file = tmp_path / "global_store.json"
    custom_store = JSONFileStorage(filepath=str(storage_file))

    set_storage(custom_store)
    retrieved = get_storage()

    assert retrieved is custom_store
