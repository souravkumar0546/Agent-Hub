import React, { useState, useCallback, useRef, useEffect } from "react";
import FileUpload from "../components/FileUpload";
import PreviewTable from "../components/PreviewTable";
import StepProgress from "../components/StepProgress";
import { MultiColumnPicker, SingleColumnPicker } from "../components/ColumnPicker";
import { groupDuplicatesAnalyze, groupDuplicatesColoredXlsx } from "../api";
import FlowDiagram, { GROUP_DUPLICATES_FLOW } from "../components/FlowDiagram";
import { useToast } from "../../components/Dialog.jsx";

const STEPS = [
  { label: "Normalizing text & building TF-IDF matrices", sub: "Per-column char n-gram vectorization" },
  { label: "Computing pairwise similarity scores", sub: "Primary column pre-filter, then multi-column scoring" },
  { label: "Grouping duplicate pairs & assigning verdicts", sub: "EXACT MATCH / VERY LIKELY / POTENTIAL" },
  { label: "AI variant validation (size/qty check)", sub: "Azure OpenAI filtering same-product-different-variant pairs" },
  { label: "Building final report", sub: "Removing false positives, formatting output" },
];

/** Alternating color pairs per duplicate block */
const GROUP_BG = [
  ["#ffff99", "#fff176"],
  ["#ffcc80", "#ffb74d"],
  ["#a5d6a7", "#81c784"],
  ["#90caf9", "#64b5f6"],
  ["#ce93d8", "#ba68c8"],
  ["#ef9a9a", "#e57373"],
  ["#80deea", "#4dd0e1"],
  ["#ffe082", "#ffd54f"],
];

function rowBackground(r) {
  const bid = Number(r.block_id);
  if (Number.isNaN(bid)) return undefined;
  const pair = GROUP_BG[((bid % GROUP_BG.length) + GROUP_BG.length) % GROUP_BG.length];
  const fill = bid % 2 === 0 ? pair[0] : pair[1];
  return fill;
}

