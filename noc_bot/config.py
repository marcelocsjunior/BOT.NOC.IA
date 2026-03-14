# -*- coding: utf-8 -*-
import os
import re
from dataclasses import dataclass
from zoneinfo import ZoneInfo

TZ_LOCAL = ZoneInfo(os.getenv("TZ_LOCAL", "America/Sao_Paulo"))

# BOT_VERSION: identificador humano do runtime.
# Baseline recomenda:
#   BOT_VERSION=YYYY-MM-DD-dm-group-ux|build=YYYY-MM-DD_HHMMSS
BOT_VERSION = os.getenv("BOT_VERSION", "2026-02-25-dm-group-ux")


def env(name: str, default: str | None = None) -> str | None:
    v = os.getenv(name)
    if v is None or v == "":
        return default
    return v


def must_env(*names: str) -> str:
    for n in names:
        v = env(n)
        if v:
            return v
    raise RuntimeError(f"Missing required env var (tried: {', '.join(names)})")


def env_bool(name: str, default: bool = False) -> bool:
    v = env(name)
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "yes", "y", "on")


def env_int(name: str, default: int) -> int:
    v = env(name)
    if v is None:
        return default
    try:
        return int(v.strip())
    except Exception:
        return default


def env_csv_ints(name: str) -> list[int]:
    raw = env(name, "") or ""
    out: list[int] = []
    for item in raw.split(","):
        s = item.strip()
        if not s:
            continue
        try:
            out.append(int(s))
        except Exception:
            continue
    return out


# Build id (rastreabilidade)
BUILD_ID = env("BUILD_ID", env("BOT_BUILD", None))
if not BUILD_ID:
    m = re.search(r"\bbuild=([0-9]{4}-[0-9]{2}-[0-9]{2}_[0-9]{6})\b", BOT_VERSION or "")
    if m:
        BUILD_ID = m.group(1)

# --- runtime ---
TELEGRAM_TOKEN = must_env("TELEGRAM_BOT_TOKEN", "BOT_TOKEN")
UNIT = env("NOC_UNIT", env("UNIT", "UN1")) or "UN1"

NOC_DB_PATH = env("NOC_DB_PATH", "/var/lib/noc/noc.db")
NOC_LOG_PATH = env("NOC_LOG_PATH", env("NOC_LOG_FILE", "/var/log/mikrotik/un1.log"))  # compat

TAILER_STATE_PATH = env("NOC_TAILER_STATE_PATH", "/var/lib/noc/tailer.state.json")

DB_FRESHNESS_S = env_int("NOC_DB_FRESHNESS_S", 600)
DB_EVENT_STALE_S = env_int("NOC_DB_EVENT_STALE_S", 3600)

TIMELINE_DEFAULT_N = env_int("NOC_TIMELINE_DEFAULT_N", 30)
MAX_TIMELINE_N = env_int("NOC_MAX_TIMELINE_N", 200)

GROUP_REPLY_MENTION_ONLY = env_bool("NOC_GROUP_MENTION_ONLY", True)

# --- DM Consultiva / IA Assistiva ---
DM_ASSISTANT_ENABLED = env_bool("DM_ASSISTANT_ENABLED", False)
DM_ASSISTANT_SHADOW_MODE = env_bool("DM_ASSISTANT_SHADOW_MODE", False)
DM_ASSISTANT_ALLOWED_CHAT_IDS = env_csv_ints("DM_ASSISTANT_ALLOWED_CHAT_IDS")

DM_ASSISTANT_STYLE = (env("DM_ASSISTANT_STYLE", "light") or "light").strip().lower()
if DM_ASSISTANT_STYLE not in ("light", "professional", "friendly"):
    DM_ASSISTANT_STYLE = "light"

DM_ASSISTANT_PROACTIVE = env_bool("DM_ASSISTANT_PROACTIVE", False)
DM_ASSISTANT_MAX_REPLY_LINES = env_int("DM_ASSISTANT_MAX_REPLY_LINES", 3)
DM_ASSISTANT_ENABLE_AI_FINISH = env_bool("DM_ASSISTANT_ENABLE_AI_FINISH", False)

# Confidence mínima do parser consultivo
_DM_ASSISTANT_MIN_CONFIDENCE_RAW = env("DM_ASSISTANT_MIN_CONFIDENCE", "0.60") or "0.60"
try:
    DM_ASSISTANT_MIN_CONFIDENCE = float(_DM_ASSISTANT_MIN_CONFIDENCE_RAW.strip())
except Exception:
    DM_ASSISTANT_MIN_CONFIDENCE = 0.60

if DM_ASSISTANT_MIN_CONFIDENCE < 0:
    DM_ASSISTANT_MIN_CONFIDENCE = 0.0
elif DM_ASSISTANT_MIN_CONFIDENCE > 1:
    DM_ASSISTANT_MIN_CONFIDENCE = 1.0

