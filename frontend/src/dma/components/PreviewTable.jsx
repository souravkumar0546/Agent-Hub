import React from "react";

export default function PreviewTable({ columns, rows, rowCount, title }) {
  if (!rows || rows.length === 0) return null;
  return (
    <div className="table-container" style={{ maxHeight: 260 }}>
      <div className="table-header">
        {title || "Preview"} &mdash; {rowCount?.toLocaleString()} rows, {columns.length} columns
      </div>
      <table>
        <thead>
          <tr>{columns.map((c) => <th key={c}>{c}</th>)}</tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i}>{columns.map((c) => <td key={c}>{r[c] ?? ""}</td>)}</tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
