import React from "react";

export function MultiColumnPicker({ columns, selected, onChange, label }) {
  const toggle = (col) => {
    if (selected.includes(col)) {
      onChange(selected.filter((c) => c !== col));
    } else {
      onChange([...selected, col]);
    }
  };
  return (
    <div className="form-group" style={{ flex: "1 1 100%" }}>
      <label>{label}</label>
      <div className="chips">
        {columns.map((col) => (
          <span
            key={col}
            className={`chip ${selected.includes(col) ? "selected" : ""}`}
            onClick={() => toggle(col)}
          >
            {col}
          </span>
        ))}
      </div>
      {selected.length > 0 && (
        <div className="muted">{selected.length} selected: {selected.join(", ")}</div>
      )}
    </div>
  );
}

export function SingleColumnPicker({ columns, value, onChange, label, placeholder }) {
  return (
    <div className="form-group">
      <label>{label}</label>
      <select value={value} onChange={(e) => onChange(e.target.value)}>
        <option value="">{placeholder || "-- Select --"}</option>
        {columns.map((col) => (
          <option key={col} value={col}>{col}</option>
        ))}
      </select>
    </div>
  );
}
