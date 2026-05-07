import React, { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import AppShell from "../../components/AppShell.jsx";
import { getProcess, startRun } from "../api.js";
import "../styles.css";

/** ProcessDetailPage — /agents/cacm/processes/:processKey. Shows the
 *  process intro plus a vertical list of KRIs. Clicking a KRI starts a run.
 */
export default function ProcessDetailPage() {
  const { processKey } = useParams();
  const navigate = useNavigate();
  const [process, setProcess] = useState(null);
  const [err, setErr] = useState("");
  const [starting, setStarting] = useState(false);
  const [startError, setStartError] = useState("");

  useEffect(() => {
    let cancelled = false;
    setProcess(null);
    setErr("");
    getProcess(processKey)
      .then((data) => {
        if (cancelled) return;
        setProcess(data);
      })
      .catch((e) => {
        if (cancelled) return;
        const status = e.response?.status;
        if (status === 404) {
          setErr("Process not found.");
        } else {
          setErr(
            e.response?.data?.detail ||
              e.message ||
              "Failed to load process."
          );
        }
      });
    return () => {
      cancelled = true;
    };
  }, [processKey]);

  async function handleSelectKri(kri) {
    if (!kri.kpi_type || starting) return;
    setStarting(true);
    setStartError("");
    try {
      const data = await startRun(kri.kpi_type);
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
    <AppShell crumbs={["Agent Hub", "Prism", process?.name || "Process"]}>
      <div className="cacm-hero">
        <div style={{ flex: 1, minWidth: 0 }}>
          <Link to="/agents/cacm" className="cacm-back-link">
            ← All Processes
          </Link>
          <h1 className="page-title" style={{ marginTop: 8, marginBottom: 6 }}>
            {process?.name || "…"}
          </h1>
          {process && (
            <div className="page-subtitle" style={{ marginBottom: 10 }}>
              {process.intro}
            </div>
          )}
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <Link to="/agents/cacm/runs" className="btn">
            Run history
          </Link>
          <Link to="/agents/cacm" className="btn">
            ← All processes
          </Link>
        </div>
      </div>

      {err && <div className="inv-warning">{err}</div>}
      {startError && <div className="inv-warning">{startError}</div>}
      {starting && <div className="cacm-loading">Starting run…</div>}

      {!err && process === null && (
        <div className="cacm-loading">Loading process…</div>
      )}

      {!err && process && process.kris && process.kris.length > 0 && (
        <div className="cacm-kri-list">
          {process.kris.map((kri, idx) => (
            <button
              type="button"
              key={`${kri.kpi_type || "kri"}-${idx}`}
              className="cacm-kri-item cacm-kri-item--live"
              onClick={() => handleSelectKri(kri)}
              disabled={starting || !kri.kpi_type}
            >
              <div className="cacm-kri-item-main">
                <div className="cacm-kri-item-name">{kri.name}</div>
              </div>
              <span className="cacm-kri-item-arrow">→</span>
            </button>
          ))}
        </div>
      )}
    </AppShell>
  );
}
