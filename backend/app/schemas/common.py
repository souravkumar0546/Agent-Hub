from pydantic import BaseModel, EmailStr


class IdName(BaseModel):
    id: int
    name: str
    # Optional slug — populated where the referent has one (departments do,
    # generic id/name references don't). The Agent Hub's "My Agents" tab
    # keys its dept-filter chips off this, so without it the filter silently
    # no-ops.
    slug: str | None = None

    model_config = {"from_attributes": True}


class OrgOut(BaseModel):
    id: int
    name: str
    slug: str
    is_active: bool
    logo_url: str | None = None

    model_config = {"from_attributes": True}


class DepartmentOut(BaseModel):
    id: int
    name: str
    slug: str
    description: str | None = None

    model_config = {"from_attributes": True}


class DepartmentCreate(BaseModel):
    name: str
    slug: str
    description: str | None = None


class UserOut(BaseModel):
    id: int
    email: EmailStr
    name: str
    is_super_admin: bool

    model_config = {"from_attributes": True}


class MemberOut(BaseModel):
    user_id: int
    email: EmailStr
    name: str
    role: str
    departments: list[IdName] = []


class InviteRequest(BaseModel):
    email: EmailStr
    name: str
    password: str
    role: str = "MEMBER"
    department_ids: list[int] = []


class AgentOut(BaseModel):
    id: int
    type: str
    name: str
    # Short brand-style name (e.g. "Vera" for RCA). Resolved from the
    # CATALOG at serialization time, NOT persisted on the Agent row — so
    # a rename of a catalog entry is reflected live without a migration.
    # Empty/absent → frontend renders only `name`.
    display_name: str | None = None
    tagline: str | None = None
    category: str | None = None
    icon: str | None = None
    is_enabled: bool
    # `is_installed` is the org-level state (alias for is_enabled).
    # `is_picked` is the current user's personal state. Populated by the
    # list route, not the DB.
    is_installed: bool = True
    is_picked: bool = False
    implemented: bool = False
    departments: list[IdName] = []

    model_config = {"from_attributes": True}


class CatalogAgentOut(BaseModel):
    """An agent type as it appears in the platform-wide catalog (code-side CATALOG).

    Unlike AgentOut, this has no DB id — it's just a template. The
    `is_installed` / `is_picked` flags are filled in relative to the
    requesting user/org when the catalog is returned.
    """

    type: str
    name: str
    display_name: str | None = None
    tagline: str | None = None
    category: str | None = None
    icon: str | None = None
    implemented: bool = False
    is_installed: bool = False
    is_picked: bool = False
    agent_id: int | None = None  # DB id when this agent exists in the user's org
