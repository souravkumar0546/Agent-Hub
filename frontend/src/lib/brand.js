import { useEffect } from 'react';
import { useAuth } from './auth.jsx';

const PRODUCT_TAGLINE = 'AGENT HUB';
const FALLBACK_NAME = 'AI Hub';

/**
 * Returns { orgName, brandLine, productName } for the currently active org.
 * Works everywhere the AuthProvider is mounted.
 *
 * - `orgName`     → "Uniqus" / "Syngene Ltd" / null if logged out
 * - `brandLine`   → "Uniqus Platform" — used for breadcrumb roots
 * - `productName` → "Uniqus AI Hub" — used for <title>, guide hero, etc.
 * - `brandMark`   → "uniqus" — lowercase italic mark in the sidebar
 *
 * Super-admins on the Platform page (no current org) get a generic label so
 * the UI doesn't lie about which tenant is in play.
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
    productName: orgName ? `${compact} AI Hub` : 'AI Hub',
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
