import React, { useState, useCallback, useRef, useEffect } from "react";
import FileUpload from "../components/FileUpload";
import PreviewTable from "../components/PreviewTable";
import StepProgress from "../components/StepProgress";
import { MultiColumnPicker } from "../components/ColumnPicker";
import { lookupAnalyze } from "../api";
import FlowDiagram, { LOOKUP_FLOW } from "../components/FlowDiagram";

const STEPS = [
  { label: "Building per-column TF-IDF corpora", sub: "Char n-gram vectorization on reference data" },
  { label: "Checking for exact matches", sub: "Case-insensitive comparison across all selected columns" },
  { label: "TF-IDF candidate search on primary column", sub: "Finding top candidates above loose threshold" },
  { label: "Keyword overlap matching", sub: "Token-level containment check on combined corpus" },
  { label: "Per-column scoring & weighted verdict", sub: "Primary 60% + secondary 40% weighting" },
];

export default function LookupPage() {
  const [fileData, setFileData] = useState(null);
  const [selectedCols, setSelectedCols] = useState([]);
  const [inputValues, setInputValues] = useState({});
  const [threshold, setThreshold] = useState(0.80);
  const [topN, setTopN] = useState(5);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);
  const [pipelineStep, setPipelineStep] = useState(-1);
  const intervalRef = useRef(null);

  const onUpload = useCallback((data) => {
    setFileData(data);
    setSelectedCols([]);
    setInputValues({});
    setResult(null);
    setError("");
  }, []);

  useEffect(() => {
    return () => { if (intervalRef.current) clearInterval(intervalRef.current); };
  }, []);

  function onColsChange(cols) {
    setSelectedCols(cols);
    setInputValues((prev) => {
      const next = {};
      cols.forEach((c) => { next[c] = prev[c] || ""; });
      return next;
    });
  }

  function setInput(col, val) {
    setInputValues((prev) => ({ ...prev, [col]: val }));
  }

  async function analyze() {
    if (!fileData || selectedCols.length === 0) return;
    const filled = Object.values(inputValues).some((v) => (v || "").trim());
    if (!filled) { setError("Fill in at least one search value."); return; }

    setLoading(true);
    setError("");
    setResult(null);
    setPipelineStep(0);

    let step = 0;
    intervalRef.current = setInterval(() => {
      step++;
      if (step < STEPS.length - 1) setPipelineStep(step);
    }, 1500);

    try {
      const data = await lookupAnalyze(fileData.file, { threshold, topN, selectedCols, inputValues });
      clearInterval(intervalRef.current);
      if (data.error) {
        setError(data.error);
      } else {
        setPipelineStep(STEPS.length);
        setResult(data);
      }
    } catch (err) {
      clearInterval(intervalRef.current);
      setError(err.response?.data?.detail || err.message || "Lookup failed");
    } finally {
      setLoading(false);
    }
  }

  const canRun = fileData && selectedCols.length > 0;
  const allRefCols = fileData?.columns || [];

  function verdictClass(v) {
    if (!v) return "verdict verdict-no";
    const lv = v.toLowerCase();
    if (lv.includes("exact") || lv.includes("very likely")) return "verdict verdict-match";
    if (lv.includes("possible") || lv.includes("matches")) return "verdict verdict-warn";
    return "verdict verdict-no";
  }

  return (
    <div className="agent-layout">
    <div className="agent-sidebar">
      <FlowDiagram title={LOOKUP_FLOW.title} phases={LOOKUP_FLOW.phases} />
    </div>
    <div className="card">
      <h2>
        Sonar
        <span style={{
          fontSize: 12,
          fontWeight: 500,
          color: 'var(--muted)',
          letterSpacing: '0.02em',
          marginLeft: 10,
        }}>
          Lookup Agent
        </span>
      </h2>
      <p className="muted">
        Upload a reference Excel file, enter search values, and find the closest matches in the database.
      </p>

      <div className="divider" />
      <div className="section-label">Step 1 — Upload Reference File</div>
      <FileUpload onUpload={onUpload} label="Upload Reference File" />

      {fileData && (
        <>
          <PreviewTable
            columns={fileData.columns}
            rows={fileData.preview}
            rowCount={fileData.row_count}
            title="Reference File Preview"
          />

          <div className="divider" />
          <div className="section-label">Step 2 — Select Columns</div>

          <MultiColumnPicker
            columns={fileData.columns}
            selected={selectedCols}
            onChange={onColsChange}
            label="Columns to Search (first = primary, 60% weight)"
          />

          {selectedCols.length > 0 && (
            <>
              <div className="divider" />
              <div className="section-label">Step 3 — Enter Search Values</div>
              <p className="muted" style={{ marginBottom: 10 }}>
                Enter the values you want to look up. First selected column is the primary match.
              </p>
              <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                {selectedCols.map((col) => (
                  <div className="form-group" key={col} style={{ maxWidth: 560 }}>
                    <label>{col}</label>
                    <input
                      type="text"
                      placeholder={`Enter ${col}...`}
                      value={inputValues[col] || ""}
                      onChange={(e) => setInput(col, e.target.value)}
                    />
                  </div>
                ))}
              </div>
            </>
          )}

          <div className="divider" />
          <div className="section-label">Settings</div>
          <div className="form-row">
            <div className="form-group" style={{ maxWidth: 340 }}>
              <label>Similarity Threshold: {Math.round(threshold * 100)}%</label>
              <input
                type="range" min="0.50" max="1.0" step="0.01"
                value={threshold}
                onChange={(e) => setThreshold(parseFloat(e.target.value))}
              />
            </div>
            <div className="form-group" style={{ maxWidth: 140 }}>
              <label>Top N Results</label>
              <input
                type="number" min="1" max="50" value={topN}
                onChange={(e) => setTopN(parseInt(e.target.value) || 5)}
              />
            </div>
          </div>

          <div className="btn-row">
            <button className="btn btn-primary" disabled={!canRun || loading} onClick={analyze}>
              {loading && <span className="spinner" />}
              {loading ? "Searching..." : "Search"}
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

          <div className={verdictClass(result.verdict)}>{result.verdict}</div>

          {result.exact_matches?.length > 0 && (
            <>
              <h3>Exact Matches ({result.exact_match_count})</h3>
              <div className="table-container">
                <table>
                  <thead>
                    <tr>{allRefCols.map((c) => <th key={c}>{c}</th>)}</tr>
                  </thead>
                  <tbody>
                    {result.exact_matches.map((r, i) => (
                      <tr key={i}>{allRefCols.map((c) => <td key={c}>{r[c] ?? ""}</td>)}</tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}

          {result.similar_matches?.length > 0 && (
            <>
              <h3>Similar Matches</h3>
              <div className="table-container">
                <table>
                  <thead>
                    <tr>
                      <th>Overall %</th>
                      {selectedCols.map((c) => <th key={c}>{c} %</th>)}
                      {allRefCols.map((c) => <th key={`ref-${c}`}>{c}</th>)}
                    </tr>
                  </thead>
                  <tbody>
                    {result.similar_matches.map((m, i) => (
                      <tr key={i}>
                        <td style={{ fontWeight: 700, color: "var(--primary)" }}>{m.overall}%</td>
                        {selectedCols.map((c) => (
                          <td key={c}>{m.per_column?.[c] != null ? `${m.per_column[c]}%` : "—"}</td>
                        ))}
                        {allRefCols.map((c) => (
                          <td key={`val-${c}`}>{m.record?.[c] ?? ""}</td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}

          {!result.exact_matches?.length && !result.similar_matches?.length && (
            <div className="alert alert-warn">
              No matches found. Try lowering the threshold or adjusting search values.
            </div>
          )}
        </>
      )}
    </div>
    </div>
  );
}
