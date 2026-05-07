import React, { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import AppShell from "../../components/AppShell.jsx";
import { getDashboard, getRun } from "../api.js";
import DashboardCharts from "../components/DashboardCharts.jsx";
import "../styles.css";

export default function DashboardPage() {
  const { runId } = useParams();
  const [data, setData] = useState(null);
  const [run, setRun] = useState(null);
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    if (!runId) return;
    setLoading(true);
    setErr("");
    Promise.all([
      getDashboard(runId),
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

  const kpiName = data?.kpi_name || data?.kpi_type || run?.kpi_type || "Run dashboard";

  const isEmpty =
    !loading &&
    !err &&
    data &&
    !data.totals &&
    !data.by_risk &&
    !data.by_company &&
    !data.by_vendor &&
    !data.monthly_trend;

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
        </div>
      </div>

      {err && <div className="inv-warning" style={{ marginBottom: 12 }}>{err}</div>}

      {loading && <div className="cacm-loading">Loading dashboard…</div>}

      {!loading && !err && isEmpty && (
        <div className="cacm-empty">
          No dashboard data yet for this run. Try again once the run completes.
        </div>
      )}

      {!loading && !err && data && !isEmpty && <DashboardCharts data={data} />}
    </AppShell>
  );
}
