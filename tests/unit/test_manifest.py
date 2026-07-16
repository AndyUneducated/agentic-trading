from atrading.core.manifest import RunManifest


def test_manifest_has_run_id_and_tz_aware_timestamp() -> None:
    manifest = RunManifest(seed=42)
    assert manifest.run_id
    assert manifest.created_at.tzinfo is not None
    assert manifest.seed == 42


def test_manifest_json_roundtrip() -> None:
    manifest = RunManifest(seed=1, llm_model="deepseek-chat", params={"a": 1})
    restored = RunManifest.model_validate_json(manifest.model_dump_json())
    assert restored.seed == 1
    assert restored.llm_model == "deepseek-chat"
    assert restored.params == {"a": 1}
    assert restored.run_id == manifest.run_id