export default function GroupDuplicatesPage() {
  const toast = useToast();
  const [fileData, setFileData] = useState(null);
  const [selectedCols, setSelectedCols] = useState([]);
  const [identifierCol, setIdentifierCol] = useState("");
  const [threshold, setThreshold] = useState(0.85);
  const [aiFilter, setAiFilter] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);
  const [pipelineStep, setPipelineStep] = useState(-1);
  const intervalRef = useRef(null);

  const onUpload = useCallback((data) => {
    setFileData(data);
    setSelectedCols([]);
    setIdentifierCol("");
    setResult(null);
    setError("");
  }, []);

  useEffect(() => {
    return () => { if (intervalRef.current) clearInterval(intervalRef.current); };
  }, []);

  async function analyze() {
    if (!fileData || selectedCols.length === 0 || !identifierCol) return;
    setLoading(true);
    setError("");
    setResult(null);
    setPipelineStep(0);

    let step = 0;
    intervalRef.current = setInterval(() => {
      step++;
      if (step < STEPS.length - 1) setPipelineStep(step);
    }, 3000);

    try {
      const data = await groupDuplicatesAnalyze(fileData.file, {
        threshold,
        selectedCols,
        identifierCol,
        applyAiFilter: aiFilter,
      });
      clearInterval(intervalRef.current);
      setPipelineStep(STEPS.length);
      setResult(data);
    } catch (err) {
      clearInterval(intervalRef.current);
      setError(err.response?.data?.detail || err.message || "Analysis failed");
    } finally {
      setLoading(false);
    }
  }

  const rows = result?.rows || [];
  const resultCols = rows.length > 0 ? Object.keys(rows[0]) : [];
  const displayCols = resultCols.filter((c) => c !== "block_id");

  async function downloadColoredXlsx() {
    if (rows.length === 0) return;
    try {
      const blob = await groupDuplicatesColoredXlsx(rows);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "duplicate_report_colored.xlsx";
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      console.error(e);
      toast(e.response?.data?.detail || e.message || "Download failed", { variant: "error" });
    }
  }

  const canRun = fileData && selectedCols.length > 0 && identifierCol;

  return (
    <div className="agent-layout">
    <div className="agent-sidebar">
      <FlowDiagram title={GROUP_DUPLICATES_FLOW.title} phases={GROUP_DUPLICATES_FLOW.phases} />
    </div>
    <div className="card">
      <h2>
        Twin
        <span style={{
          fontSize: 12,
          fontWeight: 500,
          color: 'var(--muted)',
          letterSpacing: '0.02em',
          marginLeft: 10,
        }}>
          Group Duplicates
        </span>
      </h2>
      <p className="muted">
        Upload an Excel file, select columns to compare, and find duplicate/similar rows within the file.
      </p>

      <div className="divider" />
      <div className="section-label">Step 1 — Upload File</div>
      <FileUpload onUpload={onUpload} />

      {fileData && (
        <>
          <PreviewTable
            columns={fileData.columns}
            rows={fileData.preview}
            rowCount={fileData.row_count}
            title="File Preview"
          />

          <div className="divider" />
          <div className="section-label">Step 2 — Configure Columns</div>

          <SingleColumnPicker
            columns={fileData.columns}
            value={identifierCol}
            onChange={setIdentifierCol}
            label="Identifier Column (unique ID per row)"
            placeholder="Select identifier..."
          />

          <MultiColumnPicker
            columns={fileData.columns}
            selected={selectedCols}
            onChange={setSelectedCols}
            label="Comparison Columns (first = primary, 60% weight)"
          />

          <div className="divider" />
          <div className="section-label">Step 3 — Settings & Run</div>

          <div className="form-row">
            <div className="form-group" style={{ maxWidth: 340 }}>
              <label>Similarity Threshold: {Math.round(threshold * 100)}%</label>
              <input
                type="range" min="0.50" max="1.0" step="0.01"
                value={threshold}
                onChange={(e) => setThreshold(parseFloat(e.target.value))}
              />
            </div>
            <div className="form-group" style={{ maxWidth: 400, justifyContent: "flex-end" }}>
              <label style={{ textTransform: "none", letterSpacing: 0 }}>AI Variant Filter</label>
              <label className="toggle-switch">
                <input type="checkbox" checked={aiFilter} onChange={(e) => setAiFilter(e.target.checked)} />
                <span className="toggle-slider" />
                <span className="toggle-label">{aiFilter ? "Enabled" : "Disabled"}</span>
              </label>
              <span className="input-hint">Removes same product, different size/qty duplicates via AI</span>
            </div>
          </div>

          <div className="btn-row">
            <button className="btn btn-primary" disabled={!canRun || loading} onClick={analyze}>
              {loading && <span className="spinner" />}
              {loading ? "Analyzing..." : "Find Duplicates"}
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
              <div className="metric-value">{rows.length.toLocaleString()}</div>
              <div className="metric-label">Matched Rows</div>
            </div>
            <div className="metric">
              <div className="metric-value">{fileData?.row_count?.toLocaleString()}</div>
              <div className="metric-label">Total Rows</div>
            </div>
            <div className="metric">
              <div className="metric-value">{Math.round(threshold * 100)}%</div>
              <div className="metric-label">Threshold</div>
            </div>
          </div>

          {rows.length === 0 ? (
            <div className="alert alert-warn">
              No duplicates found at {Math.round(threshold * 100)}% threshold. Try lowering the threshold or selecting fewer columns.
            </div>
          ) : (
            <>
              <p className="muted" style={{ marginBottom: 8 }}>
                Rows are color-coded by duplicate group. Download colored Excel for fully styled output.
              </p>
              <div className="btn-row">
                <button className="btn btn-primary" onClick={downloadColoredXlsx}>Download Report</button>
              </div>
              <div className="table-container">
                <div className="table-header">Duplicate Groups Report — {rows.length} rows</div>
                <table>
                  <thead>
                    <tr>{displayCols.map((c) => <th key={c}>{c}</th>)}</tr>
                  </thead>
                  <tbody>
                    {rows.map((r, i) => (
                      <tr key={i} style={{ background: rowBackground(r) }}>
                        {displayCols.map((c) => (
                          <td
                            key={c}
                            style={
                              c === "Verdict"
                                ? {
                                    fontWeight: 700,
                                    color:
                                      r[c] === "EXACT MATCH" ? "var(--success)"
                                      : r[c] === "VERY LIKELY DUPLICATE" ? "var(--warn)"
                                      : "var(--accent)",
                                  }
                                : undefined
                            }
                          >
                            {r[c] ?? ""}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </>
      )}
    </div>
    </div>
  );
}
