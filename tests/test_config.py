import pytest

from modules.config import Config, ConfigError, load_config, parse_config


def test_missing_file_gives_defaults(tmp_path):
    assert load_config(tmp_path / "nope.toml") == Config()


def test_repo_config_toml_is_valid():
    assert load_config("config.toml").mastery.pass_threshold == 0.85


@pytest.mark.parametrize(
    "data",
    [
        {"mastery": {"pass_threshold": 0}},
        {"mastery": {"pass_threshold": 1.5}},
        {"mastery": {"pass_threshold": True}},
        {"mastery": {"pass_treshold": 0.9}},  # typo must not be ignored
        {"bogus": {}},
        {"probe": {"min_questions_per_strand": 5, "max_questions_per_strand": 2}},
        {"research": {"min_independent_sources": 1}},  # verification requires >= 2
        {"research": {"source_allowlist": ["https://evil.com/x"]}},
        {"research": {"source_allowlist": ["localhost"]}},
        {"logging": {"max_event_bytes": 10**9}},
    ],
)
def test_invalid_configs_rejected(data):
    with pytest.raises(ConfigError):
        parse_config(data)


def test_malformed_toml_and_oversize(tmp_path):
    bad = tmp_path / "c.toml"
    bad.write_text("this is = = not toml")
    with pytest.raises(ConfigError):
        load_config(bad)
    bad.write_text("# " + "x" * 70000)
    with pytest.raises(ConfigError):
        load_config(bad)
