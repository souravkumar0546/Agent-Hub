import axios from "axios";
import { getOrgId, getToken } from "../lib/api.js";

// DMAhub routes are mounted at /api/dma/* on the hub backend, behind the
// standard bearer-token + X-Org-Id auth. The interceptor below reuses the
// same localStorage keys the rest of the app already writes.
//
// In production we prefix with VITE_API_BASE (the backend origin) so fetches
// bypass the static-site rewrite and go direct to the API. In dev it's empty
// and Vite's /api proxy handles it.
const API_BASE = import.meta.env.VITE_API_BASE || "";
const API = axios.create({ baseURL: `${API_BASE}/api/dma` });

API.interceptors.request.use((config) => {
  const token = getToken();
  const orgId = getOrgId();
  if (token) config.headers.Authorization = `Bearer ${token}`;
  if (orgId) config.headers["X-Org-Id"] = String(orgId);
  return config;
});

export async function uploadPreview(file) {
  const fd = new FormData();
  fd.append("file", file);
  const { data } = await API.post("/upload-preview", fd);
  return data;
}

export async function groupDuplicatesAnalyze(file, params) {
  const fd = new FormData();
  fd.append("file", file);
  fd.append("threshold", String(params.threshold));
  fd.append("selected_cols", params.selectedCols.join(","));
  fd.append("identifier_col", params.identifierCol);
  fd.append("apply_ai_variant_filter", String(params.applyAiFilter));
  const { data } = await API.post("/group-duplicates/analyze", fd);
  return data;
}

export async function groupDuplicatesColoredXlsx(rows) {
  const fd = new FormData();
  fd.append("rows_json", JSON.stringify(rows));
  const res = await API.post("/group-duplicates/colored-xlsx", fd, {
    responseType: "blob",
  });
  return res.data;
}

export async function lookupAnalyze(file, params) {
  const fd = new FormData();
  fd.append("file", file);
  fd.append("threshold", String(params.threshold));
  fd.append("top_n", String(params.topN));
  fd.append("selected_cols", params.selectedCols.join(","));
  fd.append("input_values_json", JSON.stringify(params.inputValues));
  const { data } = await API.post("/lookup/analyze", fd);
  return data;
}

export async function classificationFixMaster(file, params) {
  const fd = new FormData();
  fd.append("file", file);
  fd.append("desc_col", params.descCol);
  fd.append("class_col", params.classCol);
  fd.append("po_col", params.poCol || "");
  fd.append("status_col", params.statusCol || "");
  fd.append("sim_threshold", String(params.simThreshold));
  fd.append("ai_batch_size", String(params.aiBatchSize));
  fd.append("taxonomy_key", params.taxonomyKey || "ZSC1");
  const { data } = await API.post("/classification/fix-master", fd);
  return data;
}

export async function classificationClassifyNew(params) {
  const fd = new FormData();
  fd.append("desc_col", params.descCol);
  fd.append("class_col", params.classCol);
  fd.append("sim_threshold", String(params.simThreshold));
  fd.append("input_values_json", JSON.stringify(params.inputValues));
  if (params.masterId) {
    fd.append("master_id", params.masterId);
  } else if (params.file) {
    fd.append("file", params.file);
  } else {
    throw new Error("file or masterId required");
  }
  const { data } = await API.post("/classification/classify-new", fd);
  return data;
}

export async function classificationMasterAddRow(masterId, row) {
  const fd = new FormData();
  fd.append("master_id", masterId);
  fd.append("row_json", JSON.stringify(row));
  const { data } = await API.post("/classification/master-add-row", fd);
  return data;
}

export async function classificationDownloadHighlighted(classCol, masterId) {
  const fd = new FormData();
  fd.append("class_col", classCol);
  fd.append("master_id", masterId || "");
  const res = await API.post("/classification/download-highlighted", fd, {
    responseType: "blob",
  });
  return res.data;
}

export async function getConfig() {
  const { data } = await API.get("/config");
  return data;
}

