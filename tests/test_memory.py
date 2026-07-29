import pytest
from yasin_core.memory import (
    InMemoryShortTermMemory,
    InMemoryLongTermMemory,
    StorageLongTermMemory,
)
from yasin_core.storage.json_file import JSONFileStorage


def test_in_memory_short_term_memory():
    mem = InMemoryShortTermMemory()

    assert mem.get("key1") is None
    assert mem.get("key1", "default") == "default"

    mem.set("key1", "value1")
    assert mem.get("key1") == "value1"

    mem.set("key2", {"nested": "data"})
    assert mem.get("key2") == {"nested": "data"}

    mem.delete("key1")
    assert mem.get("key1") is None
    assert mem.get("key2") is not None

    mem.clear()
    assert mem.get("key2") is None


def test_in_memory_long_term_memory():
    mem = InMemoryLongTermMemory()

    mem.set("user_profile_1", "Yousef is a software engineer")
    mem.set("user_profile_2", "Jules is an expert AI agent")
    mem.set("metadata", {"tags": ["AI", "Ecosystem"], "version": 0.2})
    mem.set("framework_list", ["Yasin Core", "YasinRelay", "YasinHub"])

    # Search by key
    results_key = mem.search("user_profile")
    assert len(results_key) == 2
    keys = {r["key"] for r in results_key}
    assert "user_profile_1" in keys
    assert "user_profile_2" in keys

    # Search by string value (case-insensitive)
    results_val = mem.search("AI agent")
    assert len(results_val) == 1
    assert results_val[0]["key"] == "user_profile_2"

    # Search inside nested dict
    results_dict = mem.search("ecosystem")
    assert len(results_dict) == 1
    assert results_dict[0]["key"] == "metadata"

    # Search inside list
    results_list = mem.search("YasinRelay")
    assert len(results_list) == 1
    assert results_list[0]["key"] == "framework_list"

    mem.delete("user_profile_1")
    assert len(mem.search("Yousef")) == 0

    mem.clear()
    assert len(mem.search("Jules")) == 0


def test_storage_backed_long_term_memory(tmp_path):
    storage_file = tmp_path / "test_memory_storage.json"
    storage = JSONFileStorage(filepath=str(storage_file))
    mem = StorageLongTermMemory(storage=storage)

    mem.set("doc1", "The quick brown fox jumps over the lazy dog")
    mem.set("doc2", {"title": "Python Programming", "rating": 5})

    # Search
    assert len(mem.search("brown fox")) == 1
    assert mem.search("brown fox")[0]["key"] == "doc1"

    assert len(mem.search("Programming")) == 1
    assert mem.search("Programming")[0]["key"] == "doc2"

    # Verify persistence
    storage2 = JSONFileStorage(filepath=str(storage_file))
    mem2 = StorageLongTermMemory(storage=storage2)
    assert mem2.get("doc1") == "The quick brown fox jumps over the lazy dog"
    assert len(mem2.search("Programming")) == 1
