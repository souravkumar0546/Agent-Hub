# Getting started

## Logging in

Open the hub URL, enter your corporate email, and sign in with the password your organisation admin gave you. Sessions last 24 hours.

If login fails, double-check that you're using the correct tenant URL — the hub is multi-tenant, and an email that works on one tenant will not work on another.

## What you see after login

- **Left sidebar** — primary navigation: Agent Hub, Knowledge Base, My Runs, User Guide. Admins also see Members, Departments, Audit Log. Super admins additionally see Organizations.
- **Top bar** — your current organisation, your role (`SUPER_ADMIN` / `ORG_ADMIN` / `MEMBER`), and your name.
- **Agent Hub** (the default landing) — a grid of agent cards. Ready-to-use agents are shown first; upcoming agents sit below.

## Navigating the hub

Each card represents one AI agent. Click a card to open that agent's workspace. The card shows the agent's category, the departments it is tagged to, and its availability.

Agents are **not** gated by department in this release — every member of the organisation can open and run every agent. Department tags are informational only.

## Filtering by department

Above the card grid is a row of filter chips. Click a chip to narrow the list to agents tagged for that department. The `All` chip clears the filter. Filtering is driven by the backend (`?department=<slug>`) so every user sees a consistent view.

## Roles

| Role | What they can do |
|---|---|
| `SUPER_ADMIN` | Platform-level: onboard new organisations, cross-tenant visibility, configure anything. |
| `ORG_ADMIN` | Full control of one organisation — invite members, create departments, connect integrations, view the audit log. |
| `MEMBER` | Use agents, upload files to the knowledge base, download their own reports. Cannot change org settings. |

Your role is scoped per organisation — you could be an admin in one org and a member in another.

## Switching organisations

If you belong to more than one org, your profile shows a picker in the top bar. Switching orgs reloads the hub with that org's catalog, members, and departments.
