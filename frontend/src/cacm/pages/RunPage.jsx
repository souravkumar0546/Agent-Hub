import React, { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import AppShell from "../../components/AppShell.jsx";
import {
  downloadCacmFile,
  exceptionsCsvUrl,
  exceptionsXlsxUrl,
  extractedTableDownloadUrl,
  getDashboard,
  getExceptions,
  getLibrary,
  getRun,
  getStageData,
} from "../api.js";
import DashboardCharts from "../components/DashboardCharts.jsx";
import ExceptionTable from "../components/ExceptionTable.jsx";
import "../styles.css";

/* ────────────────────────────────────────────────────────────────────────
 * Wizard structure
 *
 * The CACM run is gated client-side into 6 stages. The pipeline itself
 * still runs end-to-end on POST /runs (kicked off from LibraryPage).
 * Each "Run" button here just (a) calls the matching /stage/* endpoint
 * fresh, (b) shows a brief spinner, and (c) renders details. The user
 * controls the *reveal* sequence — exactly the demo experience asked
 * for, without splitting the backend pipeline.
 * ──────────────────────────────────────────────────────────────────── */

const STAGE_ORDER = [
  { key: "extraction", label: "Data Extraction" },
  { key: "transformation", label: "Data Transformation" },
  { key: "loading", label: "Data Loading" },
  { key: "rules", label: "Rule Engine" },
  { key: "exceptions", label: "Exception Report" },
  { key: "dashboard", label: "Dashboard" },
];

// Per-stage spinner duration after the user (or autopilot) hits "Run". Longer
// values make the demo feel like real work is happening — fetching, parsing,
// computing — instead of an instant flicker.
const RUN_FAKE_DELAY_MS = 2800;
// How long a completed stage stays visible under autopilot before we
// auto-advance to the next stage. Long enough that a viewer can actually
// read the results panel.
const AUTOPILOT_STAGE_PAUSE_MS = 3500;
// Pause after the rule engine completes before navigating to the Exception
// Report. Slightly longer so the totals (records / exceptions / risk
// distribution) sit on screen as the climax.
const AUTOPILOT_FINISH_PAUSE_MS = 4000;

function fakeDelay(ms = RUN_FAKE_DELAY_MS) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function Spinner({ label = "Running…" }) {
  return (
    <div className="cacm-wizard-spinner">
      <span className="cacm-wizard-spinner-dot" />
      <span className="cacm-wizard-spinner-dot" />
      <span className="cacm-wizard-spinner-dot" />
      <span>{label}</span>
    </div>
  );
}

function StageRail({ currentStage, completedStages, onJumpTo }) {
  const completed = new Set(completedStages);
  return (
    <nav className="cacm-wizard-rail" aria-label="CACM stages">
      <div className="cacm-wizard-rail-title">Steps</div>
      {STAGE_ORDER.map((stage, idx) => {
        const isCurrent = stage.key === currentStage;
        const isDone = completed.has(stage.key);
        const isClickable = isDone || isCurrent;
        let cls = "cacm-wizard-rail-item";
        if (isCurrent) cls += " cacm-wizard-rail-item--current";
        else if (isDone) cls += " cacm-wizard-rail-item--done";
        if (isClickable) cls += " cacm-wizard-rail-item--clickable";
        return (
          <button
            type="button"
            key={stage.key}
            className={cls}
            disabled={!isClickable}
            onClick={() => isClickable && onJumpTo(stage.key)}
          >
            <span className="cacm-wizard-rail-bullet">
              {isDone ? "✓" : idx + 1}
            </span>
            {stage.label}
          </button>
        );
      })}
    </nav>
  );
}

/* ──────────────────────────── Stage 1: Extraction ─────────────────── */

function ExtractionStage({
  runId,
  kpiMeta,
  onComplete,
  completed,
  autopilot,
  onScheduleAll,
}) {
  const [running, setRunning] = useState(false);
  const [data, setData] = useState(null);
  const [err, setErr] = useState("");
  const [source, setSource] = useState("SAP ECC");

  const planned = kpiMeta?.source_tables || [];

  async function handleRun() {
    setRunning(true);
    setErr("");
    try {
      const [stage] = await Promise.all([
        getStageData(runId, "extraction"),
        fakeDelay(),
      ]);
      setData(stage);
    } catch (e) {
      setErr(e.response?.data?.detail || e.message || "Extraction failed.");
    } finally {
      setRunning(false);
    }
  }

  // Autopilot: when on, auto-fire the run on mount (or when autopilot flips
  // on later) so the demo plays itself end-to-end.
  useEffect(() => {
    if (autopilot && !data && !running) {
      handleRun();
    }
    // We deliberately depend only on `autopilot` so a re-render doesn't
    // double-trigger; `data`/`running` checks above guard the body.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autopilot]);

  // Once the run finishes under autopilot, advance after a short pause so
  // the audience sees the extracted-tables panel render.
  useEffect(() => {
    if (autopilot && data && !completed) {
      const t = setTimeout(() => onComplete(), AUTOPILOT_STAGE_PAUSE_MS);
      return () => clearTimeout(t);
    }
  }, [autopilot, data, completed, onComplete]);

  async function handleDownload(tableName) {
    try {
      await downloadCacmFile(
        extractedTableDownloadUrl(runId, tableName),
        `${tableName}.csv`
      );
    } catch (e) {
      setErr(e.response?.data?.detail || e.message || "Download failed.");
    }
  }

  return (
    <div className="cacm-wizard-stage">
      <div>
        <h2 className="cacm-wizard-stage-title">Stage 1 — Data Extraction</h2>
        <p className="cacm-wizard-stage-subtitle">
          Pull source data from SAP ECC / Datawarehouse to Prism staging area.
        </p>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 10,
            marginTop: 12,
            flexWrap: "wrap",
          }}
        >
          <label
            htmlFor="cacm-data-source"
            style={{ fontSize: 13, color: "var(--ink-dim)" }}
          >
            Data source
          </label>
          <select
            id="cacm-data-source"
            value={source}
            onChange={(e) => setSource(e.target.value)}
            disabled={running || !!data}
            style={{
              padding: "6px 10px",
              borderRadius: 6,
              border: "1px solid var(--border)",
              background: "var(--bg-card)",
              color: "var(--ink)",
              fontSize: 13,
            }}
          >
            <option value="SAP ECC">SAP ECC</option>
            <option value="SAP S/4HANA">SAP S/4HANA</option>
            <option value="Datawarehouse">Datawarehouse</option>
            <option value="Oracle EBS">Oracle EBS</option>
            <option value="Custom CSV upload">Custom CSV upload</option>
          </select>
        </div>
      </div>

      <div>
        <div className="cacm-wizard-section-label">Planned source tables</div>
        <div className="cacm-wizard-chip-list">
          {(data?.planned_tables || planned).map((t) => (
            <span key={t} className="cacm-wizard-chip">{t}</span>
          ))}
          {(data?.planned_tables || planned).length === 0 && (
            <span style={{ color: "var(--ink-muted)", fontSize: 13 }}>—</span>
          )}
        </div>
      </div>

      {err && <div className="inv-warning">{err}</div>}

      {!data && !running && (
        <p className="cacm-wizard-stage-subtitle">
          Click <strong>Run Data Extraction</strong> to begin.
        </p>
      )}
      {running && <Spinner label="Connecting to SAP and extracting tables…" />}

      {data && (
        <>
          <div className="cacm-wizard-section-label">
            Extracted tables ({data.tables.length})
          </div>
          <div className="cacm-wizard-table-grid">
            {data.tables.map((t) => (
              <ExtractedTableCard
                key={t.name}
                table={t}
                onDownload={() => handleDownload(t.name)}
              />
            ))}
          </div>
        </>
      )}

      <div className="cacm-wizard-actions">
        {!data && (
          <>
            <button
              type="button"
              className="btn btn-primary"
              onClick={handleRun}
              disabled={running || autopilot}
            >
              {running ? "Running…" : "Run Data Extraction"}
            </button>
            {!autopilot && onScheduleAll && (
              <button
                type="button"
                className="btn"
                onClick={onScheduleAll}
                disabled={running}
                title="Auto-run every stage and land on the Exception Report when done."
              >
                ▶︎ Schedule whole process
              </button>
            )}
            {autopilot && (
              <span
                style={{
                  fontSize: 12,
                  color: "var(--ink-muted)",
                  alignSelf: "center",
                }}
              >
                Auto-pilot engaged — Prism is driving the run for you.
              </span>
            )}
          </>
        )}
        {data && !completed && (
          <button
            type="button"
            className="btn btn-primary"
            onClick={onComplete}
            disabled={autopilot}
          >
            Proceed to Transformation →
          </button>
        )}
        {data && completed && (
          <button type="button" className="btn" onClick={onComplete}>
            Continue →
          </button>
        )}
      </div>
    </div>
  );
}

/** Card that wraps one extracted table — header + preview toggle + download. */
function ExtractedTableCard({ table, onDownload }) {
  const [expanded, setExpanded] = useState(false);
  return (
    <div className="cacm-wizard-table-card">
      <div className="cacm-wizard-table-card-head">
        <span className="cacm-wizard-table-name">{table.name}</span>
        <span className="cacm-wizard-table-rowcount">
          {table.row_count.toLocaleString()} rows
        </span>
      </div>
      <SampleRowsPreview
        rows={table.sample_rows}
        columns={table.columns}
        expanded={expanded}
      />
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        <button
          type="button"
          className="btn"
          onClick={() => setExpanded((v) => !v)}
        >
          {expanded ? "Collapse preview" : "Preview"}
        </button>
        <button type="button" className="btn" onClick={onDownload}>
          Download CSV
        </button>
      </div>
    </div>
  );
}

function SampleRowsPreview({ rows, columns, expanded = false }) {
  if (!rows || rows.length === 0) {
    return (
      <div style={{ fontSize: 12, color: "var(--ink-muted)" }}>
        No rows to preview.
      </div>
    );
  }
  // Compact view: 5 rows × 6 columns. Expanded view: all rows × all columns
  // (with horizontal scroll on the wrapper).
  const allCols = columns || Object.keys(rows[0]);
  const visibleCols = expanded ? allCols : allCols.slice(0, 6);
  const visibleRows = expanded ? rows : rows.slice(0, 5);
  return (
    <div
      className="cacm-wizard-mini-table-wrapper"
      style={expanded ? { maxHeight: 320, overflowY: "auto" } : undefined}
    >
      <table className="cacm-wizard-mini-table">
        <thead>
          <tr>
            {visibleCols.map((c) => (
              <th key={c}>{c}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {visibleRows.map((row, i) => (
            <tr key={i}>
              {visibleCols.map((c) => (
                <td key={c}>
                  {row[c] === null || row[c] === undefined
                    ? "—"
                    : String(row[c])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {!expanded && (rows.length > 5 || allCols.length > 6) && (
        <div
          style={{
            fontSize: 11,
            color: "var(--ink-muted)",
            padding: "4px 8px",
          }}
        >
          {rows.length > 5 && `+${rows.length - 5} more rows`}
          {rows.length > 5 && allCols.length > 6 && " · "}
          {allCols.length > 6 && `${allCols.length - 6} more columns hidden`}
        </div>
      )}
    </div>
  );
}

/* ──────────────────────────── Stage 2: Transformation ─────────────── */

function TransformationStage({ runId, onComplete, completed, autopilot }) {
  const [running, setRunning] = useState(false);
  const [data, setData] = useState(null);
  const [extractedTables, setExtractedTables] = useState(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    if (autopilot && !data && !running) handleRun();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autopilot]);

  useEffect(() => {
    if (autopilot && data && !completed) {
      const t = setTimeout(() => onComplete(), AUTOPILOT_STAGE_PAUSE_MS);
      return () => clearTimeout(t);
    }
  }, [autopilot, data, completed, onComplete]);

  async function handleRun() {
    setRunning(true);
    setErr("");
    try {
      // Fetch transformation stats AND the underlying extracted tables in
      // parallel so we can render the same per-table cards as Stage 1, but
      // labelled as "Transformed datasets" — the user wants extracted tables
      // surfaced as the transformed view (no separate derived-table block).
      const [stage, extraction] = await Promise.all([
        getStageData(runId, "transformation"),
        getStageData(runId, "extraction").catch(() => null),
        fakeDelay(),
      ]);
      setData(stage);
      setExtractedTables(extraction?.tables || []);
    } catch (e) {
      setErr(e.response?.data?.detail || e.message || "Transformation failed.");
    } finally {
      setRunning(false);
    }
  }

  async function handleDownload(tableName) {
    try {
      await downloadCacmFile(
        extractedTableDownloadUrl(runId, tableName),
        `${tableName}.csv`
      );
    } catch (e) {
      setErr(e.response?.data?.detail || e.message || "Download failed.");
    }
  }

  return (
    <div className="cacm-wizard-stage">
      <div>
        <h2 className="cacm-wizard-stage-title">
          Stage 2 — Data Transformation
        </h2>
        <p className="cacm-wizard-stage-subtitle">
          Cleanse, parse, and standardize the extracted tables so the rule
          engine sees a uniform shape.
        </p>
      </div>

      <PreRunRulesList runId={runId} />

      {err && <div className="inv-warning">{err}</div>}

      {!data && !running && (
        <p className="cacm-wizard-stage-subtitle">
          Click <strong>Run Transformation</strong> to begin.
        </p>
      )}
      {running && <Spinner label="Cleansing, parsing, standardizing…" />}

      {data && (
        <>
          <div className="cacm-wizard-stat-row">
            <div className="cacm-wizard-stat">
              <span className="cacm-wizard-stat-label">Rows in</span>
              <span className="cacm-wizard-stat-value">
                {data.rows_in.toLocaleString()}
              </span>
            </div>
            <div className="cacm-wizard-stat">
              <span className="cacm-wizard-stat-label">Rows after transform</span>
              <span className="cacm-wizard-stat-value">
                {data.rows_out.toLocaleString()}
              </span>
            </div>
          </div>
          {extractedTables && extractedTables.length > 0 && (
            <>
              <div className="cacm-wizard-section-label">
                Transformed datasets ({extractedTables.length})
              </div>
              <div className="cacm-wizard-table-grid">
                {extractedTables.map((t) => (
                  <ExtractedTableCard
                    key={t.name}
                    table={t}
                    onDownload={() => handleDownload(t.name)}
                  />
                ))}
              </div>
            </>
          )}
        </>
      )}

      <div className="cacm-wizard-actions">
        {!data && (
          <button
            type="button"
            className="btn btn-primary"
            onClick={handleRun}
            disabled={running}
          >
            {running ? "Running…" : "Run Transformation"}
          </button>
        )}
        {data && (
          <button
            type="button"
            className="btn btn-primary"
            onClick={onComplete}
          >
            {completed ? "Continue" : "Proceed to Loading"} →
          </button>
        )}
      </div>
    </div>
  );
}

/** Pre-run preview: ask the transformation endpoint for `rules_applied`
 *  and render them above the Run button so the user knows what's about
 *  to happen. Falls back to a hardcoded list if the call fails. */
function PreRunRulesList({ runId }) {
  const [rules, setRules] = useState(null);
  useEffect(() => {
    let cancelled = false;
    getStageData(runId, "transformation")
      .then((d) => {
        if (cancelled) return;
        setRules(d.rules_applied || []);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [runId]);
  if (!rules || rules.length === 0) return null;
  return (
    <div>
      <div className="cacm-wizard-section-label">
        Transformations that will be applied
      </div>
      <ul className="cacm-wizard-bullet-list">
        {rules.map((r, i) => (
          <li key={i}>{r}</li>
        ))}
      </ul>
    </div>
  );
}

/* ──────────────────────────── Stage 3: Loading ─────────────────────── */

function LoadingStage({ runId, onComplete, completed, autopilot }) {
  const [running, setRunning] = useState(false);
  const [plan, setPlan] = useState(null); // pre-run preview
  const [data, setData] = useState(null); // post-run with loaded checks
  const [tablesDone, setTablesDone] = useState(0);
  const [err, setErr] = useState("");

  useEffect(() => {
    if (autopilot && !data && !running && plan) handleRun();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autopilot, plan]);

  useEffect(() => {
    if (autopilot && data && !completed) {
      const t = setTimeout(() => onComplete(), AUTOPILOT_STAGE_PAUSE_MS);
      return () => clearTimeout(t);
    }
  }, [autopilot, data, completed, onComplete]);

  // Pre-fetch the plan so we can list target tables before the user runs.
  useEffect(() => {
    let cancelled = false;
    getStageData(runId, "loading")
      .then((d) => {
        if (cancelled) return;
        setPlan(d);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [runId]);

  async function handleRun() {
    setRunning(true);
    setErr("");
    setTablesDone(0);
    try {
      const stage = await getStageData(runId, "loading");
      // Stagger checkmark reveal so each target table looks like it loads
      // sequentially. ~140 ms per row keeps total under ~1s for 6 targets.
      const total = stage.target_tables.length;
      for (let i = 1; i <= total; i++) {
        await new Promise((r) => setTimeout(r, 140));
        setTablesDone(i);
      }
      setData(stage);
    } catch (e) {
      setErr(e.response?.data?.detail || e.message || "Data load failed.");
    } finally {
      setRunning(false);
    }
  }

  const visibleTables = data
    ? data.target_tables
    : plan
    ? plan.target_tables
    : [];

  return (
    <div className="cacm-wizard-stage">
      <div>
        <h2 className="cacm-wizard-stage-title">Stage 3 — Data Loading</h2>
        <p className="cacm-wizard-stage-subtitle">
          Load the transformed dataset into the Prism datamart so that we can
          run the rule engine.
        </p>
      </div>

      <div>
        <div className="cacm-wizard-section-label">Target tables</div>
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {visibleTables.map((t, i) => {
            const showCheck = data || (running && i < tablesDone);
            return (
              <div key={t.name} className="cacm-wizard-load-row">
                <div>
                  <span className="cacm-wizard-load-name">{t.name}</span>
                  {data && (
                    <span style={{ marginLeft: 12, color: "var(--ink-muted)", fontSize: 12 }}>
                      {t.row_count.toLocaleString()} rows
                    </span>
                  )}
                </div>
                {showCheck ? (
                  <span className="cacm-wizard-load-status">✓ Loaded</span>
                ) : (
                  <span style={{ color: "var(--ink-muted)", fontSize: 12 }}>
                    {running ? "Loading…" : "Pending"}
                  </span>
                )}
              </div>
            );
          })}
          {visibleTables.length === 0 && (
            <div style={{ color: "var(--ink-muted)", fontSize: 13 }}>
              Loading target plan…
            </div>
          )}
        </div>
      </div>

      {err && <div className="inv-warning">{err}</div>}

      <div className="cacm-wizard-actions">
        {!data && (
          <button
            type="button"
            className="btn btn-primary"
            onClick={handleRun}
            disabled={running}
          >
            {running ? "Loading…" : "Run Data Load"}
          </button>
        )}
        {data && (
          <button
            type="button"
            className="btn btn-primary"
            onClick={onComplete}
          >
            {completed ? "Continue" : "Proceed to Rule Engine"} →
          </button>
        )}
      </div>
    </div>
  );
}

/* ──────────────────────────── Stage 4: Rule Engine ─────────────────── */

function RuleEngineStage({ runId, onComplete, completed, autopilot }) {
  const [plan, setPlan] = useState(null);
  const [running, setRunning] = useState(false);
  const [data, setData] = useState(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    let cancelled = false;
    getStageData(runId, "rule-engine")
      .then((d) => {
        if (cancelled) return;
        setPlan(d);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [runId]);

  // Autopilot: auto-fire once the plan is loaded; the parent will navigate
  // to /exceptions after `completed` flips, so no auto-advance here.
  useEffect(() => {
    if (autopilot && plan && !data && !running) handleRun();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autopilot, plan]);

  useEffect(() => {
    if (autopilot && data && !completed) {
      const t = setTimeout(() => onComplete(), AUTOPILOT_STAGE_PAUSE_MS);
      return () => clearTimeout(t);
    }
  }, [autopilot, data, completed, onComplete]);

  async function handleRun() {
    setRunning(true);
    setErr("");
    try {
      const [stage] = await Promise.all([
        getStageData(runId, "rule-engine"),
        fakeDelay(),
      ]);
      setData(stage);
    } catch (e) {
      setErr(e.response?.data?.detail || e.message || "Rule engine failed.");
    } finally {
      setRunning(false);
    }
  }

  const conditions = (data || plan)?.conditions || [];
  const sources = (data || plan)?.source_tables || [];

  return (
    <div className="cacm-wizard-stage">
      <div>
        <h2 className="cacm-wizard-stage-title">Stage 4 — Rule Engine</h2>
        <p className="cacm-wizard-stage-subtitle">
          Apply the configured KPI rule against the prepared data and
          generate exceptions where the rule's conditions are met.
        </p>
      </div>

      {sources.length > 0 && (
        <div>
          <div className="cacm-wizard-section-label">Tables in scope</div>
          <div className="cacm-wizard-chip-list">
            {sources.map((t) => (
              <span key={t} className="cacm-wizard-chip">{t}</span>
            ))}
          </div>
        </div>
      )}

      {conditions.length > 0 && (
        <div>
          <div className="cacm-wizard-section-label">
            Rule conditions (applied during evaluation)
          </div>
          <ul className="cacm-wizard-bullet-list">
            {conditions.map((c, i) => (
              <li key={i}>{c}</li>
            ))}
          </ul>
        </div>
      )}

      {err && <div className="inv-warning">{err}</div>}

      {!data && running && <Spinner label="Evaluating rule against transactions…" />}
      {!data && !running && (
        <p className="cacm-wizard-stage-subtitle">
          Click <strong>Run Rule Engine</strong> to evaluate.
        </p>
      )}

      {data && (
        <div className="cacm-wizard-stat-row">
          <div className="cacm-wizard-stat">
            <span className="cacm-wizard-stat-label">Transactions evaluated</span>
            <span className="cacm-wizard-stat-value">
              {data.total_evaluated.toLocaleString()}
            </span>
          </div>
          <div className="cacm-wizard-stat">
            <span className="cacm-wizard-stat-label">Exceptions identified</span>
            <span
              className="cacm-wizard-stat-value"
              style={{ color: "#e74c3c" }}
            >
              {data.exceptions_generated.toLocaleString()}
            </span>
          </div>
        </div>
      )}

      <div className="cacm-wizard-actions">
        {!data && (
          <button
            type="button"
            className="btn btn-primary"
            onClick={handleRun}
            disabled={running}
          >
            {running ? "Running…" : "Run Rule Engine"}
          </button>
        )}
        {data && (
          <button
            type="button"
            className="btn btn-primary"
            onClick={onComplete}
          >
            {completed ? "Continue" : "View Exception Report"} →
          </button>
        )}
      </div>
    </div>
  );
}

/* ──────────────────────────── Stage 5: Exception Report ─────────────── */

const RISK_OPTIONS = ["All", "High", "Medium", "Low"];

function ExceptionReportStage({ runId, run, onComplete, completed }) {
  const [risk, setRisk] = useState("All");
  const [items, setItems] = useState(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");
  const [downloading, setDownloading] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setErr("");
    getExceptions(runId, { risk: risk === "All" ? undefined : risk })
      .then((d) => {
        if (cancelled) return;
        setItems(d.items || []);
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
    <div className="cacm-wizard-stage">
      <div>
        <h2 className="cacm-wizard-stage-title">Stage 5 — Exception Report</h2>
        <p className="cacm-wizard-stage-subtitle">
          {(items?.length ?? 0).toLocaleString()} exceptions identified
          {risk !== "All" ? ` (${risk})` : ""}.
        </p>
      </div>

      <div className="cacm-toolbar" style={{ marginBottom: 0 }}>
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

      {err && <div className="inv-warning">{err}</div>}
      {loading && <div className="cacm-loading">Loading exceptions…</div>}

      {!loading && items !== null && (
        <ExceptionTable rows={items} process={run?.process} />
      )}

      <div className="cacm-wizard-actions">
        <button
          type="button"
          className="btn btn-primary"
          onClick={onComplete}
        >
          {completed ? "View Dashboard" : "View Dashboard"} →
        </button>
      </div>
    </div>
  );
}

/* ──────────────────────────── Stage 6: Dashboard ───────────────────── */

// Empty filter state shared by the in-wizard dashboard so it renders the
// same Procurement-rich layout as the standalone /dashboard route.
const DASHBOARD_EMPTY_FILTERS = {
  companies: [],
  locations: [],
  risk_levels: [],
  aging_buckets: [],
  po_creators: [],
};

function DashboardStage({ runId }) {
  const [data, setData] = useState(null);
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState(DASHBOARD_EMPTY_FILTERS);

  // Initial load with empty filters.
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setErr("");
    getDashboard(runId, DASHBOARD_EMPTY_FILTERS)
      .then((d) => {
        if (cancelled) return;
        setData(d);
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

  // Re-fetch when filters change. Skip the no-op initial mount where
  // filters are empty AND we already have data from the initial fetch.
  useEffect(() => {
    if (!data) return undefined;
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
  }, [filters]);

  return (
    <div className="cacm-wizard-stage">
      <div>
        <h2 className="cacm-wizard-stage-title">Stage 6 — Dashboard</h2>
        <p className="cacm-wizard-stage-subtitle">
          Final view: aggregated risk and trend metrics for this run.
        </p>
      </div>
      {err && <div className="inv-warning">{err}</div>}
      {loading && <div className="cacm-loading">Loading dashboard…</div>}
      {!loading && data && (
        <DashboardCharts
          data={data}
          kpiType={data.kpi_type}
          filters={filters}
          onFiltersChange={setFilters}
          onClearFilters={() => setFilters(DASHBOARD_EMPTY_FILTERS)}
        />
      )}
    </div>
  );
}

/* ──────────────────────────── Top-level RunPage ────────────────────── */

export default function RunPage() {
  const { runId } = useParams();
  const navigate = useNavigate();

  const [run, setRun] = useState(null);
  const [kpiMeta, setKpiMeta] = useState(null);
  const [err, setErr] = useState("");

  const [currentStage, setCurrentStage] = useState("extraction");
  const [completedStages, setCompletedStages] = useState(() => new Set());
  // Autopilot mode: when on, every stage auto-runs and auto-advances on a
  // short timer so the demo plays itself end-to-end. Triggered by the
  // "Schedule whole process" button on Stage 1.
  const [autopilot, setAutopilot] = useState(false);

  // Once the rule engine completes under autopilot, jump straight to the
  // standalone Exceptions page — that's the "land them on the report"
  // outcome the user wants. The brief delay lets the rule-engine result
  // sit on screen for a moment so the audience sees the totals.
  useEffect(() => {
    if (autopilot && completedStages.has("rules")) {
      const t = setTimeout(() => {
        navigate(`/agents/cacm/runs/${runId}/exceptions`);
      }, AUTOPILOT_FINISH_PAUSE_MS);
      return () => clearTimeout(t);
    }
  }, [autopilot, completedStages, runId, navigate]);

  // Initial run summary fetch.
  useEffect(() => {
    let cancelled = false;
    if (!runId) return;
    getRun(runId)
      .then((data) => {
        if (cancelled) return;
        setRun(data);
      })
      .catch((e) => {
        if (cancelled) return;
        setErr(e.response?.data?.detail || e.message || "Failed to load run.");
      });
    return () => {
      cancelled = true;
    };
  }, [runId]);

  // Look up the KPI definition for the header.
  useEffect(() => {
    if (!run?.kpi_type) return;
    let cancelled = false;
    getLibrary()
      .then((lib) => {
        if (cancelled) return;
        for (const proc of lib.processes || []) {
          const match = (proc.kpis || []).find((k) => k.type === run.kpi_type);
          if (match) {
            setKpiMeta({ ...match, process: proc.name });
            return;
          }
        }
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [run?.kpi_type]);

  function advanceFrom(stageKey, nextKey) {
    setCompletedStages((prev) => {
      const next = new Set(prev);
      next.add(stageKey);
      return next;
    });
    if (nextKey) setCurrentStage(nextKey);
  }

  function handleJumpTo(stageKey) {
    setCurrentStage(stageKey);
  }

  // Re-fetch run once we know the pipeline is settled (best-effort: when
  // user reaches stage 5/6, totals must be hydrated). Cheap enough to
  // refetch on every advance to ensure current values.
  useEffect(() => {
    if (!runId) return;
    if (currentStage === "exceptions" || currentStage === "dashboard") {
      getRun(runId).then(setRun).catch(() => {});
    }
  }, [runId, currentStage]);

  return (
    <AppShell crumbs={["Agent Hub", "Prism", `Run ${runId}`]}>
      <div className="cacm-hero">
        <div style={{ flex: 1, minWidth: 0 }}>
          <h1 className="page-title" style={{ marginBottom: 4 }}>
            {kpiMeta?.name || run?.kpi_type || "CACM Run"}
          </h1>
          <div className="page-subtitle" style={{ marginBottom: 8 }}>
            {kpiMeta?.rule_objective ||
              kpiMeta?.description ||
              "Step-by-step Prism run — drive each stage with the buttons below."}
          </div>
          <div className="agent-meta">
            <span className="cap-tag cap-tag--accent">
              {run?.process || kpiMeta?.process || "Prism"}
            </span>
            {run?.kpi_type && <span className="cap-tag">{run.kpi_type}</span>}
          </div>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <Link to="/agents/cacm" className="btn">
            ← Library
          </Link>
        </div>
      </div>

      {err && <div className="inv-warning" style={{ marginBottom: 16 }}>{err}</div>}

      <div className="cacm-wizard">
        <StageRail
          currentStage={currentStage}
          completedStages={Array.from(completedStages)}
          onJumpTo={handleJumpTo}
        />

        <div>
          {currentStage === "extraction" && (
            <ExtractionStage
              runId={runId}
              kpiMeta={kpiMeta}
              completed={completedStages.has("extraction")}
              onComplete={() => advanceFrom("extraction", "transformation")}
              autopilot={autopilot}
              onScheduleAll={() => setAutopilot(true)}
            />
          )}
          {currentStage === "transformation" && (
            <TransformationStage
              runId={runId}
              completed={completedStages.has("transformation")}
              onComplete={() => advanceFrom("transformation", "loading")}
              autopilot={autopilot}
            />
          )}
          {currentStage === "loading" && (
            <LoadingStage
              runId={runId}
              completed={completedStages.has("loading")}
              onComplete={() => advanceFrom("loading", "rules")}
              autopilot={autopilot}
            />
          )}
          {currentStage === "rules" && (
            <RuleEngineStage
              runId={runId}
              completed={completedStages.has("rules")}
              onComplete={() => advanceFrom("rules", "exceptions")}
              autopilot={autopilot}
            />
          )}
          {currentStage === "exceptions" && (
            <ExceptionReportStage
              runId={runId}
              run={run}
              completed={completedStages.has("exceptions")}
              onComplete={() => advanceFrom("exceptions", "dashboard")}
            />
          )}
          {currentStage === "dashboard" && <DashboardStage runId={runId} />}
        </div>
      </div>
    </AppShell>
  );
}
