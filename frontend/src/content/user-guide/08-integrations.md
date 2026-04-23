# Integrations

Integrations connect the hub to your external systems. Once an org admin connects an integration, agents can read from it (e.g. pulling employee data from SuccessFactors, sending notifications via SMTP) without every agent having to re-authenticate.

## Who can manage integrations

Only `ORG_ADMIN` and `SUPER_ADMIN` can create, edit, or disconnect integrations. Members can see which integrations are connected but not their credentials.

## Available types

| Type | Purpose | Configured as |
|---|---|---|
| SuccessFactors | HR data (users, employees, org chart) | Base URL, Company ID, OAuth client ID, client secret, technical user ID |
| SAP | ERP lookups (vendors, materials) | Base URL, client, user, password |
| Azure AD / Entra ID | SSO, directory sync | Tenant ID, client ID, client secret |
| Slack | Notifications | Bot token |
| Microsoft Teams | Notifications | Webhook URL |
| Email / SMTP | Outbound email from agents | Host, port, TLS, username, password |
| Azure Blob | Document storage | Connection string, container |
| Generic Webhook | Any HTTP endpoint | URL, auth header template |

## Connecting SuccessFactors

1. Open **Integrations** from the sidebar (admin only).
2. Under **Available**, click **SuccessFactors** → **Connect**.
3. Fill in the form — the tooltips explain each field. A typical setup needs:
   - **Base URL** — e.g. `https://apisalesdemo4.successfactors.com`
   - **Company ID** — your SuccessFactors tenant (usually a short alphanumeric)
   - **OAuth client ID**
   - **Client secret**
   - **Technical user ID**
4. Click **Save**. The integration lands in **Connected** with status `disconnected` until tested.
5. Click **Test connection**. The platform hits `/odata/v2/User?$top=1` with the configured creds. If it succeeds, status flips to `connected` and the timestamp is recorded.

## Rotating credentials

Credentials are never displayed — only `●●●●`. To change them, click **Replace** and enter new values. The new ones overwrite the old ones after a confirmation.

## Disconnecting

Click **Disconnect** on a connected card. The record is deleted. Any agent that depended on that integration will error until it's reconnected.

## Under the hood

Credentials are encrypted at rest with a Fernet key. The key is read from `INTEGRATIONS_SECRET_KEY` in the backend environment; in production, rotate that key and re-save each integration to re-encrypt. Credentials are never logged, never returned from the API, and never shown in the audit log (only the metadata — which integration, when, by whom).
