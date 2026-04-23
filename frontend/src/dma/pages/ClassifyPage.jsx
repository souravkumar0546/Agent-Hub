import React, { useState, useEffect, useCallback } from "react";
import FileUpload from "../components/FileUpload";
import { SingleColumnPicker } from "../components/ColumnPicker";
import StepProgress from "../components/StepProgress";
import {
  classifySingle,
  classifyBatch,
  classifyAddToMaster,
  classifyDownloadResults,
  getMasterData,
  getTaxonomy,
  getTaxonomyOptions,
} from "../api";
import FlowDiagram, { CLASSIFY_AGENT_FLOW } from "../components/FlowDiagram";
import ClassificationSettings from "../components/ClassificationSettings";
import { useToast } from "../../components/Dialog.jsx";

const CLASSIFY_STEPS = [
  { label: "Loading master data", sub: "Reading persisted master from disk" },
  { label: "Building semantic index", sub: "TF-IDF vectorization of descriptions" },
  { label: "Searching for matches", sub: "Blocking keys + cosine similarity" },
  { label: "AI classification", sub: "Confirming match or classifying from scratch" },
];

export default function ClassifyPage() {
  const toast = useToast();
  const [taxonomyOptions, setTaxonomyOptions] = useState([]);
  const [taxonomyKey, setTaxonomyKey] = useState("ZSC1");
  const [masterStatus, setMasterStatus] = useState(null); // {available, row_count, desc_col, class_col} or null

  const [mode, setMode] = useState("single"); // "single" | "batch"

  // Single mode
  const [descInput, setDescInput] = useState("");
  const [poInput, setPoInput] = useState("");
  const [singleLoading, setSingleLoading] = useState(false);
  const [singleError, setSingleError] = useState("");
  const [singleResult, setSingleResult] = useState(null);
  const [history, setHistory] = useState([]);

  // Batch mode
  const [batchFile, setBatchFile] = useState(null);
  const [batchDescCol, setBatchDescCol] = useState("");
  const [batchPoCol, setBatchPoCol] = useState("");
  const [batchLoading, setBatchLoading] = useState(false);
  const [batchError, setBatchError] = useState("");
  const [batchResults, setBatchResults] = useState(null);
  const [batchStep, setBatchStep] = useState(-1);

  const [simThreshold, setSimThreshold] = useState(0.65);
  const [settingsOpen, setSettingsOpen] = useState(false);

  // Sorted list of valid category names, used by the inline override
  // dropdown on each result row. Re-fetched whenever `taxonomyKey` flips
  // so switching taxonomies gives the right option set. Empty on error;
  // dropdown falls back to a read-only span in that case.
  const [categoryOptions, setCategoryOptions] = useState([]);

  useEffect(() => {
    getTaxonomyOptions().then(setTaxonomyOptions).catch(() => {});
  }, []);

  useEffect(() => {
    let cancelled = false;
    getTaxonomy()
      .then((t) => {
        if (cancelled) return;
        const cats = Object.keys(t?.categories || {}).sort();
        setCategoryOptions(cats);
      })
      .catch(() => { if (!cancelled) setCategoryOptions([]); });
    return () => { cancelled = true; };
  }, [taxonomyKey]);

  useEffect(() => {
    checkMaster(taxonomyKey);
  }, [taxonomyKey]);

  async function checkMaster(key) {
    setMasterStatus(null);
    try {
      const data = await getMasterData(key);
      setMasterStatus({
        available: true,
        row_count: data.total_rows,
        desc_col: data.meta?.desc_col || "",
        class_col: data.meta?.class_col || "",
      });
    } catch {
      setMasterStatus({ available: false, row_count: 0, desc_col: "", class_col: "" });
    }
  }

  // ── Single Classification ──
  async function handleClassifySingle() {
    if (!descInput.trim()) { setSingleError("Enter a material description."); return; }
    setSingleLoading(true); setSingleError(""); setSingleResult(null);
    try {
      const inputValues = {};
      if (masterStatus?.desc_col) inputValues[masterStatus.desc_col] = descInput;
      else inputValues["description"] = descInput;
      if (poInput.trim()) {
        inputValues["PO Text"] = poInput;
      }
      const data = await classifySingle({ taxonomyKey, inputValues, simThreshold });
      if (data.error) { setSingleError(data.error); }
      else {
        setSingleResult(data);
        setHistory((prev) => [
          { desc: descInput, po: poInput, result: data, time: new Date().toLocaleTimeString() },
          ...prev,
        ]);
      }
    } catch (err) {
      setSingleError(err.response?.data?.detail || err.message || "Classification failed");
    } finally {
      setSingleLoading(false);
    }
  }

  async function handleAddSingleToMaster() {
    if (!singleResult) return;
    const row = {
      "Material Description": descInput,
      "PO Text": poInput || "",
      "Classification": singleResult.assigned_category,
    };
    try {
      await classifyAddToMaster(taxonomyKey, [row]);
      checkMaster(taxonomyKey);
      setSingleResult(null); setDescInput(""); setPoInput("");
    } catch (e) { toast(e.message || "Failed to add to master", { variant: "error" }); }
  }

  // ── Classification overrides (user disagrees with AI) ──
  //
  // Both flows let the user change the category via a dropdown on each
  // result row. We snapshot the AI's original pick into `ai_category` on
  // first override so later renders can tell AI vs human, mark the row's
  // `method` as "user_override", and refresh the `reasoning` so the
  // downloaded report carries the correction reason instead of the stale
  // AI explanation.
  //
  // `assigned_category` stays the current (possibly-overridden) value,
  // which means every downstream consumer (`handleAddAllToMaster`,
  // `handleDownloadBatch`, `handleAddSingleToMaster`) transparently
  // picks up the correction without extra plumbing.
  function overrideRow(row, newCategory) {
    if (newCategory === row.assigned_category) return row;
    const aiCategory = row.ai_category ?? row.assigned_category;
    return {
      ...row,
      ai_category: aiCategory,
      assigned_category: newCategory,
      method: "user_override",
      reasoning: `User override (was "${aiCategory}"${row.reasoning ? "; AI reasoning: " + row.reasoning : ""})`,
    };
  }

  function setBatchRowCategory(index, newCategory) {
    setBatchResults((prev) => {
      if (!prev?.results) return prev;
      const nextRows = prev.results.slice();
      nextRows[index] = overrideRow(nextRows[index], newCategory);
      return { ...prev, results: nextRows };
    });
  }

  function setSingleCategory(newCategory) {
    setSingleResult((prev) => (prev ? overrideRow(prev, newCategory) : prev));
  }

  // ── Batch Classification ──
  const onBatchUpload = useCallback((data) => {
    setBatchFile(data);
    setBatchDescCol(""); setBatchPoCol("");
    setBatchResults(null); setBatchError("");
  }, []);

  async function handleClassifyBatch() {
    if (!batchFile || !batchDescCol) return;
    setBatchLoading(true); setBatchError(""); setBatchResults(null); setBatchStep(0);
    const interval = setInterval(() => {
      setBatchStep((s) => Math.min(s + 1, CLASSIFY_STEPS.length - 1));
    }, 3000);
    try {
      const data = await classifyBatch(batchFile.file, {
        taxonomyKey, descCol: batchDescCol, poCol: batchPoCol, simThreshold,
      });
      clearInterval(interval);
      setBatchStep(CLASSIFY_STEPS.length);
      setBatchResults(data);
    } catch (err) {
      clearInterval(interval);
      setBatchError(err.response?.data?.detail || err.message || "Batch classification failed");
    } finally {
      setBatchLoading(false);
    }
  }

  async function handleAddAllToMaster() {
    if (!batchResults?.results) return;
    const rows = batchResults.results
      .filter((r) => r.assigned_category && r.assigned_category !== "UNKNOWN")
      .map((r) => ({
        "Material Description": r.input_description || "",
        "PO Text": r.input_po || "",
        "Classification": r.assigned_category,
      }));
    try {
      await classifyAddToMaster(taxonomyKey, rows);
      checkMaster(taxonomyKey);
      toast(`Added ${rows.length} rows to master.`, { variant: "success" });
    } catch (e) { toast(e.message || "Failed", { variant: "error" }); }
  }

  async function handleDownloadBatch() {
    if (!batchResults?.results) return;
    // Build rows: original data + Classification + Method + Reasoning
    const downloadRows = batchResults.results.map((r) => {
      const row = { ...(r.original_row || {}) };
      row["Classification"] = r.assigned_category || "";
      row["Method"] = (
        r.method === "user_override" ? "User Override"
          : r.method === "group_match_confirmed" ? "Master Match"
            : "AI Classification"
      );
      row["Reasoning"] = r.reasoning || "";
      return row;
    });
    try {
      const blob = await classifyDownloadResults(downloadRows);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a"); a.href = url;
      a.download = "classification_results.xlsx"; a.click();
      URL.revokeObjectURL(url);
    } catch (e) { toast(e.message || "Download failed", { variant: "error" }); }
  }

  const batchCols = batchFile?.columns || [];

  return (
    <div className="agent-layout">
      <div className="agent-sidebar">
        <FlowDiagram title={CLASSIFY_AGENT_FLOW.title} phases={CLASSIFY_AGENT_FLOW.phases} />
      </div>
      <div className="card">
        <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between" }}>
          <div>
            <h2>
              Curator
              <span style={{
                fontSize: 12,
                fontWeight: 500,
                color: 'var(--muted)',
                letterSpacing: '0.02em',
                marginLeft: 10,
              }}>
                Data Classifier
              </span>
            </h2>
            <p className="muted">
              Classify new materials (single or batch) against the persisted master data. AI-powered lookup and categorization.
            </p>
          </div>
          <button className="settings-gear" title="Classification Settings" onClick={() => setSettingsOpen(true)}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="3"/>
              <path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 010 2.83 2 2 0 01-2.83 0l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-4 0v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83 0 2 2 0 010-2.83l.06-.06a1.65 1.65 0 00.33-1.82 1.65 1.65 0 00-1.51-1H3a2 2 0 010-4h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 010-2.83 2 2 0 012.83 0l.06.06a1.65 1.65 0 001.82.33H9a1.65 1.65 0 001-1.51V3a2 2 0 014 0v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 0 2 2 0 010 2.83l-.06.06a1.65 1.65 0 00-.33 1.82V9a1.65 1.65 0 001.51 1H21a2 2 0 010 4h-.09a1.65 1.65 0 00-1.51 1z"/>
            </svg>
          </button>
        </div>

        <ClassificationSettings
          open={settingsOpen}
          onClose={() => setSettingsOpen(false)}
          simThreshold={simThreshold}
          setSimThreshold={setSimThreshold}
          taxonomyKey={taxonomyKey}
        />

        {/* ── Taxonomy Selection ── */}
        <div className="divider" />
        <div className="section-label">Step 1 — Select Material Type</div>
        <div className="form-group" style={{ maxWidth: 400, marginBottom: 10 }}>
          <label>Material Type</label>
          <select value={taxonomyKey} onChange={(e) => setTaxonomyKey(e.target.value)}>
            {taxonomyOptions.map((t) => <option key={t.key} value={t.key}>{t.label}</option>)}
            {taxonomyOptions.length === 0 && <option value="ZSC1">Consumables - ZSC1</option>}
          </select>
        </div>

        {masterStatus === null && <p className="muted">Checking master data...</p>}
        {masterStatus && masterStatus.available && (
          <div className="alert alert-success" style={{ padding: "8px 14px" }}>
            Master available: <strong>{masterStatus.row_count} rows</strong> (columns: {masterStatus.desc_col}, {masterStatus.class_col})
          </div>
        )}
        {masterStatus && !masterStatus.available && (
          <div className="alert alert-info" style={{ padding: "8px 14px" }}>
            No master data for <strong>{taxonomyKey}</strong>. Classifications will use AI from taxonomy definitions. To add results to master, build one first using <strong>Forge</strong> (Master Builder).
          </div>
        )}

        {masterStatus && (
          <>
            {/* ── Mode Toggle ── */}
            <div className="divider" />
            <div className="section-label">Step 2 — Classify</div>
            <div className="btn-row" style={{ marginBottom: 14 }}>
              <button className={`btn ${mode === "single" ? "btn-primary" : "btn-outline"}`} onClick={() => setMode("single")}>
                Single Material
              </button>
              <button className={`btn ${mode === "batch" ? "btn-primary" : "btn-outline"}`} onClick={() => setMode("batch")}>
                Batch Upload
              </button>
            </div>

            {/* ── Single Mode ── */}
            {mode === "single" && (
              <>
                <div style={{ display: "flex", flexDirection: "column", gap: 10, marginBottom: 12 }}>
                  <div className="form-group" style={{ maxWidth: 560 }}>
                    <label>Material Description</label>
                    <input type="text" placeholder="Enter material description..." value={descInput} onChange={(e) => setDescInput(e.target.value)} />
                  </div>
                  <div className="form-group" style={{ maxWidth: 560 }}>
                    <label>PO Text (optional)</label>
                    <input type="text" placeholder="Enter PO text..." value={poInput} onChange={(e) => setPoInput(e.target.value)} />
                  </div>
                </div>
                <div className="btn-row">
                  <button className="btn btn-primary" disabled={singleLoading || !descInput.trim()} onClick={handleClassifySingle}>
                    {singleLoading && <span className="spinner" />}
                    {singleLoading ? "Classifying..." : "Classify Material"}
                  </button>
                </div>
                {singleError && <div className="alert alert-error">{singleError}</div>}
                {singleResult && (() => {
                  // Single-result override: same union-then-sort trick as the
                  // batch table so the dropdown always has a valid selected
                  // option even if the AI returned a legacy / non-taxonomy name.
                  const currentVal = singleResult.assigned_category || "";
                  const optionSet = new Set(categoryOptions);
                  if (currentVal) optionSet.add(currentVal);
                  const options = Array.from(optionSet).sort();
                  const isOverride = singleResult.method === "user_override";
                  const methodLabel = (
                    isOverride ? "User Override"
                      : singleResult.method === "group_match_confirmed" ? "Group Match (AI Confirmed)"
                        : "AI New Classification"
                  );
                  return (
                  <div style={{ marginTop: 12 }}>
                    <div className="verdict verdict-match" style={{ display: "flex", alignItems: "center", gap: 10 }}>
                      <span>Category:</span>
                      {options.length > 0 ? (
                        <select
                          value={currentVal}
                          onChange={(e) => setSingleCategory(e.target.value)}
                          aria-label="Category"
                          title={isOverride && singleResult.ai_category ? `AI said: ${singleResult.ai_category}` : "Override if you disagree"}
                          style={{ fontWeight: 700, color: isOverride ? "var(--warn)" : "var(--primary)", minWidth: 200 }}
                        >
                          {options.map((opt) => (
                            <option key={opt} value={opt}>{opt}</option>
                          ))}
                        </select>
                      ) : (
                        <strong>{currentVal}</strong>
                      )}
                    </div>
                    <div className="metrics">
                      <div className="metric">
                        <div className="metric-value" style={{ fontSize: 14, color: "var(--text)" }}>
                          {methodLabel}
                        </div>
                        <div className="metric-label">Method</div>
                      </div>
                    </div>
                    {singleResult.reasoning && <div className="alert alert-info">{singleResult.reasoning}</div>}
                    {singleResult.matched_rows?.length > 0 && (
                      <div className="table-container" style={{ marginTop: 8 }}>
                        <div className="table-header">Similar Materials in Master</div>
                        <table>
                          <thead><tr><th>Description</th><th>Category</th><th>Similarity</th></tr></thead>
                          <tbody>
                            {singleResult.matched_rows.map((r, i) => (
                              <tr key={i}>
                                <td>{r.description}</td><td>{r.category}</td>
                                <td style={{ fontWeight: 700 }}>{(r.score * 100).toFixed(1)}%</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                    <div className="btn-row">
                      <button className="btn btn-outline" onClick={handleAddSingleToMaster} disabled={!masterStatus?.available}>
                        Add to Master & Continue
                      </button>
                      {!masterStatus?.available && (
                        <span className="input-hint">No master exists. Build one with Forge first to enable adding.</span>
                      )}
                    </div>
                  </div>
                  );
                })()}

                {history.length > 0 && (
                  <>
                    <div className="divider" />
                    <div className="section-label">Classification History ({history.length})</div>
                    <div className="table-container">
                      <table>
                        <thead><tr><th>Time</th><th>Description</th><th>Category</th><th>Method</th></tr></thead>
                        <tbody>
                          {history.map((h, i) => (
                            <tr key={i}>
                              <td>{h.time}</td><td>{h.desc}</td>
                              <td style={{ fontWeight: 700, color: "var(--primary)" }}>{h.result.assigned_category}</td>
                              <td>{h.result.method === "group_match_confirmed" ? "Group Match" : "AI New"}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </>
                )}
              </>
            )}

            {/* ── Batch Mode ── */}
            {mode === "batch" && (
              <>
                <FileUpload onUpload={onBatchUpload} label="Upload Materials to Classify" />
                {batchFile && (
                  <>
                    <div className="form-row" style={{ marginTop: 12 }}>
                      <SingleColumnPicker columns={batchCols} value={batchDescCol} onChange={setBatchDescCol}
                        label="Description Column" placeholder="Select description..." />
                      <SingleColumnPicker columns={batchCols} value={batchPoCol} onChange={setBatchPoCol}
                        label="PO Column (optional)" placeholder="None" />
                    </div>
                    <div className="btn-row">
                      <button className="btn btn-primary" disabled={!batchDescCol || batchLoading} onClick={handleClassifyBatch}>
                        {batchLoading && <span className="spinner" />}
                        {batchLoading ? "Classifying..." : `Classify All (${batchFile.row_count} rows)`}
                      </button>
                    </div>
                  </>
                )}
                {batchLoading && <StepProgress steps={CLASSIFY_STEPS} currentStep={batchStep} />}
                {batchError && <div className="alert alert-error">{batchError}</div>}
                {batchResults && !batchLoading && (
                  <>
                    <div className="alert alert-success">
                      Classified {batchResults.total} materials.
                    </div>
                    <div className="table-container" style={{ maxHeight: 420 }}>
                      <div className="table-header">Results ({batchResults.total} rows)</div>
                      <table>
                        <thead>
                          <tr><th>#</th><th>Description</th><th>Category</th><th>Method</th><th>Reasoning</th></tr>
                        </thead>
                        <tbody>
                          {batchResults.results.map((r, i) => {
                            // Override dropdown: include both the taxonomy's current
                            // category list AND the row's present assigned_category
                            // (which may be "UNKNOWN" or a legacy value the AI
                            // produced but the current taxonomy no longer lists).
                            // Union-then-sort so the dropdown always has a valid
                            // selected option and doesn't collapse to the first
                            // alphabetical choice on render.
                            const currentVal = r.assigned_category || "";
                            const optionSet = new Set(categoryOptions);
                            if (currentVal) optionSet.add(currentVal);
                            const options = Array.from(optionSet).sort();
                            const isOverride = r.method === "user_override";
                            return (
                              <tr key={i}>
                                <td>{i + 1}</td>
                                <td>{r.input_description}</td>
                                <td>
                                  {options.length > 0 ? (
                                    <select
                                      value={currentVal}
                                      onChange={(e) => setBatchRowCategory(i, e.target.value)}
                                      aria-label={`Category for row ${i + 1}`}
                                      title={isOverride && r.ai_category ? `AI said: ${r.ai_category}` : undefined}
                                      style={{
                                        fontWeight: 700,
                                        color: isOverride ? "var(--warn)" : "var(--primary)",
                                        minWidth: 160,
                                      }}
                                    >
                                      {options.map((opt) => (
                                        <option key={opt} value={opt}>{opt}</option>
                                      ))}
                                    </select>
                                  ) : (
                                    <span style={{ fontWeight: 700, color: "var(--primary)" }}>{currentVal}</span>
                                  )}
                                </td>
                                <td>{
                                  isOverride ? "User Override"
                                    : r.method === "group_match_confirmed" ? "Match"
                                      : "AI New"
                                }</td>
                                <td style={{ fontSize: 12 }}>{r.reasoning?.slice(0, 120)}</td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                    <div className="btn-row">
                      <button className="btn btn-primary" onClick={handleAddAllToMaster} disabled={!masterStatus?.available}>
                        Add All to Master
                      </button>
                      <button className="btn btn-outline" onClick={handleDownloadBatch}>Download Results</button>
                      {!masterStatus?.available && (
                        <span className="input-hint">No master exists. Build one with Forge first to enable adding.</span>
                      )}
                    </div>
                  </>
                )}
              </>
            )}
          </>
        )}
      </div>
    </div>
  );
}
