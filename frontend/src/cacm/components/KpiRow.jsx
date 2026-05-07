import React from "react";

/** A single KPI inside a `<ProcessTile>` — clickable row with name,
 *  description and a small green "live" dot to indicate the KPI is
 *  available for execution. The full rule_objective is exposed via
 *  the native `title` tooltip. */
export default function KpiRow({ kpi, onClick }) {
  return (
    <button
      type="button"
      className="cacm-kpi-row"
      onClick={() => onClick && onClick(kpi)}
      title={kpi.rule_objective || kpi.description || ""}
    >
      <span className="cacm-kpi-dot" aria-hidden="true" />
      <span className="cacm-kpi-content">
        <span className="cacm-kpi-name">{kpi.name}</span>
        {kpi.description && (
          <span className="cacm-kpi-desc">{kpi.description}</span>
        )}
      </span>
      <span className="cacm-kpi-arrow" aria-hidden="true">→</span>
    </button>
  );
}
