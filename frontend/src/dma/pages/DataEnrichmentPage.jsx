import React, { useState, useCallback, useRef, useEffect } from "react";
import FileUpload from "../components/FileUpload";
import PreviewTable from "../components/PreviewTable";
import StepProgress from "../components/StepProgress";
import { SingleColumnPicker } from "../components/ColumnPicker";
import { enrichmentEnrich, enrichmentDownload } from "../api";
import FlowDiagram, { DATA_ENRICHMENT_FLOW } from "../components/FlowDiagram";
import { useToast } from "../../components/Dialog.jsx";

const STEPS = [
  { label: "Reading uploaded file", sub: "Parsing Excel rows and columns" },
  { label: "Looking up CAS numbers on BLDPharm", sub: "Single-shot product page fetch per CAS" },
  { label: "Extracting breadcrumb taxonomy", sub: "Parsing product classification hierarchy" },
  { label: "Building enriched output", sub: "Appending Search Result & Source columns" },
];

export default function DataEnrichmentPage() {
  const toast = useToast();
  const [fileData, setFileData] = useState(null);
  const [casCol, setCasCol] = useState("");

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);
  const [pipelineStep, setPipelineStep] = useState(-1);

  const intervalRef = useRef(null);

  const onUpload = useCallback((data) => {
    setFileData(data);
    setCasCol("");
    setResult(null);
    setError("");
  }, []);

  useEffect(() => {
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, []);

  async function handleEnrich() {
    if (!fileData || !casCol) return;
    setLoading(true);
    setError("");
    setResult(null);
    setPipelineStep(0);

    let step = 0;
    intervalRef.current = setInterval(() => {
      step++;
      if (step < STEPS.length - 1) setPipelineStep(step);
    }, 5000);

    try {
      const data = await enrichmentEnrich(fileData.file, { casCol });
      clearInterval(intervalRef.current);
      setPipelineStep(STEPS.length);
      setResult(data);
    } catch (err) {
      clearInterval(intervalRef.current);
      setError(err.response?.data?.detail || err.message || "Enrichment failed");
    } finally {
      setLoading(false);
    }
  }

  async function handleDownload() {
    if (!fileData || !casCol) return;
    try {
      const blob = await enrichmentDownload(fileData.file, { casCol });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "enriched_data.xlsx";
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      console.error(e);
      toast(e.response?.data?.detail || e.message || "Download failed", { variant: "error" });
    }
  }

  const rows = result?.rows || [];
  const columns = result?.columns || [];
  const summary = result?.summary || {};
  const canRun = fileData && casCol;

  return (
    <div className="agent-layout">
      <div className="agent-sidebar">
        <FlowDiagram title={DATA_ENRICHMENT_FLOW.title} phases={DATA_ENRICHMENT_FLOW.phases} />
      </div>
      <div className="card">
        <h2>
          Echo
          <span style={{
            fontSize: 12,
            fontWeight: 500,
            color: 'var(--muted)',
            letterSpacing: '0.02em',
            marginLeft: 10,
          }}>
            Data Enrichment
          </span>
        </h2>
        <p className="muted">
          Enrich material data by looking up CAS numbers on BLDPharm to fetch product taxonomy and classification hierarchy.
        </p>

        <div className="divider" />
        <div className="section-label">Step 1 — Upload Data File</div>
        <FileUpload onUpload={onUpload} label="Upload Material Data File" />

        {fileData && (
          <>
            <PreviewTable
              columns={fileData.columns}
              rows={fileData.preview}
              rowCount={fileData.row_count}
              title="File Preview"
            />

            <div className="divider" />
            <div className="section-label">Step 2 — Select CAS Column</div>
            <SingleColumnPicker
              columns={fileData.columns}
              value={casCol}
              onChange={setCasCol}
              label="CAS Number Column"
              placeholder="Select CAS column..."
            />

            <div className="divider" />
            <div className="section-label">Step 3 — Run Enrichment</div>
            <p className="muted" style={{ marginBottom: 10 }}>
              Each CAS number will be looked up on BLDPharm. This may take a while for large files (~1 sec per row).
            </p>

            <div className="btn-row">
              <button className="btn btn-primary" disabled={!canRun || loading} onClick={handleEnrich}>
                {loading && <span className="spinner" />}
                {loading ? "Enriching..." : "Enrich Data"}
              </button>
            </div>
          </>
        )}

        {loading && <StepProgress steps={STEPS} currentStep={pipelineStep} />}

        {error && <div className="alert alert-error">{error}</div>}

        {result && !loading && (
          <>
            <div className="divider" />
            <div className="section-label">Results</div>

            <div className="metrics">
              <div className="metric">
                <div className="metric-value">{summary.total_rows ?? 0}</div>
                <div className="metric-label">Total Rows</div>
              </div>
              <div className="metric">
                <div className="metric-value" style={{ color: "var(--success)" }}>{summary.mapped ?? 0}</div>
                <div className="metric-label">Mapped</div>
              </div>
              <div className="metric">
                <div className="metric-value" style={{ color: "var(--warn)" }}>{summary.unmapped ?? 0}</div>
                <div className="metric-label">Unmapped</div>
              </div>
              {summary.errors > 0 && (
                <div className="metric">
                  <div className="metric-value" style={{ color: "var(--danger)" }}>{summary.errors}</div>
                  <div className="metric-label">Errors</div>
                </div>
              )}
            </div>

            <div className="btn-row">
              <button className="btn btn-primary" onClick={handleDownload}>
                Download Report
              </button>
            </div>

            {rows.length > 0 && columns.length > 0 && (
              <div className="table-container" style={{ maxHeight: 420 }}>
                <div className="table-header">Enriched Data — {rows.length} rows</div>
                <table>
                  <thead>
                    <tr>{columns.map((c) => <th key={c}>{c}</th>)}</tr>
                  </thead>
                  <tbody>
                    {rows.map((r, i) => (
                      <tr
                        key={i}
                        style={{
                          background: (r["Source / Evidence"] || "").includes("BLDPharm")
                            ? "#e8f5e9"
                            : undefined,
                        }}
                      >
                        {columns.map((c) => (
                          <td key={c}>{r[c] ?? ""}</td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
