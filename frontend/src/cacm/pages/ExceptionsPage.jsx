import React, { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import AppShell from "../../components/AppShell.jsx";
import {
  downloadCacmFile,
  exceptionsCsvUrl,
  exceptionsXlsxUrl,
  getExceptions,
  getRun,
} from "../api.js";
import ExceptionTable from "../components/ExceptionTable.jsx";
import "../styles.css";

const RISK_OPTIONS = ["All", "High", "Medium", "Low"];

export default function ExceptionsPage() {
  const { runId } = useParams();
  const [risk, setRisk] = useState("All");
  const [data, setData] = useState(null);
  const [run, setRun] = useState(null);
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(true);
  const [downloading, setDownloading] = useState(false);

  useEffect(() => {
    let cancelled = false;
    if (!runId) return;
    getRun(runId)
      .then((r) => {
        if (!cancelled) setRun(r);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [runId]);

  useEffect(() => {
    let cancelled = false;
    if (!runId) return;
    setLoading(true);
    setErr("");
    getExceptions(runId, { risk: risk === "All" ? undefined : risk })
      .then((d) => {
        if (cancelled) return;
        setData(d);
      })
      .catch((e) => {
        if (cancelled) return;
        setErr(e.response?.data?.detail || e.message || "Failed to load exceptions.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [runId, risk]);

  async function handleDownload(format) {
    setDownloading(true);
    try {
      const path = format === "csv" ? exceptionsCsvUrl(runId) : exceptionsXlsxUrl(runId);
      const fallback = `cacm_exceptions_${runId}.${format === "csv" ? "csv" : "xlsx"}`;
      await downloadCacmFile(path, fallback);
    } catch (e) {
      setErr(e.response?.data?.detail || e.message || "Download failed.");
    } finally {
      setDownloading(false);
    }
  }

  return (
    <AppShell crumbs={["Agent Hub", "Prism", `Run ${runId}`, "Exceptions"]}>
      <div className="cacm-hero">
        <div style={{ flex: 1, minWidth: 0 }}>
          <h1 className="page-title" style={{ marginBottom: 4 }}>
            Exceptions
          </h1>
          <div className="page-subtitle" style={{ marginBottom: 8 }}>
            {run?.kpi_type ? `${run.kpi_type} · run #${runId}` : `Run #${runId}`}
          </div>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <Link to={`/agents/cacm/run/${runId}`} className="btn">
            ← Back to run
          </Link>
          <Link to={`/agents/cacm/runs/${runId}/dashboard`} className="btn">
            Dashboard
          </Link>
        </div>
      </div>

      <div className="cacm-toolbar" style={{ marginBottom: 16 }}>
        <div className="cacm-toolbar-group filter-row" style={{ marginBottom: 0 }}>
          <span style={{ color: "var(--ink-dim)", fontSize: 13, marginRight: 4 }}>
            Risk:
          </span>
          {RISK_OPTIONS.map((r) => (
            <button
              key={r}
              type="button"
              className={`filter-chip${risk === r ? " active" : ""}`}
              onClick={() => setRisk(r)}
            >
              {r}
            </button>
          ))}
        </div>
        <div className="cacm-toolbar-group">
          <button
            type="button"
            className="btn"
            disabled={downloading}
            onClick={() => handleDownload("csv")}
          >
            Download CSV
          </button>
          <button
            type="button"
            className="btn btn-primary"
            disabled={downloading}
            onClick={() => handleDownload("xlsx")}
          >
            Download Excel
          </button>
        </div>
      </div>

      {err && <div className="inv-warning" style={{ marginBottom: 12 }}>{err}</div>}

      {loading && <div className="cacm-loading">Loading exceptions…</div>}

      {!loading && data && (
        <>
          <div className="cacm-section-title">
            {data.total ?? data.items?.length ?? 0} exceptions
            {risk !== "All" ? ` (${risk})` : ""}
          </div>
          <ExceptionTable rows={data.items || []} process={run?.process} />
        </>
      )}
    </AppShell>
  );
}
