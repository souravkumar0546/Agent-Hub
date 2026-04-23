from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class OrgSummary(BaseModel):
    id: int
    name: str
    slug: str
    role: str
    logo_url: str | None = None

    model_config = {"from_attributes": True}


class DepartmentSummary(BaseModel):
    id: int
    name: str
    slug: str
    is_head: bool = False

    model_config = {"from_attributes": True}


class MeResponse(BaseModel):
    id: int
    email: EmailStr
    name: str
    is_super_admin: bool
    orgs: list[OrgSummary]
    current_org_id: int | None = None
    current_org_role: str | None = None
    departments: list[DepartmentSummary] = []


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: MeResponse
