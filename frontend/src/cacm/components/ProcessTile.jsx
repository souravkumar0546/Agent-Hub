import React from "react";
import KpiRow from "./KpiRow.jsx";

/** A process card listing all KPIs that belong to that process. Clicks on
 *  a KPI bubble up to `onSelect(kpi)` so the parent page can kick off a run.
 */
export default function ProcessTile({ process, onSelect }) {
  const kpis = process.kpis || [];
  return (
    <div className="cacm-process-tile">
      <div className="cacm-process-header">
        <div className="cacm-process-name">{process.name}</div>
        <div className="cacm-process-count">
          {kpis.length} KPI{kpis.length === 1 ? "" : "s"}
        </div>
      </div>
      <div className="cacm-process-kpis">
        {kpis.length === 0 && (
          <div className="cacm-process-empty">No KPIs configured</div>
        )}
        {kpis.map((kpi) => (
          <KpiRow key={kpi.type} kpi={kpi} onClick={onSelect} />
        ))}
      </div>
    </div>
  );
}
