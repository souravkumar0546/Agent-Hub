import React, { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import AppShell from "../../components/AppShell.jsx";
import { getProcesses } from "../api.js";
import "../styles.css";

/** ProcessesPage — landing for /agents/cacm. Shows the CACM intro plus a
 *  grid of business-process tiles. Clicking a tile drills into the
 *  per-process KRI list at /agents/cacm/processes/:processKey.
 */
export default function ProcessesPage() {
  const navigate = useNavigate();
  const [processes, setProcesses] = useState(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    let cancelled = false;
    getProcesses()
      .then((data) => {
        if (cancelled) return;
        setProcesses(data.processes || []);
      })
      .catch((e) => {
        if (cancelled) return;
        setErr(
          e.response?.data?.detail ||
            e.message ||
            "Failed to load CACM processes."
        );
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <AppShell crumbs={["Agent Hub", "Prism"]}>
      <div className="cacm-hero">
        <div style={{ flex: 1, minWidth: 0 }}>
          <h1 className="page-title" style={{ marginBottom: 4 }}>
            Continuous Audit & Continuous Monitoring
          </h1>
          <div className="page-subtitle" style={{ marginBottom: 8 }}>
            Pick a business process to explore its Key Risk Indicators.
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

      <div className="cacm-intro-card">
        <p className="cacm-intro-para">
          The Continuous Audit & Continuous Monitoring (CACM) solution enables
          organizations to proactively identify control gaps, policy violations,
          and transactional anomalies across enterprise systems through
          automated, always-on risk monitoring. By continuously evaluating ERP
          data against control rules, the platform surfaces high-risk
          exceptions, and generates audit-ready insights for timely corrective
          action.
        </p>
        <p className="cacm-intro-para">
          Each KRI (Key Risk Indicator) is mapped to underlying source tables,
          business logic, risk thresholds, and recommended remediation actions,
          enabling a transparent and traceable control monitoring framework.
        </p>
      </div>

      {err && <div className="inv-warning">{err}</div>}

      {!err && processes === null && (
        <div className="cacm-loading">Loading processes…</div>
      )}

      {!err && processes !== null && processes.length === 0 && (
        <div className="cacm-empty">No processes are configured.</div>
      )}

      {!err && processes && processes.length > 0 && (
        <div className="cacm-tile-grid">
          {processes.map((p) => (
            <button
              type="button"
              key={p.key}
              className="cacm-process-card"
              onClick={() => navigate(`/agents/cacm/processes/${p.key}`)}
            >
              <div className="cacm-process-card-header">
                <div className="cacm-process-card-name">{p.name}</div>
              </div>
              <div className="cacm-process-card-intro">{p.intro}</div>
              <div className="cacm-process-card-footer">
                <span className="cacm-process-card-arrow">→</span>
              </div>
            </button>
          ))}
        </div>
      )}
    </AppShell>
  );
}
