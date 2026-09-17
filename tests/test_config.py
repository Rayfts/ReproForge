from reproforge.core.config import ReproForgeConfig
from reproforge.reproduction.support import runtime_policy_error


def test_host_environment_is_not_inherited_by_default(monkeypatch) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "top-secret")
    monkeypatch.setenv("UNRELATED_VALUE", "also-secret")

    config = ReproForgeConfig()

    assert config.selected_environment() == {}


def test_repository_requests_require_operator_grants(monkeypatch) -> None:
    monkeypatch.setenv("SAFE_VALUE", "visible")
    monkeypatch.setenv("MY_SECRET", "secret")
    config = ReproForgeConfig()
    config.security.allowed_environment = ["SAFE_VALUE"]
    config.security.allowed_secrets = ["MY_SECRET"]

    assert config.selected_environment() == {}

    monkeypatch.setenv("REPROFORGE_ENV_GRANTS", "SAFE_VALUE")
    monkeypatch.setenv("REPROFORGE_SECRET_GRANTS", "MY_SECRET")

    assert config.selected_environment() == {
        "SAFE_VALUE": "visible",
        "MY_SECRET": "secret",
    }


def test_github_control_plane_tokens_are_never_injected(monkeypatch) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "must-not-leak")
    monkeypatch.setenv("GH_TOKEN", "also-must-not-leak")
    monkeypatch.setenv("REPROFORGE_SECRET_GRANTS", "GITHUB_TOKEN,GH_TOKEN")
    config = ReproForgeConfig()
    config.security.allowed_secrets = ["GITHUB_TOKEN", "GH_TOKEN"]

    assert config.selected_environment() == {}


def test_unenforced_domain_allowlist_fails_closed() -> None:
    config = ReproForgeConfig()
    config.security.allowed_network_domains = ["api.example.com"]

    error = runtime_policy_error(config)

    assert error is not None
    assert "cannot enforce allowed_network_domains" in error
