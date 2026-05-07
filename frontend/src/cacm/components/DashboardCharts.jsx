import React, { useMemo } from "react";
import {
  Area,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ComposedChart,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
} from "recharts";

/** Procurement-rich dashboard for the `po_after_invoice` KPI.
 *  Falls back to a simpler 4-chart grid for other KPIs (Inventory, etc.). */

const RISK_COLORS = {
  High: "#e74c3c",
  Medium: "#f59e0b",
  Low: "#22c55e",
};

const SERIES_FILL = "#5b8cff";
const VENDOR_FILL = "#a06cd5";

const LOCATION_COLOR_MAP = {
  purple: "#8b5cf6",
  red: "#e74c3c",
  blue: "#3b82f6",
  orange: "#f59e0b",
  green: "#22c55e",
};

// Bar tints for the PO-creators horizontal-bar list — alternated round-robin.
const CREATOR_PALETTE = ["#5b8cff", "#a06cd5", "#22c55e", "#f59e0b", "#3b82f6", "#8b5cf6", "#e879f9", "#06b6d4"];

function asArray(maybe) {
  if (!maybe) return [];
  if (Array.isArray(maybe)) return maybe;
  return Object.entries(maybe).map(([name, value]) => ({ name, value }));
}

function formatINR(amt) {
  if (amt == null) return "—";
  const n = Number(amt);
  if (!isFinite(n)) return "—";
  if (n >= 1_00_00_000) return `₹${(n / 1_00_00_000).toFixed(2)} Cr`;
  if (n >= 1_00_000) return `₹${(n / 1_00_000).toFixed(2)} L`;
  if (n >= 1_000) return `₹${(n / 1_000).toFixed(0)}K`;
  return `₹${Math.round(n)}`;
}

function formatINRShort(amt) {
  const n = Number(amt || 0);
  if (n >= 1_00_00_000) return `₹${(n / 1_00_00_000).toFixed(1)}Cr`;
  if (n >= 1_00_000) return `₹${(n / 1_00_000).toFixed(1)}L`;
  if (n >= 1_000) return `₹${(n / 1_000).toFixed(0)}K`;
  return `₹${Math.round(n)}`;
}

// ── Filter dropdown ─────────────────────────────────────────────────────────

function MultiSelect({ label, options, value, onChange }) {
  // Single-select implemented as a plain <select> for the demo. Empty value
  // = no filter on this axis. The backend supports multi-value via comma —
  // we wrap in an array so the API helper can join.
  const onPick = (e) => {
    const v = e.target.value;
    onChange(v === "" ? [] : [v]);
  };
  return (
    <select
      className="cacm-dash-filter-select"
      value={value[0] || ""}
      onChange={onPick}
    >
      <option value="">{label}</option>
      {options.map((opt) => (
        <option key={opt} value={opt}>
          {opt}
        </option>
      ))}
    </select>
  );
}

function FilterBar({ data, filters, onFiltersChange, onClearFilters }) {
  const fo = data.filter_options || {};
  const set = (key) => (next) =>
    onFiltersChange({ ...filters, [key]: next });
  const hasAny =
    filters.companies.length ||
    filters.locations.length ||
    filters.risk_levels.length ||
    filters.aging_buckets.length ||
    filters.po_creators.length;
  return (
    <div className="cacm-dash-filter-bar">
      <MultiSelect
        label="All Companies"
        options={fo.companies || []}
        value={filters.companies}
        onChange={set("companies")}
      />
      <MultiSelect
        label="All Locations"
        options={fo.locations || []}
        value={filters.locations}
        onChange={set("locations")}
      />
      <MultiSelect
        label="All Risk Levels"
        options={fo.risk_levels || []}
        value={filters.risk_levels}
        onChange={set("risk_levels")}
      />
      <MultiSelect
        label="All Aging"
        options={fo.aging_buckets || []}
        value={filters.aging_buckets}
        onChange={set("aging_buckets")}
      />
      <MultiSelect
        label="All PO Creators"
        options={fo.po_creators || []}
        value={filters.po_creators}
        onChange={set("po_creators")}
      />
      <button
        type="button"
        className="cacm-dash-filter-clear"
        onClick={onClearFilters}
        disabled={!hasAny}
      >
        Clear
      </button>
    </div>
  );
}

