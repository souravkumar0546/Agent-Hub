import React from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

/** Map a backend dashboard payload onto a 4-tile summary header + a 2x2
 *  grid of charts. Each chart renders an empty-state placeholder if the
 *  corresponding data array is missing or empty. */

const RISK_COLORS = {
  High: "#e74c3c",
  Medium: "#f59e0b",
  Low: "#22c55e",
};

const SERIES_FILL = "#5b8cff";
const VENDOR_FILL = "#a06cd5";

function asArray(maybe) {
  if (!maybe) return [];
  if (Array.isArray(maybe)) return maybe;
  // Allow `{ HIGH: 5, MEDIUM: 3 }` style objects.
  return Object.entries(maybe).map(([name, value]) => ({ name, value }));
}

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

export default function DashboardCharts({ data }) {
  const totals = data?.totals || {};
  const byRisk = asArray(data?.by_risk);
  const byCompany = asArray(data?.by_company);
  const byVendor = asArray(data?.by_vendor);
  const monthly = asArray(data?.monthly_trend);

  return (
    <div className="cacm-dashboard">
      <div className="cacm-tiles">
        <SummaryTile
          label="Total records"
          value={totals.total_records ?? totals.records}
        />
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
        <SummaryTile
          label="Open count"
          value={totals.open_count ?? totals.open}
        />
      </div>

      <div className="cacm-chart-grid">
        <ChartCard title="By Company Code" isEmpty={byCompany.length === 0}>
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={byCompany}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
              <XAxis dataKey={byCompany[0]?.company_code ? "company_code" : "name"} stroke="var(--ink-dim)" fontSize={11} />
              <YAxis stroke="var(--ink-dim)" fontSize={11} />
              <Tooltip
                contentStyle={{
                  background: "var(--bg-card)",
                  border: "1px solid var(--border)",
                  fontSize: 12,
                }}
              />
              <Bar dataKey={byCompany[0]?.count != null ? "count" : "value"} fill={SERIES_FILL} />
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
              <XAxis dataKey={monthly[0]?.month ? "month" : "name"} stroke="var(--ink-dim)" fontSize={11} />
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
              <Bar dataKey={byVendor[0]?.count != null ? "count" : "value"} fill={VENDOR_FILL} />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>
      </div>
    </div>
  );
}
