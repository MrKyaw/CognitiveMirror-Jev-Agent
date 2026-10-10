"""Runtime settings, loaded from environment variables (see .env.example)."""
from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
CONFIG_DIR = PACKAGE_DIR / "config"
POLICY_DIR = CONFIG_DIR / "policies"

DEPLOYMENT_MODES = ("local", "private_cloud", "enterprise")
ROLES = ("agent", "admin", "compliance")
LLM_PROVIDERS = ("none", "openai", "anthropic")
DEV_API_KEYS = "dev-agent-key:agent,dev-admin-key:admin,dev-compliance-key:compliance"


class ConfigError(ValueError):
    """Invalid configuration; raised at startup so misconfiguration fails fast."""


@dataclass(frozen=True)
class Settings:
    deployment_mode: str = "local"
    db_path: Path = Path("data/cognitive_mirror.db")
    database_url: str = ""
    api_keys: Mapping[str, str] = field(default_factory=dict)
    require_auth: bool = True
    stdio_role: str = "agent"
    retention_days: int = 30
    shared_context_ttl_minutes: int = 240
    policy_profile: str = "default"
    jev_config_path: Path | None = None
    jev_model: str = "jev-latest"
    typesafe_api_key: str = ""
    llm_provider: str = "none"
    llm_api_key: str = ""
    llm_model: str = ""
    llm_base_url: str = ""
    llm_timeout_s: float = 4.0
    allowed_hosts: tuple[str, ...] = ()
    log_level: str = "INFO"

    @property
    def llm_enabled(self) -> bool:
        return self.llm_provider != "none" and bool(self.llm_api_key)

    def role_for_key(self, key: str | None) -> str | None:
        if not key:
            return None
        return self.api_keys.get(key)


def _parse_keys(raw: str) -> dict[str, str]:
    keys: dict[str, str] = {}
    for item in filter(None, (p.strip() for p in raw.split(","))):
        key, sep, role = item.rpartition(":")
        if not sep or not key or role not in ROLES:
            raise ConfigError(f"CM_API_KEYS entry {item!r} must be '<key>:<{'|'.join(ROLES)}>'")
        keys[key] = role
    return keys


def _bool(raw: str) -> bool:
    return raw.strip().lower() in ("1", "true", "yes", "on")


def load_settings(env: Mapping[str, str] | None = None) -> Settings:
    env = os.environ if env is None else env
    mode = env.get("CM_DEPLOYMENT_MODE", "local")
    if mode not in DEPLOYMENT_MODES:
        raise ConfigError(f"CM_DEPLOYMENT_MODE must be one of {DEPLOYMENT_MODES}, got {mode!r}")
    keys = _parse_keys(env.get("CM_API_KEYS", DEV_API_KEYS))
    if mode == "enterprise" and set(keys) & set(_parse_keys(DEV_API_KEYS)):
        raise ConfigError("enterprise mode refuses the built-in dev API keys; set CM_API_KEYS")
    require_auth = _bool(env.get("CM_REQUIRE_AUTH", "true"))
    if mode == "enterprise" and not require_auth:
        raise ConfigError("enterprise mode requires CM_REQUIRE_AUTH=true")
    stdio_role = env.get("CM_STDIO_ROLE", "agent")
    if stdio_role not in ROLES:
        raise ConfigError(f"CM_STDIO_ROLE must be one of {ROLES}")
    policy = env.get("CM_POLICY_PROFILE", "enterprise" if mode == "enterprise" else "default")
    if not (POLICY_DIR / f"{policy}.json").exists():
        raise ConfigError(f"unknown CM_POLICY_PROFILE {policy!r}")
    provider = env.get("CM_LLM_PROVIDER", "none")
    if provider not in LLM_PROVIDERS:
        raise ConfigError(f"CM_LLM_PROVIDER must be one of {LLM_PROVIDERS}")
    jev_cfg = env.get("CM_JEV_CONFIG")
    if jev_cfg and not Path(jev_cfg).exists():
        raise ConfigError(f"CM_JEV_CONFIG file not found: {jev_cfg}")
    db_url = env.get("CM_DATABASE_URL", "").strip()
    if db_url and not db_url.startswith("postgres"):
        raise ConfigError("CM_DATABASE_URL must be a postgresql:// URL")
    try:
        retention = int(env.get("CM_RETENTION_DAYS", "30"))
        shared_ttl = int(env.get("CM_SHARED_CONTEXT_TTL_MINUTES", "240"))
        timeout = float(env.get("CM_LLM_TIMEOUT_S", "4.0"))
    except ValueError as e:
        raise ConfigError(f"numeric setting is invalid: {e}") from e
    if retention < 1 or shared_ttl < 1 or timeout <= 0:
        raise ConfigError("retention, shared context TTL and LLM timeout must be positive")
    hosts = tuple(h.strip() for h in env.get("CM_ALLOWED_HOSTS", "").split(",") if h.strip())
    return Settings(
        deployment_mode=mode,
        db_path=Path(env.get("CM_DB_PATH", "data/cognitive_mirror.db")),
        database_url=db_url,
        api_keys=keys,
        require_auth=require_auth,
        stdio_role=stdio_role,
        retention_days=retention,
        shared_context_ttl_minutes=shared_ttl,
        policy_profile=policy,
        jev_config_path=Path(jev_cfg) if jev_cfg else None,
        jev_model=env.get("CM_JEV_MODEL", "jev-latest"),
        typesafe_api_key=env.get("TYPESAFE_API_KEY", ""),
        llm_provider=provider,
        llm_api_key=env.get("CM_LLM_API_KEY", ""),
        llm_model=env.get("CM_LLM_MODEL", ""),
        llm_base_url=env.get("CM_LLM_BASE_URL", ""),
        llm_timeout_s=timeout,
        allowed_hosts=hosts,
        log_level=env.get("CM_LOG_LEVEL", "INFO").upper(),
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return load_settings()


def reset_settings() -> None:
    get_settings.cache_clear()