// ── KPI tiles ───────────────────────────────────────────────────────────────

function KpiTile({ value, label, sub, accent }) {
  return (
    <div className="cacm-dash-kpi-tile">
      <div
        className="cacm-dash-kpi-value"
        style={accent ? { color: accent } : undefined}
      >
        {value}
      </div>
      <div className="cacm-dash-kpi-label">{label}</div>
      {sub != null && <div className="cacm-dash-kpi-sub">{sub}</div>}
    </div>
  );
}

function KpiRow({ totals }) {
  const t = totals || {};
  return (
    <div className="cacm-dash-kpi-row">
      <KpiTile
        value={t.total_exceptions ?? 0}
        label="Total Exceptions"
        sub="Across all companies"
        accent="#e74c3c"
      />
      <KpiTile
        value={t.high_risk_count ?? 0}
        label="High Risk"
        sub={`${(t.high_risk_pct ?? 0).toFixed(1)}% of total`}
        accent="#e74c3c"
      />
      <KpiTile
        value={formatINR(t.total_invoice_amt)}
        label="Total Invoice Amt"
        sub="Gross exposure"
        accent="#f59e0b"
      />
      <KpiTile
        value={`${(t.avg_delay_days ?? 0).toFixed(1)}d`}
        label="Avg Delay Days"
        sub="Days after invoice"
      />
      <KpiTile
        value={`${t.max_delay_days ?? 0}d`}
        label="Max Delay"
        sub={t.max_delay_location || "—"}
      />
    </div>
  );
}

// ── Card wrapper ────────────────────────────────────────────────────────────

function Card({ title, subtitle, children, className = "" }) {
  return (
    <div className={`cacm-dash-card ${className}`}>
      <div className="cacm-dash-card-head">
        <div className="cacm-dash-card-title">{title}</div>
        {subtitle && <div className="cacm-dash-card-sub">{subtitle}</div>}
      </div>
      <div className="cacm-dash-card-body">{children}</div>
    </div>
  );
}

// ── Charts ──────────────────────────────────────────────────────────────────

function MonthlyTrendChart({ rows }) {
  if (!rows || rows.length === 0) {
    return <div className="cacm-chart-empty">No data</div>;
  }
  return (
    <ResponsiveContainer width="100%" height={260}>
      <ComposedChart data={rows} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
        <defs>
          <linearGradient id="excArea" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#8b5cf6" stopOpacity={0.5} />
            <stop offset="100%" stopColor="#8b5cf6" stopOpacity={0.05} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
        <XAxis dataKey="month" stroke="var(--ink-dim)" fontSize={11} />
        <YAxis yAxisId="left" stroke="#8b5cf6" fontSize={11} />
        <YAxis yAxisId="right" orientation="right" stroke="#f59e0b" fontSize={11} />
        <Tooltip
          contentStyle={{
            background: "var(--bg-card)",
            border: "1px solid var(--border)",
            fontSize: 12,
          }}
        />
        <Legend wrapperStyle={{ fontSize: 12 }} />
        <Area
          yAxisId="left"
          type="monotone"
          dataKey="exceptions"
          name="Exceptions"
          stroke="#8b5cf6"
          strokeWidth={2}
          fill="url(#excArea)"
        />
        <Line
          yAxisId="right"
          type="monotone"
          dataKey="avg_delay"
          name="Avg Delay (d)"
          stroke="#f59e0b"
          strokeDasharray="5 4"
          strokeWidth={2}
          dot={{ r: 3, fill: "#f59e0b" }}
        />
      </ComposedChart>
    </ResponsiveContainer>
  );
}

