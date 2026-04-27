# Managing members (admin)

This section is for **org admins**. Members can skip it.

## Inviting a new colleague

1. Sidebar → **Admin** → **Members**.
2. Click **Invite member**.
3. Fill in email, full name, role (`ORG_ADMIN` or `MEMBER`), and an initial password the user will be asked to change on first login.
4. Optional: tick the departments the new user belongs to.
5. **Save**.

The invite creates the user account and the membership in your org. There's no email yet — share the credentials with your colleague directly. We'll add invite emails (with a one-time link) before public launch.

## Changing a member's role

Members tab → click a row → **Edit** → change Role → **Save**. The change takes effect on the user's next request — they don't need to log out.

## Suspending or removing a member

- **Suspend** (recoverable): Edit → toggle **Active** off. The user can no longer sign in but their history is preserved.
- **Remove** (irreversible): Edit → **Delete membership**. The user keeps their account globally but loses access to this org.

## Departments

Sidebar → **Admin** → **Departments**.

Each department has a name, slug, and optional description. Add or rename via the dialog. Departments are informational today — agents are available to every member regardless of department — but they show up as filter chips on the Agent Hub and are recorded against each agent run for analytics.

To assign a member to one or more departments, edit the member row and tick the department checkboxes.

## Audit log

Sidebar → **Admin** → **Audit Log** lists every action in your org, newest first:

- Agent runs (`agent.run`)
- Field edits in RCA (`agent.field_edit`)
- Integration tests (`integration.test`)
- Member changes (`member.invite`, `member.update`, `member.remove`)
- Department changes
- Login events
- Assistant chats

Filter by user, action, or date range. The log is append-only — entries can't be deleted or edited.
