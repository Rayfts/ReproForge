from reproforge.core.config import ReproForgeConfig


def test_host_environment_is_not_inherited_by_default(monkeypatch) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "top-secret")
    monkeypatch.setenv("UNRELATED_VALUE", "also-secret")

    config = ReproForgeConfig()

    assert config.selected_environment() == {}


def test_only_explicit_environment_and_secrets_are_selected(monkeypatch) -> None:
    monkeypatch.setenv("SAFE_VALUE", "visible")
    monkeypatch.setenv("MY_SECRET", "secret")
    monkeypatch.setenv("GITHUB_TOKEN", "must-not-leak")
    config = ReproForgeConfig()
    config.security.allowed_environment = ["SAFE_VALUE"]
    config.security.allowed_secrets = ["MY_SECRET"]

    assert config.selected_environment() == {
        "SAFE_VALUE": "visible",
        "MY_SECRET": "secret",
    }