function CompanyAnalysisChart({ rows }) {
  if (!rows || rows.length === 0) {
    return <div className="cacm-chart-empty">No data</div>;
  }
  return (
    <ResponsiveContainer width="100%" height={260}>
      <BarChart data={rows} margin={{ top: 10, right: 8, left: -10, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
        <XAxis dataKey="company_code" stroke="var(--ink-dim)" fontSize={11} />
        <YAxis stroke="var(--ink-dim)" fontSize={11} />
        <Tooltip
          contentStyle={{
            background: "var(--bg-card)",
            border: "1px solid var(--border)",
            fontSize: 12,
          }}
        />
        <Legend wrapperStyle={{ fontSize: 11 }} />
        <Bar dataKey="high" name="High" stackId="risk" fill={RISK_COLORS.High} />
        <Bar dataKey="medium" name="Medium" stackId="risk" fill={RISK_COLORS.Medium} />
        <Bar dataKey="low" name="Low" stackId="risk" fill={RISK_COLORS.Low} />
      </BarChart>
    </ResponsiveContainer>
  );
}

function AgingBuckets({ rows }) {
  if (!rows || rows.length === 0) {
    return <div className="cacm-chart-empty">No data</div>;
  }
  const max = Math.max(...rows.map((r) => r.count), 1);
  return (
    <div className="cacm-dash-aging-list">
      {rows.map((r) => {
        const widthPct = (r.count / max) * 100;
        const color = RISK_COLORS[r.risk] || SERIES_FILL;
        return (
          <div key={r.label} className="cacm-dash-aging-row">
            <div className="cacm-dash-aging-label">
              <span style={{ fontWeight: 600, color: "var(--ink)" }}>{r.label}</span>
              <span style={{ color: "var(--ink-dim)", fontSize: 12, marginLeft: 6 }}>
                — {r.risk} Risk
              </span>
            </div>
            <div className="cacm-dash-aging-track">
              <div
                className="cacm-dash-aging-bar"
                style={{ width: `${widthPct}%`, background: color }}
              />
              <div className="cacm-dash-aging-value">
                {r.count}
                <span className="cacm-dash-aging-pct"> ({r.pct}%)</span>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

function PoCreators({ rows }) {
  if (!rows || rows.length === 0) {
    return <div className="cacm-chart-empty">No data</div>;
  }
  const max = Math.max(...rows.map((r) => r.count), 1);
  return (
    <div className="cacm-dash-creator-list">
      {rows.map((r, i) => {
        const widthPct = (r.count / max) * 100;
        const color = CREATOR_PALETTE[i % CREATOR_PALETTE.length];
        return (
          <div key={r.user} className="cacm-dash-creator-row">
            <div className="cacm-dash-creator-name">{r.user}</div>
            <div className="cacm-dash-creator-track">
              <div
                className="cacm-dash-creator-bar"
                style={{ width: `${widthPct}%`, background: color }}
              />
              <div className="cacm-dash-creator-value">
                {r.count} exc · {formatINRShort(r.total_invoice_amt)}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

function FinancialBubble({ rows }) {
  const data = useMemo(() => {
    if (!rows || rows.length === 0) return { high: [], medium: [], low: [] };
    const out = { High: [], Medium: [], Low: [] };
    rows.forEach((r) => {
      const item = {
        x: r.delay_days,
        y: (r.invoice_amount || 0) / 1_00_000, // lakhs
        z: Math.max((r.po_amount || 0) / 1_00_000, 1),
        exception_no: r.exception_no,
        delay: r.delay_days,
        invoice: r.invoice_amount,
        po: r.po_amount,
        risk: r.risk,
      };
      (out[r.risk] || out.Low).push(item);
    });
    return out;
  }, [rows]);

  if (!rows || rows.length === 0) {
    return <div className="cacm-chart-empty">No data</div>;
  }

  const tooltipFmt = (val, name, p) => {
    if (name === "delay") return [`${val} days`, "Delay"];
    if (name === "invoice") return [formatINR(p?.payload?.invoice), "Invoice"];
    if (name === "po") return [formatINR(p?.payload?.po), "PO Amount"];
    return [val, name];
  };

  return (
    <ResponsiveContainer width="100%" height={300}>
      <ScatterChart margin={{ top: 10, right: 30, left: 0, bottom: 5 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
        <XAxis
          type="number"
          dataKey="x"
          name="delay"
          unit="d"
          stroke="var(--ink-dim)"
          fontSize={11}
          label={{
            value: "Delay (days)",
            position: "insideBottom",
            offset: -2,
            fill: "var(--ink-dim)",
            fontSize: 11,
          }}
        />
        <YAxis
          type="number"
          dataKey="y"
          name="invoice"
          unit="L"
          stroke="var(--ink-dim)"
          fontSize={11}
          label={{
            value: "Invoice (₹ Lakh)",
            angle: -90,
            position: "insideLeft",
            fill: "var(--ink-dim)",
            fontSize: 11,
          }}
        />
        <ZAxis type="number" dataKey="z" range={[80, 600]} name="po" />
        <Tooltip
          cursor={{ strokeDasharray: "3 3" }}
          formatter={tooltipFmt}
          contentStyle={{
            background: "var(--bg-card)",
            border: "1px solid var(--border)",
            fontSize: 12,
          }}
        />
        <Legend wrapperStyle={{ fontSize: 11 }} />
        <Scatter name="High" data={data.High} fill={RISK_COLORS.High} fillOpacity={0.7} />
        <Scatter name="Medium" data={data.Medium} fill={RISK_COLORS.Medium} fillOpacity={0.7} />
        <Scatter name="Low" data={data.Low} fill={RISK_COLORS.Low} fillOpacity={0.7} />
      </ScatterChart>
    </ResponsiveContainer>
  );
}

function LocationGrid({ rows }) {
  if (!rows || rows.length === 0) {
    return <div className="cacm-chart-empty">No data</div>;
  }
  return (
    <div className="cacm-dash-location-grid">
      {rows.map((r) => {
        const bg = LOCATION_COLOR_MAP[r.color] || SERIES_FILL;
        return (
          <div
            key={r.location}
            className="cacm-dash-location-card"
            style={{ background: bg }}
          >
            <div className="cacm-dash-location-name">{r.location}</div>
            <div className="cacm-dash-location-count">{r.count}</div>
            <div className="cacm-dash-location-amt">{formatINR(r.total_invoice_amt)}</div>
            <div className="cacm-dash-location-pct">{r.pct_of_total}% of total</div>
          </div>
        );
      })}
    </div>
  );
}

// ── Procurement-rich layout ─────────────────────────────────────────────────

function ProcurementDashboard({
  data,
  filters,
  onFiltersChange,
  onClearFilters,
}) {
  return (
    <div className="cacm-dashboard">
      <FilterBar
        data={data}
        filters={filters}
        onFiltersChange={onFiltersChange}
        onClearFilters={onClearFilters}
      />

      <KpiRow totals={data.totals} />

      <div className="cacm-dash-row cacm-dash-row--7-3">
        <Card
          title="Monthly Trend Analysis"
          subtitle="Exception count & avg delay over time"
        >
          <MonthlyTrendChart rows={data.monthly_trend || []} />
        </Card>
        <Card
          title="Company Analysis"
          subtitle="Exception count by company code"
        >
          <CompanyAnalysisChart rows={data.company_breakdown || []} />
        </Card>
      </div>

      <div className="cacm-dash-row cacm-dash-row--1-1">
        <Card
          title="Aging Bucket Analysis"
          subtitle="Distribution of exceptions by delay window"
        >
          <AgingBuckets rows={data.aging_buckets || []} />
        </Card>
        <Card
          title="User Behavior — PO Creators"
          subtitle="Top creators by exception count"
        >
          <PoCreators rows={data.po_creators || []} />
        </Card>
      </div>

      <div className="cacm-dash-row cacm-dash-row--7-3">
        <Card
          title="Financial Exposure — Bubble Chart"
          subtitle="Invoice amount vs delay days (bubble = PO amount)"
        >
          <FinancialBubble rows={data.financial_exposure || []} />
        </Card>
        <Card title="Location Exposure" subtitle="Exception count by plant">
          <LocationGrid rows={data.location_breakdown || []} />
        </Card>
      </div>
    </div>
  );
}

// ── Inventory dashboard (repeated_material_adjustments) ─────────────────────

// Colour token map for the inventory charts. Mirror the Procurement palette
// where it makes sense; add a few extra tokens (teal / lavender / amber /
// grey) used by movement-type and donut slices.
const INVENTORY_TOKEN_MAP = {
  purple: "#8b5cf6",
  red: "#e74c3c",
  blue: "#3b82f6",
  orange: "#f59e0b",
  green: "#22c55e",
  teal: "#14b8a6",
  lavender: "#c084fc",
  amber: "#fbbf24",
  grey: "#94a3b8",
};

function tokenToHex(token) {
  return INVENTORY_TOKEN_MAP[token] || token || INVENTORY_TOKEN_MAP.purple;
}

function formatCrore(amt) {
  const n = Number(amt || 0);
  if (n >= 1_00_00_000) return `₹${(n / 1_00_00_000).toFixed(2)} Cr`;
  if (n >= 1_00_000) return `₹${(n / 1_00_000).toFixed(2)} L`;
  if (n >= 1_000) return `₹${(n / 1_000).toFixed(0)}K`;
  return `₹${Math.round(n)}`;
}

function InventoryFilterBar({ data, filters, onFiltersChange, onClearFilters }) {
  const fo = data.filter_options || {};
  const set = (key) => (next) =>
    onFiltersChange({ ...filters, [key]: next });
  const hasAny =
    (filters.companies?.length || 0) +
      (filters.locations?.length || 0) +
      (filters.risk_levels?.length || 0) +
      (filters.movement_types?.length || 0) +
      (filters.material_groups?.length || 0) +
      (filters.reversals?.length || 0) >
    0;
  return (
    <div className="cacm-dash-filter-bar">
      <MultiSelect
        label="All Companies"
        options={fo.companies || []}
        value={filters.companies || []}
        onChange={set("companies")}
      />
      <MultiSelect
        label="All Locations"
        options={fo.locations || []}
        value={filters.locations || []}
        onChange={set("locations")}
      />
      <MultiSelect
        label="All Risk Levels"
        options={fo.risk_levels || []}
        value={filters.risk_levels || []}
        onChange={set("risk_levels")}
      />
      <MultiSelect
        label="All Movement Types"
        options={fo.movement_types || []}
        value={filters.movement_types || []}
        onChange={set("movement_types")}
      />
      <MultiSelect
        label="All Material Groups"
        options={fo.material_groups || []}
        value={filters.material_groups || []}
        onChange={set("material_groups")}
      />
      <MultiSelect
        label="All Reversals"
        options={fo.reversals || ["Yes", "No"]}
        value={filters.reversals || []}
        onChange={set("reversals")}
      />
      <button
        type="button"
        className="cacm-dash-filter-clear"
        onClick={onClearFilters}
        disabled={!hasAny}
      >
        Clear
      </button>
    </div>
  );
}

function InventoryKpiRow({ totals }) {
  const t = totals || {};
  return (
    <div className="cacm-dash-kpi-row cacm-dash-kpi-row--6">
      <KpiTile
        value={t.total_exceptions ?? 0}
        label="Total Exceptions"
        sub="Adjustment transactions"
        accent="#e74c3c"
      />
      <KpiTile
        value={t.high_risk_count ?? 0}
        label="High Risk (≥6 ADJ.)"
        sub={`${(t.high_risk_pct ?? 0).toFixed(1)}% of total`}
        accent="#e74c3c"
      />
      <KpiTile
        value={formatCrore(t.total_adj_value)}
        label="Total Adj. Value"
        sub="Gross inventory exposure"
        accent="#f59e0b"
      />
      <KpiTile
        value={(t.avg_adj_count ?? 0).toFixed(1)}
        label="Avg Adj. Count"
        sub="Per material-plant combo"
      />
      <KpiTile
        value={t.reversal_transactions ?? 0}
        label="Reversal Transactions"
        sub={`${(t.reversal_pct ?? 0).toFixed(1)}% of exceptions`}
        accent="#8b5cf6"
      />
      <KpiTile
        value={t.unique_materials ?? 0}
        label="Unique Materials"
        sub="With repeated adjustments"
      />
    </div>
  );
}

function MovementTypeChart({ rows }) {
  if (!rows || rows.length === 0) {
    return <div className="cacm-chart-empty">No data</div>;
  }
  return (
    <ResponsiveContainer width="100%" height={260}>
      <BarChart data={rows} margin={{ top: 10, right: 16, left: -10, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
        <XAxis
          dataKey="label"
          stroke="var(--ink-dim)"
          fontSize={10}
          interval={0}
          angle={-25}
          textAnchor="end"
          height={56}
        />
        <YAxis stroke="var(--ink-dim)" fontSize={11} />
        <Tooltip
          contentStyle={{
            background: "var(--bg-card)",
            border: "1px solid var(--border)",
            fontSize: 12,
          }}
        />
        <Bar dataKey="count" name="Exceptions" radius={[6, 6, 0, 0]}>
          {rows.map((row) => (
            <Cell key={row.code} fill={tokenToHex(row.color)} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

function InventoryMonthlyTrend({ rows }) {
  if (!rows || rows.length === 0) {
    return <div className="cacm-chart-empty">No data</div>;
  }
  // Convert total_value into ₹ Lakh for the right axis so the legend reads
  // small numbers but tooltip can show the original.
  const data = rows.map((r) => ({
    ...r,
    value_lakh: (r.total_value || 0) / 1_00_000,
  }));
  return (
    <ResponsiveContainer width="100%" height={260}>
      <ComposedChart data={data} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
        <defs>
          <linearGradient id="invExcArea" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#8b5cf6" stopOpacity={0.5} />
            <stop offset="100%" stopColor="#8b5cf6" stopOpacity={0.05} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
        <XAxis dataKey="month" stroke="var(--ink-dim)" fontSize={11} />
        <YAxis yAxisId="left" stroke="#8b5cf6" fontSize={11} />
        <YAxis
          yAxisId="right"
          orientation="right"
          stroke="#f59e0b"
          fontSize={11}
          tickFormatter={(v) => `${v.toFixed(0)}L`}
        />
        <Tooltip
          contentStyle={{
            background: "var(--bg-card)",
            border: "1px solid var(--border)",
            fontSize: 12,
          }}
          formatter={(val, name) => {
            if (name === "Total ₹ (Lakh)")
              return [`₹${Number(val).toFixed(2)} L`, "Total Value"];
            return [val, name];
          }}
        />
        <Legend wrapperStyle={{ fontSize: 12 }} />
        <Area
          yAxisId="left"
          type="monotone"
          dataKey="exceptions"
          name="Exceptions"
          stroke="#8b5cf6"
          strokeWidth={2}
          fill="url(#invExcArea)"
        />
        <Line
          yAxisId="right"
          type="monotone"
          dataKey="value_lakh"
          name="Total ₹ (Lakh)"
          stroke="#f59e0b"
          strokeDasharray="5 4"
          strokeWidth={2}
          dot={{ r: 3, fill: "#f59e0b" }}
        />
      </ComposedChart>
    </ResponsiveContainer>
  );
}

function InventoryCompanyChart({ rows }) {
  if (!rows || rows.length === 0) {
    return <div className="cacm-chart-empty">No data</div>;
  }
  return (
    <ResponsiveContainer width="100%" height={260}>
      <BarChart data={rows} margin={{ top: 10, right: 8, left: -10, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
        <XAxis
          dataKey="label"
          stroke="var(--ink-dim)"
          fontSize={10}
          interval={0}
        />
        <YAxis stroke="var(--ink-dim)" fontSize={11} />
        <Tooltip
          contentStyle={{
            background: "var(--bg-card)",
            border: "1px solid var(--border)",
            fontSize: 12,
          }}
        />
        <Legend wrapperStyle={{ fontSize: 11 }} />
        <Bar dataKey="low" name="Low" stackId="risk" fill={RISK_COLORS.Low} />
        <Bar dataKey="medium" name="Medium" stackId="risk" fill={RISK_COLORS.Medium} />
        <Bar dataKey="high" name="High" stackId="risk" fill={RISK_COLORS.High} />
      </BarChart>
    </ResponsiveContainer>
  );
}

function MaterialGroupDonut({ rows }) {
  if (!rows || rows.length === 0) {
    return <div className="cacm-chart-empty">No data</div>;
  }
  return (
    <ResponsiveContainer width="100%" height={260}>
      <PieChart>
        <Pie
          data={rows}
          dataKey="value"
          nameKey="group"
          cx="50%"
          cy="50%"
          innerRadius={55}
          outerRadius={90}
          paddingAngle={2}
          label={({ pct }) => (pct >= 4 ? `${pct}%` : "")}
          labelLine={false}
        >
          {rows.map((row) => (
            <Cell key={row.group} fill={tokenToHex(row.color)} />
          ))}
        </Pie>
        <Tooltip
          contentStyle={{
            background: "var(--bg-card)",
            border: "1px solid var(--border)",
            fontSize: 12,
          }}
          formatter={(val, name, p) => [
            `${formatCrore(val)} (${p?.payload?.pct ?? 0}%)`,
            p?.payload?.group ?? name,
          ]}
        />
        <Legend
          wrapperStyle={{ fontSize: 11 }}
          formatter={(value) => value}
        />
      </PieChart>
    </ResponsiveContainer>
  );
}

function InventoryLocationBars({ rows }) {
  if (!rows || rows.length === 0) {
    return <div className="cacm-chart-empty">No data</div>;
  }
  const max = Math.max(...rows.map((r) => r.count), 1);
  return (
    <div className="cacm-dash-creator-list">
      {rows.map((r) => {
        const widthPct = (r.count / max) * 100;
        const color = tokenToHex(r.color);
        return (
          <div key={r.location} className="cacm-dash-creator-row">
            <div className="cacm-dash-creator-name">{r.label}</div>
            <div className="cacm-dash-creator-track">
              <div
                className="cacm-dash-creator-bar"
                style={{ width: `${widthPct}%`, background: color }}
              />
              <div className="cacm-dash-creator-value">
                {r.count} exc · {r.high_count} High
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

function InventoryDashboard({ data, filters, onFiltersChange, onClearFilters }) {
  return (
    <div className="cacm-dashboard">
      <InventoryFilterBar
        data={data}
        filters={filters}
        onFiltersChange={onFiltersChange}
        onClearFilters={onClearFilters}
      />

      <InventoryKpiRow totals={data.totals} />

      <div className="cacm-dash-row cacm-dash-row--1-1">
        <Card
          title="Movement Type Distribution"
          subtitle="Exception count by SAP movement code"
        >
          <MovementTypeChart rows={data.movement_type_distribution || []} />
        </Card>
        <Card
          title="Monthly Trend Analysis"
          subtitle="Exceptions and total ₹ value by month"
        >
          <InventoryMonthlyTrend rows={data.monthly_trend || []} />
        </Card>
      </div>

      <div className="cacm-dash-row cacm-dash-row--3col">
        <Card
          title="Company Analysis"
          subtitle="Stacked by risk level"
        >
          <InventoryCompanyChart rows={data.company_breakdown || []} />
        </Card>
        <Card
          title="Material Group Exposure"
          subtitle="Adj. value share by material group"
        >
          <MaterialGroupDonut rows={data.material_group_exposure || []} />
        </Card>
        <Card
          title="Location Analysis"
          subtitle="Exceptions and high-risk count per plant"
        >
          <InventoryLocationBars rows={data.location_analysis || []} />
        </Card>
      </div>
    </div>
  );
}

// ── Generic / Inventory fallback layout ─────────────────────────────────────

function SummaryTile({ label, value, accent }) {
  return (
    <div className="cacm-tile">
      <div className="cacm-tile-label">{label}</div>
      <div
        className="cacm-tile-value"
        style={accent ? { color: accent } : undefined}
      >
        {value ?? "—"}
      </div>
    </div>
  );
}

function ChartCard({ title, children, isEmpty }) {
  return (
    <div className="cacm-chart-card">
      <div className="cacm-chart-title">{title}</div>
      {isEmpty ? (
        <div className="cacm-chart-empty">No data</div>
      ) : (
        <div className="cacm-chart-body">{children}</div>
      )}
    </div>
  );
}

function GenericDashboard({ data }) {
  const totals = data?.totals || {};
  const byRisk = asArray(data?.by_risk);
  const byCompany = asArray(data?.by_company);
  const byVendor = asArray(data?.by_vendor);
  const monthly = asArray(data?.monthly_trend);

  return (
    <div className="cacm-dashboard">
      <div className="cacm-tiles">
        <SummaryTile label="Total records" value={totals.total_records ?? totals.records} />
        <SummaryTile
          label="Total exceptions"
          value={totals.total_exceptions ?? totals.exceptions}
          accent="var(--err)"
        />
        <SummaryTile
          label="Exception %"
          value={
            totals.exception_pct != null
              ? `${Number(totals.exception_pct).toFixed(2)}%`
              : "—"
          }
        />
        <SummaryTile label="Open count" value={totals.open_count ?? totals.open} />
      </div>

      <div className="cacm-chart-grid">
        <ChartCard title="By Company Code" isEmpty={byCompany.length === 0}>
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={byCompany}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
              <XAxis
                dataKey={byCompany[0]?.company_code ? "company_code" : "name"}
                stroke="var(--ink-dim)"
                fontSize={11}
              />
              <YAxis stroke="var(--ink-dim)" fontSize={11} />
              <Tooltip
                contentStyle={{
                  background: "var(--bg-card)",
                  border: "1px solid var(--border)",
                  fontSize: 12,
                }}
              />
              <Bar
                dataKey={byCompany[0]?.count != null ? "count" : "value"}
                fill={SERIES_FILL}
              />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="By Risk" isEmpty={byRisk.length === 0}>
          <ResponsiveContainer width="100%" height={260}>
            <PieChart>
              <Pie
                data={byRisk}
                dataKey={byRisk[0]?.count != null ? "count" : "value"}
                nameKey={byRisk[0]?.risk ? "risk" : "name"}
                cx="50%"
                cy="50%"
                outerRadius={90}
                label
              >
                {byRisk.map((entry, idx) => {
                  const key = entry.risk || entry.name;
                  return (
                    <Cell
                      key={`cell-${idx}`}
                      fill={RISK_COLORS[key] || SERIES_FILL}
                    />
                  );
                })}
              </Pie>
              <Tooltip
                contentStyle={{
                  background: "var(--bg-card)",
                  border: "1px solid var(--border)",
                  fontSize: 12,
                }}
              />
            </PieChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="Monthly Trend" isEmpty={monthly.length === 0}>
          <ResponsiveContainer width="100%" height={260}>
            <LineChart data={monthly}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
              <XAxis
                dataKey={monthly[0]?.month ? "month" : "name"}
                stroke="var(--ink-dim)"
                fontSize={11}
              />
              <YAxis stroke="var(--ink-dim)" fontSize={11} />
              <Tooltip
                contentStyle={{
                  background: "var(--bg-card)",
                  border: "1px solid var(--border)",
                  fontSize: 12,
                }}
              />
              <Line
                type="monotone"
                dataKey={monthly[0]?.count != null ? "count" : "value"}
                stroke={SERIES_FILL}
                strokeWidth={2}
                dot={{ r: 3 }}
              />
            </LineChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="Top Vendors" isEmpty={byVendor.length === 0}>
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={byVendor.slice(0, 10)} layout="vertical">
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
              <XAxis type="number" stroke="var(--ink-dim)" fontSize={11} />
              <YAxis
                type="category"
                dataKey={byVendor[0]?.vendor ? "vendor" : "name"}
                stroke="var(--ink-dim)"
                fontSize={11}
                width={120}
              />
              <Tooltip
                contentStyle={{
                  background: "var(--bg-card)",
                  border: "1px solid var(--border)",
                  fontSize: 12,
                }}
              />
              <Bar
                dataKey={byVendor[0]?.count != null ? "count" : "value"}
                fill={VENDOR_FILL}
              />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>
      </div>
    </div>
  );
}

// ── Public component ────────────────────────────────────────────────────────

export default function DashboardCharts({
  data,
  kpiType,
  filters,
  onFiltersChange,
  onClearFilters,
}) {
  // Procurement-specific layout for `po_after_invoice`.
  // Inventory-specific layout for `repeated_material_adjustments`.
  // Anything else (future KPIs) gets the generic 4-chart grid.
  const isProcurement =
    kpiType === "po_after_invoice" ||
    data?.kpi_type === "po_after_invoice" ||
    !!data?.aging_buckets;

  const isInventory =
    kpiType === "repeated_material_adjustments" ||
    data?.kpi_type === "repeated_material_adjustments" ||
    !!data?.movement_type_distribution;

  if (isProcurement && filters && onFiltersChange) {
    return (
      <ProcurementDashboard
        data={data}
        filters={filters}
        onFiltersChange={onFiltersChange}
        onClearFilters={onClearFilters || (() => {})}
      />
    );
  }
  if (isInventory && filters && onFiltersChange) {
    return (
      <InventoryDashboard
        data={data}
        filters={filters}
        onFiltersChange={onFiltersChange}
        onClearFilters={onClearFilters || (() => {})}
      />
    );
  }
  return <GenericDashboard data={data} />;
}
