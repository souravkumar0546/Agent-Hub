import React, { useState } from "react";

/** Coloured risk badge — High = red, Medium = amber, Low = green. */
function RiskBadge({ risk }) {
  const r = (risk || "").toLowerCase();
  let cls = "cacm-risk cacm-risk--low";
  if (r === "high") cls = "cacm-risk cacm-risk--high";
  else if (r === "medium") cls = "cacm-risk cacm-risk--medium";
  return <span className={cls}>{risk || "—"}</span>;
}

/** Render the most informative payload field as the "Reason" / "Value"
 *  surfaces. The CACM rules emit different shapes depending on the KPI
 *  (vendor mismatch, threshold breach, missing field, etc.) so we look
 *  at a known set of keys and fall back to JSON if nothing matches. */
function pickReason(payload) {
  if (!payload) return "";
  return (
    payload.reason ||
    payload.exception_reason ||
    payload.description ||
    payload.summary ||
    ""
  );
}

function pickValue(payload) {
  if (!payload) return "";
  const candidates = ["value", "amount", "delta", "diff", "actual", "observed"];
  for (const k of candidates) {
    if (payload[k] !== undefined && payload[k] !== null) {
      const v = payload[k];
      if (typeof v === "number") return v.toLocaleString();
      return String(v);
    }
  }
  return "";
}

function formatNumber(v) {
  if (v === null || v === undefined || v === "") return "—";
  if (typeof v === "number") return v.toLocaleString();
  const n = Number(v);
  if (!Number.isNaN(n)) return n.toLocaleString();
  return String(v);
}

function formatString(v) {
  if (v === null || v === undefined || v === "") return "—";
  return String(v);
}

function PayloadDetails({ payload }) {
  if (!payload || typeof payload !== "object") return null;
  const entries = Object.entries(payload);
  if (entries.length === 0) return null;
  return (
    <div className="cacm-exc-details">
      <table className="cacm-exc-payload">
        <tbody>
          {entries.map(([k, v]) => (
            <tr key={k}>
              <th>{k}</th>
              <td>
                {v === null || v === undefined
                  ? "—"
                  : typeof v === "object"
                  ? JSON.stringify(v)
                  : String(v)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/* ────────────────────────── Procurement columns ───────────────────── */

const PROCUREMENT_COLUMNS = [
  { key: "exception_no", label: "Exception #" },
  { key: "risk", label: "Risk", isRisk: true },
  { key: "company_code", label: "Company Code", source: "fields" },
  { key: "location", label: "Location", source: "fields" },
  { key: "po_no", label: "PO Number", source: "fields" },
  { key: "po_line_item", label: "PO Line Item", source: "fields" },
  { key: "po_created", label: "PO Date", source: "fields" },
  { key: "invoice_posted", label: "Invoice Date", source: "fields" },
  { key: "po_created_by", label: "PO Created By", source: "fields" },
  { key: "invoice_created_by", label: "Invoice Created By", source: "fields" },
  { key: "po_amount", label: "PO Amount", source: "fields", numeric: true },
  { key: "invoice_amount", label: "Invoice Amount", source: "fields", numeric: true },
  { key: "po_approval_status", label: "PO Approval", source: "fields" },
  { key: "diff_days", label: "Diff (days)", source: "fields", numeric: true },
  { key: "aging_bucket", label: "Aging Bucket", source: "fields" },
];

function ProcurementRow({ row, isOpen, onToggle }) {
  const payload = row.payload_json || {};
  const fields = payload.fields || {};
  return (
    <>
      <tr>
        {PROCUREMENT_COLUMNS.map((col) => {
          if (col.key === "exception_no") {
            return <td key={col.key}>{row.exception_no}</td>;
          }
          if (col.isRisk) {
            return (
              <td key={col.key}>
                <RiskBadge risk={row.risk} />
              </td>
            );
          }
          const v = fields[col.key];
          return (
            <td key={col.key}>
              {col.numeric ? formatNumber(v) : formatString(v)}
            </td>
          );
        })}
        <td>
          <button
            type="button"
            className="cacm-exc-toggle"
            onClick={onToggle}
          >
            {isOpen ? "Hide" : "Action"}
          </button>
        </td>
      </tr>
      {isOpen && (
        <tr className="cacm-exc-detail-row">
          <td colSpan={PROCUREMENT_COLUMNS.length + 1}>
            <div className="cacm-exc-action" style={{ marginBottom: 8 }}>
              <strong>Recommended action:</strong>{" "}
              {payload.recommended_action || payload.action || "—"}
            </div>
            <PayloadDetails payload={payload} />
          </td>
        </tr>
      )}
    </>
  );
}

/* ────────────────────────── Generic / Inventory ────────────────────── */

function GenericRow({ row, isOpen, onToggle }) {
  const payload = row.payload_json || {};
  const action = payload.recommended_action || payload.action || "";
  return (
    <>
      <tr>
        <td>{row.exception_no}</td>
        <td>
          <RiskBadge risk={row.risk} />
        </td>
        <td>{pickReason(payload)}</td>
        <td>{pickValue(payload)}</td>
        <td className="cacm-exc-action">{action}</td>
        <td>
          <button
            type="button"
            className="cacm-exc-toggle"
            onClick={onToggle}
          >
            {isOpen ? "Hide" : "Details"}
          </button>
        </td>
      </tr>
      {isOpen && (
        <tr className="cacm-exc-detail-row">
          <td colSpan={6}>
            <PayloadDetails payload={payload} />
          </td>
        </tr>
      )}
    </>
  );
}

/* ────────────────────────── Public component ──────────────────────── */

export default function ExceptionTable({ rows = [], process }) {
  const [expanded, setExpanded] = useState(() => new Set());

  function toggle(id) {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  if (rows.length === 0) {
    return (
      <div className="cacm-empty">No exceptions for the current filter.</div>
    );
  }

  // Detect process style. The Procurement KPI carries a much richer payload
  // (company_code / location / po_no etc.) so we render a wider table.
  const procurementPayload =
    rows[0]?.payload_json?.fields?.po_no !== undefined ||
    process === "Procurement";

  if (procurementPayload) {
    return (
      <div className="cacm-exc-wrapper">
        <table className="cacm-exc-table">
          <thead>
            <tr>
              {PROCUREMENT_COLUMNS.map((c) => (
                <th key={c.key}>{c.label}</th>
              ))}
              <th />
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <ProcurementRow
                key={row.id}
                row={row}
                isOpen={expanded.has(row.id)}
                onToggle={() => toggle(row.id)}
              />
            ))}
          </tbody>
        </table>
      </div>
    );
  }

  return (
    <div className="cacm-exc-wrapper">
      <table className="cacm-exc-table">
        <thead>
          <tr>
            <th>Exception #</th>
            <th>Risk</th>
            <th>Reason</th>
            <th>Value</th>
            <th>Recommended Action</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <GenericRow
              key={row.id}
              row={row}
              isOpen={expanded.has(row.id)}
              onToggle={() => toggle(row.id)}
            />
          ))}
        </tbody>
      </table>
    </div>
  );
}
