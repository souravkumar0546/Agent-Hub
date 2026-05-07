import { useEffect } from 'react';
import { useAuth } from './auth.jsx';

const PRODUCT_NAME = 'Uniqus Labs';
const PRODUCT_TAGLINE = 'AGENT & APPLICATION HUB';
const FALLBACK_NAME = PRODUCT_NAME;

/**
 * Returns brand strings for the currently active org. The PRODUCT name is a
 * constant ("Uniqus Labs") — this is a Uniqus product served to customers, not
 * a white-label. The TENANT identity (org name + logo) is what changes per
 * customer and shows up in the sidebar logo plate, breadcrumb root, etc.
 *
 * - `orgName`     → "Uniqus Consultech" / null if logged out
 * - `displayName` → tenant name when known, else product name
 * - `brandLine`   → "Uniqus Consultech Platform" / "Platform" — breadcrumb root
 * - `productName` → always "Uniqus Labs" — used for <title>, footer, etc.
 *
 * Super-admins on the Platform page (no current org) get the product name as
 * the display name so the UI doesn't lie about which tenant is in play.
 */
export function useBrand() {
  const { user } = useAuth();
  const org = user?.orgs?.find((o) => o.id === user.current_org_id) || null;
  const orgName = org?.name || null;
  const displayName = orgName || FALLBACK_NAME;
  const compact = displayName.replace(/\s+(Ltd|Inc|LLC|Pvt|Limited|Corporation)\.?$/i, '').trim();

  return {
    orgName,
    displayName,
    // `org.logo_url` is populated on the me payload via OrgOut.
    logoUrl: org?.logo_url || null,
    brandMark: compact.toLowerCase(),
    brandLine: orgName ? `${compact} Platform` : 'Platform',
    productName: PRODUCT_NAME,
    tagline: PRODUCT_TAGLINE,
  };
}

/** Side-effect hook: keep document.title in sync with the active org. */
export function useDocumentTitle(suffix = '') {
  const { productName } = useBrand();
  useEffect(() => {
    const base = productName;
    document.title = suffix ? `${suffix} — ${base}` : base;
  }, [productName, suffix]);
}
