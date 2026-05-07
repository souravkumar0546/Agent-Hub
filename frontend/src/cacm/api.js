import axios from "axios";
import { useEffect, useRef, useState } from "react";
import { getOrgId, getToken } from "../lib/api.js";

// CACM routes are mounted at /api/cacm/* on the hub backend, behind the
// standard bearer-token + X-Org-Id auth. Mirror the DMA api.js pattern so
// the interceptor reuses the same localStorage keys the rest of the app
// already writes.
//
// In production we prefix with VITE_API_BASE (the backend origin) so
// fetches bypass the static-site rewrite and go direct to the API.
const API_BASE = import.meta.env.VITE_API_BASE || "";
const API = axios.create({ baseURL: `${API_BASE}/api/cacm` });

API.interceptors.request.use((config) => {
  const token = getToken();
  const orgId = getOrgId();
  if (token) config.headers.Authorization = `Bearer ${token}`;
  if (orgId) config.headers["X-Org-Id"] = String(orgId);
  return config;
});

export async function getLibrary() {
  const { data } = await API.get("/library");
  return data;
}

export async function getProcesses() {
  const { data } = await API.get("/processes");
  return data;
}

export async function getProcess(processKey) {
  const { data } = await API.get(`/processes/${processKey}`);
  return data;
}

export async function startRun(kpiType) {
  const { data } = await API.post("/runs", { kpi_type: kpiType });
  return data;
}

export async function getRun(runId) {
  const { data } = await API.get(`/runs/${runId}`);
  return data;
}

export async function listRuns() {
  const { data } = await API.get("/runs");
  return data;
}

export async function getEvents(runId, since = 0) {
  const { data } = await API.get(`/runs/${runId}/events`, {
    params: { since },
  });
  return data;
}

export async function getExceptions(runId, { risk } = {}) {
  const params = {};
  if (risk && risk !== "All") params.risk = risk;
  const { data } = await API.get(`/runs/${runId}/exceptions`, { params });
  return data;
}

/** Fetch the dashboard payload for a run. `filters` is an object whose
 *  values are arrays of strings; each one maps to a comma-separated query
 *  param. Unknown / empty arrays are dropped so the URL stays clean.
 *  The keys cover both Procurement (companies/locations/risk/aging/creators)
 *  and Inventory (movement_types/material_groups/reversals) — extra keys
 *  on either side are simply ignored by the backend. */
export async function getDashboard(runId, filters = {}) {
  const params = {};
  for (const key of [
    "companies",
    "locations",
    "risk_levels",
    "aging_buckets",
    "po_creators",
    "movement_types",
    "material_groups",
    "reversals",
  ]) {
    const v = filters[key];
    if (Array.isArray(v) && v.length > 0) {
      params[key] = v.join(",");
    }
  }
  const { data } = await API.get(`/runs/${runId}/dashboard`, { params });
  return data;
}

/** Per-stage detail for the wizard. `stageName` is one of:
 *  "extraction" | "transformation" | "loading" | "rule-engine".
 */
export async function getStageData(runId, stageName) {
  const { data } = await API.get(`/runs/${runId}/stage/${stageName}`);
  return data;
}

/** Path (NOT a full URL) for downloading an extracted source table as CSV.
 *  Pair with `downloadCacmFile` so the request goes through the auth-aware
 *  axios instance.
 */
export function extractedTableDownloadUrl(runId, tableName) {
  return `/runs/${runId}/stage/extraction/download/${tableName}.csv`;
}

export function exceptionsCsvUrl(runId) {
  return `/cacm/runs/${runId}/exceptions.csv`;
}

export function exceptionsXlsxUrl(runId) {
  return `/cacm/runs/${runId}/exceptions.xlsx`;
}

/** Auth-aware download helper for CACM blobs. Mirrors lib/api.js::downloadFile
 *  but routes through the cacm axios instance so we get the same interceptor
 *  treatment. Returns once the click is fired. */
export async function downloadCacmFile(path, fallbackName = "download") {
  const res = await API.get(path, { responseType: "blob" });
  const cd = res.headers["content-disposition"] || "";
  const match = cd.match(/filename="?([^"]+)"?/);
  const filename = match ? match[1] : fallbackName;

  const url = URL.createObjectURL(res.data);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

/** Polling hook that streams CACM run events. Polls /runs/{id}/events
 *  on a `intervalMs` cadence and tracks the last seen `seq` so the
 *  backend can return only new entries. Stops automatically when the
 *  run reaches a terminal state. On error, doubles the interval to
 *  back off (capped at 10s). Cleans up on unmount.
 *
 *  Returns: `{ events: Event[], status: "running"|"succeeded"|"failed" }`
 */
export function useEvents(runId, intervalMs = 500) {
  const [events, setEvents] = useState([]);
  const [status, setStatus] = useState("running");
  const cursorRef = useRef(0);
  const cancelledRef = useRef(false);
  const currentDelayRef = useRef(intervalMs);

  useEffect(() => {
    if (!runId) return undefined;
    cancelledRef.current = false;
    cursorRef.current = 0;
    currentDelayRef.current = intervalMs;
    setEvents([]);
    setStatus("running");

    let timer = null;

    async function tick() {
      if (cancelledRef.current) return;
      try {
        const data = await getEvents(runId, cursorRef.current);
        if (cancelledRef.current) return;
        const nextEvents = data.events || [];
        if (nextEvents.length > 0) {
          setEvents((prev) => [...prev, ...nextEvents]);
          const lastSeq = nextEvents[nextEvents.length - 1].seq;
          cursorRef.current = Math.max(cursorRef.current, lastSeq);
        }
        const nextStatus = data.status || "running";
        setStatus(nextStatus);
        // Reset backoff on success.
        currentDelayRef.current = intervalMs;
        if (nextStatus !== "running") return;
      } catch (err) {
        // Backoff on transient errors. Cap at 10s so we don't permanently
        // wedge if the backend goes away.
        currentDelayRef.current = Math.min(currentDelayRef.current * 2, 10000);
      }
      if (!cancelledRef.current) {
        timer = setTimeout(tick, currentDelayRef.current);
      }
    }

    tick();

    return () => {
      cancelledRef.current = true;
      if (timer) clearTimeout(timer);
    };
  }, [runId, intervalMs]);

  return { events, status };
}
