import React, { useRef, useState } from "react";
import { uploadPreview } from "../api";

export default function FileUpload({ onUpload, label = "Upload Excel file" }) {
  const inputRef = useRef(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [fileName, setFileName] = useState("");
  const [dragging, setDragging] = useState(false);

  async function processFile(file) {
    if (!file) return;
    setError("");
    setFileName(file.name);
    setLoading(true);
    try {
      const preview = await uploadPreview(file);
      onUpload({ file, ...preview });
    } catch (err) {
      setError(err.response?.data?.detail || err.message || "Upload failed");
    } finally {
      setLoading(false);
    }
  }

  function handleChange(e) {
    processFile(e.target.files[0]);
  }

  function handleDrop(e) {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) processFile(file);
  }

  function handleDragOver(e) {
    e.preventDefault();
    setDragging(true);
  }

  function handleDragLeave() {
    setDragging(false);
  }

  return (
    <div>
      <div className="form-group">
        <label>{label}</label>
        <div
          className={`upload-zone${dragging ? " dragging" : ""}`}
          onClick={() => inputRef.current?.click()}
          onDrop={handleDrop}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
        >
          <div className="upload-zone-icon">{fileName && !error ? "\u2705" : "\u{1F4C2}"}</div>
          <div className="upload-zone-text">
            {fileName && !loading && !error
              ? fileName
              : "Click to browse or drag & drop your file here"}
          </div>
          <div className="upload-zone-sub">Supports .xlsx, .xls, and .csv files</div>
          <input
            type="file"
            accept=".xlsx,.xls,.csv"
            ref={inputRef}
            onChange={handleChange}
          />
        </div>
      </div>
      {loading && <div className="alert alert-info">Reading file...</div>}
      {error && <div className="alert alert-error">{error}</div>}
    </div>
  );
}
