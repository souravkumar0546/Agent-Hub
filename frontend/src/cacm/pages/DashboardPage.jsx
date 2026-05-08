import React, { useCallback, useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import AppShell from "../../components/AppShell.jsx";
import { getDashboard, getRun } from "../api.js";
import DashboardCharts from "../components/DashboardCharts.jsx";
import { exportDashboardToPpt } from "../lib/dashboardPptExport.js";
import "../styles.css";

const EMPTY_FILTERS = {
  companies: [],
  locations: [],
  risk_levels: [],
  aging_buckets: [],
  po_creators: [],
  movement_types: [],
  material_groups: [],
  reversals: [],
};

export default function DashboardPage() {
  const { runId } = useParams();
  const [data, setData] = useState(null);
  const [run, setRun] = useState(null);
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState(EMPTY_FILTERS);

  // Initial load — pulls run summary + first dashboard payload.
  useEffect(() => {
    let cancelled = false;
    if (!runId) return;
    setLoading(true);
    setErr("");
    Promise.all([
      getDashboard(runId, EMPTY_FILTERS),
      getRun(runId).catch(() => null),
    ])
      .then(([d, r]) => {
        if (cancelled) return;
        setData(d);
        if (r) setRun(r);
      })
      .catch((e) => {
        if (cancelled) return;
        setErr(e.response?.data?.detail || e.message || "Failed to load dashboard.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [runId]);

  // Re-fetch on filter change. Skips the initial mount because filters start
  // empty and the initial effect above already fetched with empty filters.
  useEffect(() => {
    if (!runId) return undefined;
    if (
      filters.companies.length === 0 &&
      filters.locations.length === 0 &&
      filters.risk_levels.length === 0 &&
      filters.aging_buckets.length === 0 &&
      filters.po_creators.length === 0 &&
      (filters.movement_types?.length || 0) === 0 &&
      (filters.material_groups?.length || 0) === 0 &&
      (filters.reversals?.length || 0) === 0
    ) {
      // Avoid duplicate fetch on first mount; the initial effect handles it.
      // But if user clears filters AFTER applying some, we still need to
      // re-fetch. Trigger only when `data` already exists (i.e. we're past
      // initial mount).
      if (!data) return undefined;
    }
    let cancelled = false;
    setErr("");
    getDashboard(runId, filters)
      .then((d) => {
        if (cancelled) return;
        setData(d);
      })
      .catch((e) => {
        if (cancelled) return;
        setErr(e.response?.data?.detail || e.message || "Failed to load dashboard.");
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [runId, filters]);

  const onFiltersChange = useCallback((next) => setFilters(next), []);
  const onClearFilters = useCallback(() => setFilters(EMPTY_FILTERS), []);

  const kpiName = data?.kpi_name || data?.kpi_type || run?.kpi_type || "Run dashboard";
  const kpiType = data?.kpi_type || run?.kpi_type || "";

  const [exporting, setExporting] = useState(false);
  const dashboardRef = useRef(null);
  const handleExportPpt = useCallback(async () => {
    if (!data || !dashboardRef.current) return;
    setExporting(true);
    try {
      await exportDashboardToPpt({
        dashboardEl: dashboardRef.current,
        kpiName,
        kpiType,
        runId,
      });
    } catch (e) {
      setErr(e?.message || "Failed to export PPT.");
    } finally {
      setExporting(false);
    }
  }, [data, kpiName, kpiType, runId]);

  const isEmpty =
    !loading &&
    !err &&
    data &&
    !data.totals &&
    !data.aging_buckets &&
    !data.company_breakdown &&
    !data.movement_type_distribution;

  return (
    <AppShell crumbs={["Agent Hub", "Prism", `Run ${runId}`, "Dashboard"]}>
      <div className="cacm-hero">
        <div style={{ flex: 1, minWidth: 0 }}>
          <h1 className="page-title" style={{ marginBottom: 4 }}>
            {kpiName}
          </h1>
          <div className="page-subtitle" style={{ marginBottom: 8 }}>
            Dashboard for run #{runId}
          </div>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <Link to={`/agents/cacm/run/${runId}`} className="btn">
            ← Back to run
          </Link>
          <Link to={`/agents/cacm/runs/${runId}/exceptions`} className="btn">
            View exceptions
          </Link>
          <button
            type="button"
            className="btn btn-primary"
            onClick={handleExportPpt}
            disabled={!data || loading || exporting}
          >
            {exporting ? "Exporting…" : "Export to PPT"}
          </button>
        </div>
      </div>

      {err && <div className="inv-warning" style={{ marginBottom: 12 }}>{err}</div>}

      {loading && <div className="cacm-loading">Loading dashboard…</div>}

      {!loading && !err && isEmpty && (
        <div className="cacm-empty">
          No dashboard data yet for this run. Try again once the run completes.
        </div>
      )}

      {!loading && !err && data && !isEmpty && (
        <div ref={dashboardRef}>
          <DashboardCharts
            data={data}
            kpiType={kpiType}
            filters={filters}
            onFiltersChange={onFiltersChange}
            onClearFilters={onClearFilters}
          />
        </div>
      )}
    </AppShell>
  );
}