# --- IA (Cloudflare Workers AI) ---
AI_ENABLED = env_bool("AI_ENABLED", False)
CF_ACCOUNT_ID = env("CLOUDFLARE_ACCOUNT_ID")
CF_AUTH_TOKEN = env("CLOUDFLARE_AUTH_TOKEN")
CF_AI_MODEL = env("CLOUDFLARE_AI_MODEL", "@cf/meta/llama-3.1-8b-instruct")

AI_TIMEOUT_S = env_int("AI_TIMEOUT_S", 12)
AI_CACHE_TTL_S = env_int("AI_CACHE_TTL_S", 300)
AI_RL_PER_MIN = env_int("AI_RL_PER_MIN", 12)

# --- checks / severidade (UN1) ---
KNOWN_CHECKS = {
    "UN1": {
        "MUNDIVOX": "189.91.71.218",
        "VALENET": "187.1.49.122",
        "ESCALLO CLOUD": "187.33.28.57",
        "VOIP": "138.99.240.49",
    }
}

CHECK_ALIASES = {
    "MUNDIVOX": ["mundi", "mundivox"],
    "VALENET": ["vale", "valenet"],
    "ESCALLO CLOUD": ["escalo", "escallo", "cloud", "escalo cloud"],
    "VOIP": ["voip", "sip"],
}

WINDOW_ALIASES = {
    "24h": ["24h", "hoje", "últimas 24h", "ultimas 24h", "dia"],
    "7d": ["7d", "semana", "últimos 7d", "ultimos 7d", "7 dias"],
    "30d": ["30d", "mês", "mes", "30 dias"],
}

NOISE_TOKENS = [
    t.strip().upper()
    for t in (env("NOC_NOISE_TOKENS", "SELFTEST,PUSH-TEST,UN1 TEST,TEST").split(","))
    if t.strip()
]


@dataclass(frozen=True)
class Svc:
    code: str
    # key base para match. Para qualidade, o match usa "key" + must="QUALITY".
    key: str
    label: str
    subject: str
    aliases: tuple[str, ...]


# Catálogo de serviços (UN1)
SVCS: dict[str, Svc] = {
    "NET": Svc(
        "NET",
        "INTERNET",
        "Internet (Qualidade)",
        "Internet (Qualidade)",
        ("internet", "rede", "qualidade internet", "qualidade da internet"),
    ),
    "TEL": Svc(
        "TEL",
        "VOIP",
        "Telefonia",
        "Telefonia",
        ("telefonia", "telefone", "ligações", "ligacoes", "ramal", "voip", "sip"),
    ),
    "L1": Svc(
        "L1",
        "MUNDIVOX",
        "Internet (Link 1) (Mundivox)",
        "Internet (Link 1) (Mundivox/Primário)",
        ("link1", "link 1", "internet 1", "mundivox", "primário", "primario"),
    ),
    "L2": Svc(
        "L2",
        "VALENET",
        "Internet (Link 2) (Valenet)",
        "Internet (Link 2) (Valenet/Secundário)",
        ("link2", "link 2", "internet 2", "valenet", "secundário", "secundario"),
    ),
    "ESC": Svc(
        "ESC",
        "ESCALLO",
        "ESCALLO",
        "ESCALLO",
        ("escalo", "escallo", "omminichanel", "futurotec escallo", "futurotec"),
    ),

    # VPN site-to-site (UN2/UN3)
    # Observação: disponibilidade (UP/DOWN). Não usa QUALITY.
    "VPN2": Svc(
        "VPN2",
        "VPN_UN2",
        "VPN UN2 (Barreiro)",
        "VPN UN2 (Barreiro)",
        (
            "vpn un2",
            "vpn barreiro",
            "barreiro vpn",
            "vpn unidade 2",
        ),
    ),
    "VPN3": Svc(
        "VPN3",
        "VPN_UN3",
        "VPN UN3 (Alípio de Mello)",
        "VPN UN3 (Alípio de Mello)",
        (
            "vpn un3",
            "vpn alipio",
            "vpn alípio",
            "vpn alipio de mello",
            "vpn alípio de mello",
            "alipio vpn",
            "alípio vpn",
            "vpn unidade 3",
        ),
    ),
}


def severity_label(check_name: str, wan_mundi_state: str | None, wan_vale_state: str | None) -> str:
    c = (check_name or "").upper()

    if "MUNDIVOX" in c and wan_mundi_state == "DOWN":
        return "SEV1"
    if "VALENET" in c and wan_vale_state == "DOWN" and wan_mundi_state == "UP":
        return "SEV3"

    if any(x in c for x in ("ESCALLO", "VOIP")):
        if wan_mundi_state == "UP" and (wan_vale_state in ("UP", None)):
            return "SEV2"

    return "SEV4"
