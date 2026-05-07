import React, { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import AppShell from "../../components/AppShell.jsx";
import { getLibrary, startRun } from "../api.js";
import ProcessTile from "../components/ProcessTile.jsx";
import "../styles.css";

/** Library landing — fetches `/library` and renders one ProcessTile per
 *  process, each containing the KPIs available for that process. Clicking
 *  a KPI POSTs `/runs` and navigates to the run detail page so the user
 *  can watch the streaming events.
 */
export default function LibraryPage() {
  const navigate = useNavigate();
  const [processes, setProcesses] = useState(null);
  const [err, setErr] = useState("");
  const [starting, setStarting] = useState(false);
  const [startError, setStartError] = useState("");

  useEffect(() => {
    let cancelled = false;
    getLibrary()
      .then((data) => {
        if (cancelled) return;
        setProcesses(data.processes || []);
      })
      .catch((e) => {
        if (cancelled) return;
        setErr(e.response?.data?.detail || e.message || "Failed to load CACM library.");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  async function handleSelectKpi(kpi) {
    if (starting) return;
    setStarting(true);
    setStartError("");
    try {
      const data = await startRun(kpi.type);
      if (!data?.run_id) {
        throw new Error("Backend did not return a run_id.");
      }
      navigate(`/agents/cacm/run/${data.run_id}`);
    } catch (e) {
      setStartError(
        e.response?.data?.detail || e.message || "Failed to start run."
      );
    } finally {
      setStarting(false);
    }
  }

  return (
    <AppShell crumbs={["Agent Hub", "Prism"]}>
      <div className="cacm-hero">
        <div style={{ flex: 1, minWidth: 0 }}>
          <h1 className="page-title" style={{ marginBottom: 4 }}>
            Continuous Audit & Continuous Monitoring
          </h1>
          <div className="page-subtitle" style={{ marginBottom: 8 }}>
            Pick a KPI to walk it through extraction → transformation → rule
            execution → exceptions → dashboard.
          </div>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <Link to="/agents/cacm/runs" className="btn">
            Run history
          </Link>
          <Link to="/" className="btn">
            ← Agent Hub
          </Link>
        </div>
      </div>

      {err && <div className="inv-warning">{err}</div>}
      {startError && <div className="inv-warning">{startError}</div>}
      {starting && (
        <div className="cacm-loading">Starting run…</div>
      )}

      {!err && processes === null && (
        <div className="cacm-loading">Loading CACM library…</div>
      )}

      {!err && processes !== null && processes.length === 0 && (
        <div className="cacm-empty">No processes are configured for this org.</div>
      )}

      {!err && processes && processes.length > 0 && (
        <div className="cacm-process-grid">
          {processes.map((p) => (
            <ProcessTile key={p.name} process={p} onSelect={handleSelectKpi} />
          ))}
        </div>
      )}
    </AppShell>
  );
}
