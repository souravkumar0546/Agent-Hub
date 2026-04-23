import React, { useState, useEffect } from "react";
import { getTaxonomy, updateTaxonomy } from "../api";
import { useToast } from "../../components/Dialog.jsx";

export default function ClassificationSettings({
  open,
  onClose,
  simThreshold,
  setSimThreshold,
  aiBatchSize,
  setAiBatchSize,
  taxonomyKey,
}) {
  const toast = useToast();
  const [taxonomy, setTaxonomy] = useState(null);
  const [loadedKey, setLoadedKey] = useState(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  // Editable state
  const [categories, setCategories] = useState({});
  const [overrideRules, setOverrideRules] = useState("");

  // Reload taxonomy when modal opens or taxonomyKey changes
  useEffect(() => {
    if (open && taxonomyKey !== loadedKey) {
      setLoading(true);
      setError("");
      // First switch the backend to the selected taxonomy, then fetch it
      updateTaxonomy({ taxonomy_key: taxonomyKey })
        .then((data) => {
          setTaxonomy(data);
          setCategories(data.categories || {});
          setOverrideRules(data.override_rules || "");
          setLoadedKey(taxonomyKey);
        })
        .catch((e) => setError(e.message || "Failed to load taxonomy"))
        .finally(() => setLoading(false));
    }
  }, [open, taxonomyKey, loadedKey]);

  if (!open) return null;

  function updateCat(catName, field, value) {
    setCategories((prev) => ({
      ...prev,
      [catName]: { ...prev[catName], [field]: value },
    }));
  }

  function removeCat(catName) {
    setCategories((prev) => {
      const next = { ...prev };
      delete next[catName];
      return next;
    });
  }

  function addCategory() {
    const name = prompt("Enter new category name:");
    if (!name || !name.trim()) return;
    if (categories[name.trim()]) {
      toast("Category already exists.", { variant: "warning" });
      return;
    }
    setCategories((prev) => ({
      ...prev,
      [name.trim()]: { definition: "", examples: "" },
    }));
  }

  async function handleSave() {
    setSaving(true);
    setError("");
    setSuccess("");
    try {
      const updated = await updateTaxonomy({
        categories,
        override_rules: overrideRules,
      });
      setTaxonomy(updated);
      setSuccess("Taxonomy updated successfully.");
      setTimeout(() => setSuccess(""), 3000);
    } catch (e) {
      setError(e.response?.data?.detail || e.message || "Save failed");
    } finally {
      setSaving(false);
    }
  }

  const catEntries = Object.entries(categories);

  return (
    <div className="settings-overlay" onClick={onClose}>
      <div className="settings-modal" onClick={(e) => e.stopPropagation()}>
        <div className="settings-header">
          <h3>Classification Settings</h3>
          <button className="settings-close" onClick={onClose}>&times;</button>
        </div>

        <div className="settings-body">
          {/* ── Model Settings ── */}
          <div className="settings-section">
            <div className="settings-section-title">Model Settings</div>
            <div className="form-row">
              <div className="form-group" style={{ flex: 1 }}>
                <label>Similarity Threshold: {Math.round(simThreshold * 100)}%</label>
                <input
                  type="range" min="0.40" max="0.95" step="0.01"
                  value={simThreshold}
                  onChange={(e) => setSimThreshold(parseFloat(e.target.value))}
                />
              </div>
              {setAiBatchSize && (
                <div className="form-group" style={{ maxWidth: 160 }}>
                  <label>AI Batch Size</label>
                  <input
                    type="number" min="1" max="20" value={aiBatchSize}
                    onChange={(e) => setAiBatchSize(Math.max(1, Math.min(20, parseInt(e.target.value) || 1)))}
                  />
                  <span className="input-hint">Groups per API call (1-20)</span>
                </div>
              )}
            </div>
          </div>

          {loading && <div className="settings-loading">Loading taxonomy...</div>}

          {!loading && taxonomy && (
            <>
              {/* ── Category Definitions ── */}
              <div className="settings-section">
                <div className="settings-section-title">
                  Category Definitions ({catEntries.length})
                  <button className="btn btn-sm btn-outline" onClick={addCategory} style={{ marginLeft: 12 }}>
                    + Add Category
                  </button>
                </div>
                <div className="settings-categories">
                  {catEntries.map(([name, info]) => (
                    <div className="settings-cat-card" key={name}>
                      <div className="settings-cat-header">
                        <span className="settings-cat-name">{name}</span>
                        <button
                          className="settings-cat-remove"
                          title="Remove category"
                          onClick={() => removeCat(name)}
                        >
                          &times;
                        </button>
                      </div>
                      <div className="form-group" style={{ marginBottom: 8 }}>
                        <label>Definition</label>
                        <textarea
                          rows={2}
                          value={info.definition || ""}
                          onChange={(e) => updateCat(name, "definition", e.target.value)}
                        />
                      </div>
                      <div className="form-group">
                        <label>Examples</label>
                        <input
                          type="text"
                          value={info.examples || ""}
                          onChange={(e) => updateCat(name, "examples", e.target.value)}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* ── Override Rules ── */}
              <div className="settings-section">
                <div className="settings-section-title">Critical Override Rules</div>
                <p className="muted" style={{ marginBottom: 8, fontSize: 12 }}>
                  Edge-case rules applied FIRST by the AI, before matching definitions.
                </p>
                <textarea
                  className="settings-rules-textarea"
                  rows={8}
                  value={overrideRules}
                  onChange={(e) => setOverrideRules(e.target.value)}
                />
              </div>
            </>
          )}

          {error && <div className="alert alert-error">{error}</div>}
          {success && <div className="alert alert-success">{success}</div>}
        </div>

        <div className="settings-footer">
          <button className="btn btn-secondary" onClick={onClose}>Cancel</button>
          <button className="btn btn-primary" onClick={handleSave} disabled={saving || loading}>
            {saving && <span className="spinner" />}
            {saving ? "Saving..." : "Save Changes"}
          </button>
        </div>
      </div>
    </div>
  );
}
