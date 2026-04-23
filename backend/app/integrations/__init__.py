"""Integration registry + catalog.

Each integration type has:
  - a static descriptor in CATALOG (icon, description, config / credential schema)
  - a handler module under `app.integrations.<type>` exposing
      `test_connection(config, credentials) -> (ok: bool, error: str | None)`

The routes layer drives the catalog to the UI so forms are entirely
backend-driven — adding a new integration is a two-file change
(catalog entry + handler module).
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass, field
from typing import Callable


# ── Field type system used by the catalog schemas ────────────────────────────
# Kept tiny on purpose — the frontend only needs these three types.
# `text` and `url` render as single-line inputs; `password` masks the value.
# Future: add `select`, `boolean`, `number` when needed.

@dataclass(frozen=True)
class FieldSpec:
    key: str
    label: str
    type: str = "text"          # one of: text | password | url | textarea
    required: bool = True
    placeholder: str = ""
    help: str = ""
    group: str = "config"       # "config" or "credentials"


@dataclass(frozen=True)
class IntegrationDef:
    type: str
    name: str
    description: str
    icon: str = "plug"
    category: str = "General"
    implemented: bool = False
    fields: tuple[FieldSpec, ...] = field(default_factory=tuple)

    def schema(self) -> list[dict]:
        return [
            {
                "key": f.key,
                "label": f.label,
                "type": f.type,
                "required": f.required,
                "placeholder": f.placeholder,
                "help": f.help,
                "group": f.group,
            }
            for f in self.fields
        ]


# Shared field specs reused across integrations.
_BASE_URL = FieldSpec(
    key="base_url", label="Base URL", type="url",
    placeholder="https://apisalesdemo4.successfactors.com",
    help="API root for the tenant.",
)


CATALOG: list[IntegrationDef] = [
    IntegrationDef(
        type="successfactors",
        name="SAP SuccessFactors",
        description="HR system of record — users, positions, departments, onboarding.",
        icon="users",
        category="HR",
        implemented=True,
        fields=(
            _BASE_URL,
            FieldSpec(key="company_id", label="Company ID",
                      placeholder="e.g. SFSALES027530",
                      help="The tenant's SF Company ID."),
            FieldSpec(key="tech_user_id", label="Technical User ID",
                      placeholder="e.g. svc_syngene@SFSALES027530",
                      help="Integration user that the API calls run as.",
                      required=False),
            FieldSpec(key="client_id", label="OAuth Client ID", group="credentials",
                      help="SAML assertion client from SF Admin Center."),
            FieldSpec(key="client_secret", label="Client Secret", type="password", group="credentials",
                      help="Symmetric secret issued with the OAuth client."),
        ),
    ),
    IntegrationDef(
        type="smtp",
        name="Email (SMTP)",
        description="Outbound email for notifications and report delivery.",
        icon="mail",
        category="Messaging",
        implemented=True,
        fields=(
            FieldSpec(key="host", label="SMTP host", placeholder="smtp.office365.com"),
            FieldSpec(key="port", label="Port", placeholder="587"),
            FieldSpec(key="from_address", label="From address",
                      placeholder="noreply@syngene.com"),
            FieldSpec(key="use_tls", label="Use STARTTLS (true/false)",
                      placeholder="true", required=False),
            FieldSpec(key="username", label="Username", group="credentials"),
            FieldSpec(key="password", label="Password", type="password", group="credentials"),
        ),
    ),
    IntegrationDef(
        type="sap",
        name="SAP ERP",
        description="Finance, procurement, master data (OData / BAPI).",
        icon="box",
        category="ERP",
        fields=(
            _BASE_URL,
            FieldSpec(key="client", label="SAP Client", placeholder="100"),
            FieldSpec(key="username", label="Username", group="credentials"),
            FieldSpec(key="password", label="Password", type="password", group="credentials"),
        ),
    ),
    IntegrationDef(
        type="azure_ad",
        name="Microsoft Entra ID (Azure AD)",
        description="Directory + SSO source for org members.",
        icon="shield",
        category="Identity",
        fields=(
            FieldSpec(key="tenant_id", label="Tenant ID",
                      placeholder="00000000-0000-0000-0000-000000000000"),
            FieldSpec(key="client_id", label="App (client) ID", group="credentials"),
            FieldSpec(key="client_secret", label="Client secret", type="password", group="credentials"),
        ),
    ),
    IntegrationDef(
        type="slack",
        name="Slack",
        description="Post notifications to channels; slash-command triggers (later).",
        icon="chat",
        category="Messaging",
        fields=(
            FieldSpec(key="default_channel", label="Default channel",
                      placeholder="#agent-notifications", required=False),
            FieldSpec(key="bot_token", label="Bot token (xoxb-…)",
                      type="password", group="credentials"),
        ),
    ),
    IntegrationDef(
        type="teams",
        name="Microsoft Teams",
        description="Incoming-webhook notifications to Teams channels.",
        icon="chat",
        category="Messaging",
        fields=(
            FieldSpec(key="webhook_url", label="Incoming-webhook URL", type="url",
                      group="credentials",
                      help="Channel → Connectors → Incoming Webhook."),
        ),
    ),
    IntegrationDef(
        type="azure_blob",
        name="Azure Blob Storage",
        description="Document storage for knowledge base + run artifacts.",
        icon="flask",
        category="Storage",
        fields=(
            FieldSpec(key="account", label="Storage account",
                      placeholder="syngenedocs"),
            FieldSpec(key="container", label="Container name",
                      placeholder="knowledge-base"),
            FieldSpec(key="sas_token", label="SAS token", type="password", group="credentials",
                      help="Paste the SAS query string — starts with 'sv='."),
        ),
    ),
    IntegrationDef(
        type="webhook",
        name="Generic Webhook",
        description="Send agent run events to an arbitrary HTTP endpoint.",
        icon="plug",
        category="General",
        fields=(
            FieldSpec(key="url", label="Endpoint URL", type="url"),
            FieldSpec(key="auth_header", label="Auth header (optional)",
                      type="password", required=False, group="credentials",
                      help="Full header value, e.g. 'Bearer abc…'."),
        ),
    ),
]


def get_def(itype: str) -> IntegrationDef | None:
    return next((d for d in CATALOG if d.type == itype), None)


def get_test_handler(itype: str) -> Callable | None:
    """Resolve `app.integrations.<type>.test_connection`.

    Returns None if the handler module doesn't exist. Routes will report this
    as 'not implemented yet' rather than 500-ing.
    """
    try:
        module = importlib.import_module(f"app.integrations.{itype}")
    except ImportError:
        return None
    return getattr(module, "test_connection", None)
