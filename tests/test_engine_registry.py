import json

import pytest

import agents.meta_data_fiter.engine_registry as registry


@pytest.fixture(autouse=True)
def isolated_registry(tmp_path, monkeypatch):
    """Points DATA_PATH/CACHE_DIR at a tiny temp fixture instead of the real 25k+
    record catalogue (a full build takes several seconds) and resets the
    module-level singleton, which would otherwise leak across tests."""
    data_path = tmp_path / "egyptian-drugs.json"
    data_path.write_text(
        json.dumps([{"commercial_name_en": "PANADOL", "commercial_name_ar": "بانادول",
                     "scientific_name": "PARACETAMOL", "manufacturer": "GSK",
                     "drug_class": "ANALGESIC", "route": "ORAL.SOLID", "price_egp": 20.0}]),
        encoding="utf-8",
    )
    cache_dir = tmp_path / "cache"

    monkeypatch.setattr(registry, "DATA_PATH", data_path)
    monkeypatch.setattr(registry, "CACHE_DIR", cache_dir)
    monkeypatch.setattr(registry, "_commercial_engine", registry._UNSET)

    return data_path, cache_dir


def test_first_call_builds_and_writes_a_cache_file(isolated_registry):
    data_path, cache_dir = isolated_registry

    engine = registry.get_commercial_engine()

    assert engine.records[0]["commercial_name_en"] == "PANADOL"
    cache_files = list(cache_dir.glob("commercial_engine_*.pkl"))
    assert len(cache_files) == 1


def test_second_call_reuses_the_same_in_memory_engine(isolated_registry):
    first = registry.get_commercial_engine()
    second = registry.get_commercial_engine()
    assert first is second


def test_fresh_process_loads_from_the_existing_cache_file(isolated_registry, monkeypatch):
    registry.get_commercial_engine()  # builds + writes the cache

    # Simulate a fresh process: no in-memory singleton yet.
    monkeypatch.setattr(registry, "_commercial_engine", registry._UNSET)

    from agents.meta_data_fiter import search_engine as search_engine_module
    original_load_data = search_engine_module.MedicineSearchEngine.load_data

    def _fail_if_called(self, source):
        raise AssertionError("load_data() should not run again -- the cache should be loaded instead")

    monkeypatch.setattr(search_engine_module.MedicineSearchEngine, "load_data", _fail_if_called)
    try:
        engine = registry.get_commercial_engine()
    finally:
        monkeypatch.setattr(search_engine_module.MedicineSearchEngine, "load_data", original_load_data)

    assert engine.records[0]["commercial_name_en"] == "PANADOL"


def test_source_file_change_triggers_a_rebuild_and_drops_the_stale_cache(isolated_registry):
    data_path, cache_dir = isolated_registry

    registry.get_commercial_engine()
    old_cache_files = list(cache_dir.glob("commercial_engine_*.pkl"))
    assert len(old_cache_files) == 1

    # Change the source file's content (and therefore its hash) and reset the
    # in-memory singleton, as if the process restarted after a data update.
    data_path.write_text(
        json.dumps([{"commercial_name_en": "AUGMENTIN", "commercial_name_ar": "أوجمينتين",
                     "scientific_name": "AMOXICILLIN", "manufacturer": "GSK",
                     "drug_class": "ANTIBIOTIC", "route": "ORAL.SOLID", "price_egp": 30.0}]),
        encoding="utf-8",
    )
    registry._commercial_engine = registry._UNSET

    engine = registry.get_commercial_engine()

    assert engine.records[0]["commercial_name_en"] == "AUGMENTIN"
    new_cache_files = list(cache_dir.glob("commercial_engine_*.pkl"))
    assert len(new_cache_files) == 1
    assert new_cache_files[0] != old_cache_files[0]


def test_warm_up_populates_the_singleton(isolated_registry):
    registry.warm_up_commercial_engine()
    assert registry._commercial_engine is not registry._UNSET