export async function getTaxonomyOptions() {
  const { data } = await API.get("/classification/taxonomy-options");
  return data;
}

export async function getTaxonomy() {
  const { data } = await API.get("/classification/taxonomy");
  return data;
}

export async function updateTaxonomy(taxonomy) {
  const { data } = await API.put("/classification/taxonomy", taxonomy);
  return data;
}

// ── Master Builder ──────────────────────────────────────────────────────

export async function masterBuilderFixMaster(file, params) {
  const fd = new FormData();
  fd.append("file", file);
  fd.append("desc_col", params.descCol);
  fd.append("class_col", params.classCol);
  fd.append("po_col", params.poCol || "");
  fd.append("status_col", params.statusCol || "");
  fd.append("sim_threshold", String(params.simThreshold));
  fd.append("ai_batch_size", String(params.aiBatchSize));
  fd.append("taxonomy_key", params.taxonomyKey || "ZSC1");
  const { data } = await API.post("/master-builder/fix-master", fd, { timeout: 600000 });
  return data;
}

export async function masterBuilderAddToMaster(reviewId, overrides) {
  // `overrides` is an optional `{ rowIndex: newCategory }` map; the reviewer
  // builds it by tweaking the dropdown on each row of the fixed grid. We
  // JSON-encode it onto the multipart payload so the backend's Form parser
  // picks it up as a single field. Null / empty → omitted.
  const fd = new FormData();
  fd.append("review_id", reviewId);
  if (overrides && Object.keys(overrides).length > 0) {
    fd.append("overrides", JSON.stringify(overrides));
  }
  const { data } = await API.post("/master-builder/add-to-master", fd);
  return data;
}

export async function getMasters() {
  const { data } = await API.get("/master-builder/masters");
  return data;
}

export async function getMasterData(taxonomyKey) {
  const { data } = await API.get(`/master-builder/masters/${taxonomyKey}`);
  return data;
}

export async function downloadMaster(taxonomyKey) {
  const res = await API.get(`/master-builder/masters/${taxonomyKey}/download`, {
    responseType: "blob",
  });
  return res.data;
}

// ── Classification Agent ────────────────────────────────────────────────

export async function classifySingle(params) {
  const fd = new FormData();
  fd.append("taxonomy_key", params.taxonomyKey);
  fd.append("input_values_json", JSON.stringify(params.inputValues));
  fd.append("sim_threshold", String(params.simThreshold || 0.65));
  const { data } = await API.post("/classify/single", fd, { timeout: 120000 });
  return data;
}

export async function classifyBatch(file, params) {
  const fd = new FormData();
  fd.append("taxonomy_key", params.taxonomyKey);
  fd.append("file", file);
  fd.append("desc_col", params.descCol);
  fd.append("po_col", params.poCol || "");
  fd.append("sim_threshold", String(params.simThreshold || 0.65));
  const { data } = await API.post("/classify/batch", fd, { timeout: 600000 });
  return data;
}

export async function classifyAddToMaster(taxonomyKey, rows) {
  const fd = new FormData();
  fd.append("taxonomy_key", taxonomyKey);
  fd.append("rows_json", JSON.stringify(rows));
  const { data } = await API.post("/classify/add-to-master", fd);
  return data;
}

export async function classifyDownloadResults(results) {
  const fd = new FormData();
  fd.append("results_json", JSON.stringify(results));
  const res = await API.post("/classify/download", fd, { responseType: "blob" });
  return res.data;
}

// ── Data Enrichment ─────────────────────────────────────────────────────

export async function enrichmentEnrich(file, params) {
  const fd = new FormData();
  fd.append("file", file);
  fd.append("cas_col", params.casCol);
  const { data } = await API.post("/enrichment/enrich", fd, { timeout: 600000 });
  return data;
}

export async function enrichmentDownload(file, params) {
  const fd = new FormData();
  fd.append("file", file);
  fd.append("cas_col", params.casCol);
  const res = await API.post("/enrichment/download", fd, {
    responseType: "blob",
    timeout: 600000,
  });
  return res.data;
}
