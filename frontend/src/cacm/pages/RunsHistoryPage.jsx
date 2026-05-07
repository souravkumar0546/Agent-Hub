import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import AppShell from "../../components/AppShell.jsx";
import { listRuns } from "../api.js";
import "../styles.css";

function formatDate(iso) {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString([], {
      dateStyle: "medium",
      timeStyle: "short",
    });
  } catch {
    return iso;
  }
}

export default function RunsHistoryPage() {
  const [runs, setRuns] = useState(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    let cancelled = false;
    listRuns()
      .then((data) => {
        if (cancelled) return;
        // Backend may return { runs: [...] } or just an array; normalize.
        const items = Array.isArray(data) ? data : data.runs || data.items || [];
        setRuns(items);
      })
      .catch((e) => {
        if (cancelled) return;
        setErr(e.response?.data?.detail || e.message || "Failed to load runs.");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <AppShell crumbs={["Agent Hub", "CACM", "Runs"]}>
      <div className="cacm-hero">
        <div style={{ flex: 1, minWidth: 0 }}>
          <h1 className="page-title" style={{ marginBottom: 4 }}>
            CACM Run History
          </h1>
          <div className="page-subtitle" style={{ marginBottom: 8 }}>
            Recent KPI executions for your organisation.
          </div>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <Link to="/agents/cacm" className="btn btn-primary">
            + New run
          </Link>
          <Link to="/" className="btn">
            ← Agent Hub
          </Link>
        </div>
      </div>

      {err && <div className="inv-warning">{err}</div>}

      {!err && runs === null && <div className="cacm-loading">Loading runs…</div>}

      {!err && runs !== null && runs.length === 0 && (
        <div className="cacm-empty">No CACM runs yet. Pick a KPI from the library to start one.</div>
      )}

      {!err && runs && runs.length > 0 && (
        <div className="cacm-runs-list">
          {runs.map((r) => {
            const status = (r.status || "running").toLowerCase();
            const target =
              status === "succeeded"
                ? `/agents/cacm/runs/${r.id}/dashboard`
                : `/agents/cacm/run/${r.id}`;
            return (
              <Link key={r.id} to={target} className="cacm-run-row">
                <div>
                  <div className="cacm-run-name">{r.kpi_type || `Run #${r.id}`}</div>
                  <div className="cacm-run-meta">
                    {r.process ? `${r.process} · ` : ""}#{r.id}
                  </div>
                </div>
                <div className={`cacm-run-status cacm-run-status--${status}`}>
                  {status}
                </div>
                <div className="cacm-run-meta">{formatDate(r.started_at)}</div>
                <div className="cacm-run-meta">
                  {r.total_exceptions != null
                    ? `${Number(r.total_exceptions).toLocaleString()} exceptions`
                    : "—"}
                </div>
                <div style={{ color: "var(--ink-muted)", fontSize: 12 }}>→</div>
              </Link>
            );
          })}
        </div>
      )}
    </AppShell>
  );
}
