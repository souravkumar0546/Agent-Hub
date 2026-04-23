import React from "react";

/**
 * Vertical process flow diagram for agent sidebar.
 *
 * Props:
 *   title    – heading above the diagram
 *   phases   – array of { label, nodes: [{ text, type }] }
 *              type: "input" | "process" | "ai" | "decision" | "output"
 */

const ICONS = {
  input:    "\u{1F4C4}",   // document
  process:  "\u2699\uFE0F", // gear
  ai:       "\u{1F916}",   // robot
  decision: "\u{1F500}",   // shuffle / branch
  output:   "\u2705",      // check
};

const TYPE_CLASS = {
  input:    "flow-node--input",
  process:  "flow-node--process",
  ai:       "flow-node--ai",
  decision: "flow-node--decision",
  output:   "flow-node--output",
};

export default function FlowDiagram({ title, phases }) {
  return (
    <div className="flow-diagram">
      <div className="flow-title">{title}</div>

      {phases.map((phase, pi) => (
        <div key={pi} className="flow-phase">
          {phase.label && <div className="flow-phase-label">{phase.label}</div>}

          {phase.nodes.map((node, ni) => (
            <div key={ni} className="flow-node-wrapper">
              <div className={`flow-node ${TYPE_CLASS[node.type] || ""}`}>
                <span className="flow-node-icon">{ICONS[node.type] || "\u25CF"}</span>
                <span className="flow-node-text">{node.text}</span>
              </div>
              {/* arrow between nodes, except after last node of last phase */}
              {!(pi === phases.length - 1 && ni === phase.nodes.length - 1) && (
                <div className="flow-arrow" />
              )}
            </div>
          ))}
        </div>
      ))}

      <div className="flow-legend">
        <div className="flow-legend-title">Legend</div>
        <div className="flow-legend-items">
          <span className="flow-legend-item"><span className="flow-dot flow-dot--input" />Input</span>
          <span className="flow-legend-item"><span className="flow-dot flow-dot--process" />Process</span>
          <span className="flow-legend-item"><span className="flow-dot flow-dot--ai" />AI Step</span>
          <span className="flow-legend-item"><span className="flow-dot flow-dot--decision" />Decision</span>
          <span className="flow-legend-item"><span className="flow-dot flow-dot--output" />Output</span>
        </div>
      </div>
    </div>
  );
}


/* ─── Per-agent flow data ────────────────────────── */

export const MASTER_BUILDER_FLOW = {
  title: "Forge · Pipeline",
  phases: [
    {
      label: "Data Input",
      nodes: [
        { text: "Upload raw master data (.xlsx/.csv)", type: "input" },
        { text: "Select material type (taxonomy)", type: "input" },
        { text: "Map columns (description, classification, status)", type: "input" },
      ],
    },
    {
      label: "Fix Inconsistencies",
      nodes: [
        { text: "Clean descriptions (strip catalog #, brands, units)", type: "process" },
        { text: "Generate blocking keys & candidate groups", type: "process" },
        { text: "TF-IDF cosine similarity within groups", type: "process" },
        { text: "Identify inconsistent groups (mixed classes)", type: "decision" },
        { text: "AI validate groups & remove outliers", type: "ai" },
        { text: "AI reclassify inconsistent groups", type: "ai" },
      ],
    },
    {
      label: "Persist",
      nodes: [
        { text: "Merge with existing master (if append mode)", type: "process" },
        { text: "Save corrected master to disk", type: "output" },
      ],
    },
  ],
};

export const CLASSIFY_AGENT_FLOW = {
  title: "Curator · Pipeline",
  phases: [
    {
      label: "Setup",
      nodes: [
        { text: "Select material type (taxonomy)", type: "input" },
        { text: "Load persisted master from disk", type: "process" },
      ],
    },
    {
      label: "Classify",
      nodes: [
        { text: "Enter description or upload batch Excel", type: "input" },
        { text: "Build TF-IDF index from master", type: "process" },
        { text: "Search for matching material group", type: "process" },
        { text: "AI confirm match or classify from scratch", type: "ai" },
      ],
    },
    {
      label: "Output",
      nodes: [
        { text: "Assigned L2 category per material", type: "output" },
        { text: "Optionally add to persisted master", type: "output" },
      ],
    },
  ],
};

export const CLASSIFICATION_FLOW = {
  title: "Curator · Full Pipeline",
  phases: [
    {
      label: "Phase 1 — Fix Master",
      nodes: [
        { text: "Upload master data (.xlsx/.csv)", type: "input" },
        { text: "Clean descriptions (strip catalog #, brands, units)", type: "process" },
        { text: "Generate blocking keys & candidate groups", type: "process" },
        { text: "TF-IDF cosine similarity within groups", type: "process" },
        { text: "Identify inconsistent groups (mixed classes)", type: "decision" },
        { text: "AI validate groups & remove outliers", type: "ai" },
        { text: "AI reclassify inconsistent groups into L2 category", type: "ai" },
        { text: "Fixed master data with corrections applied", type: "output" },
      ],
    },
    {
      label: "Phase 2 — Classify New",
      nodes: [
        { text: "Enter new material description", type: "input" },
        { text: "Build TF-IDF index from fixed master", type: "process" },
        { text: "Search for best matching group", type: "process" },
        { text: "AI confirm match or classify as new", type: "ai" },
        { text: "Assigned L2 category + add to master", type: "output" },
      ],
    },
  ],
};

export const GROUP_DUPLICATES_FLOW = {
  title: "Twin · Pipeline",
  phases: [
    {
      label: "Data Ingestion",
      nodes: [
        { text: "Upload file (.xlsx/.csv)", type: "input" },
        { text: "Select identifier & comparison columns", type: "input" },
      ],
    },
    {
      label: "Text Cleaning",
      nodes: [
        { text: "Lowercase & strip whitespace", type: "process" },
        { text: "Remove special characters (#, @, |, etc.)", type: "process" },
        { text: "Collapse multiple spaces", type: "process" },
      ],
    },
    {
      label: "Similarity Analysis",
      nodes: [
        { text: "Build per-column TF-IDF char n-gram matrices", type: "process" },
        { text: "Compute pairwise cosine similarity + token containment", type: "process" },
        { text: "Weighted scoring (primary 60% + secondary 40%)", type: "process" },
      ],
    },
    {
      label: "Grouping & Validation",
      nodes: [
        { text: "Group pairs above threshold into blocks", type: "decision" },
        { text: "Assign verdicts: Exact / Very Likely / Potential", type: "decision" },
        { text: "AI variant filter (same product, different size/qty)", type: "ai" },
      ],
    },
    {
      label: "Output",
      nodes: [
        { text: "Color-coded duplicate groups report", type: "output" },
      ],
    },
  ],
};

export const LOOKUP_FLOW = {
  title: "Sonar · Pipeline",
  phases: [
    {
      label: "Setup",
      nodes: [
        { text: "Upload reference file (.xlsx/.csv)", type: "input" },
        { text: "Select search columns (primary + secondary)", type: "input" },
        { text: "Enter search values for each column", type: "input" },
      ],
    },
    {
      label: "Search Pipeline",
      nodes: [
        { text: "Build per-column TF-IDF corpora", type: "process" },
        { text: "Check for exact matches (case-insensitive)", type: "process" },
        { text: "TF-IDF candidate search on primary column", type: "process" },
        { text: "Token-level keyword overlap matching", type: "process" },
      ],
    },
    {
      label: "Scoring & Verdict",
      nodes: [
        { text: "Per-column scoring (primary 60%, secondary 40%)", type: "decision" },
        { text: "Rank top-N results above threshold", type: "decision" },
        { text: "Final verdict: Exact / Very Likely / Possible / No Match", type: "output" },
      ],
    },
  ],
};

export const DATA_ENRICHMENT_FLOW = {
  title: "Echo · Pipeline",
  phases: [
    {
      label: "Data Ingestion",
      nodes: [
        { text: "Upload material data file (.xlsx)", type: "input" },
        { text: "Select CAS Number column", type: "input" },
      ],
    },
    {
      label: "BLDPharm Lookup",
      nodes: [
        { text: "Clean CAS number (digits + hyphens only)", type: "process" },
        { text: "Fetch product page: bldpharm.com/products/<CAS>.html", type: "process" },
        { text: "Single-shot HTTP GET (no retries)", type: "decision" },
        { text: "Rate-limited at ~1 req/sec", type: "process" },
      ],
    },
    {
      label: "Taxonomy Extraction",
      nodes: [
        { text: "Parse breadcrumb navigation from product page", type: "process" },
        { text: "Extract classification hierarchy (e.g. Products > Catalysts > ...)", type: "process" },
        { text: "Mark unmapped if no product page found", type: "decision" },
      ],
    },
    {
      label: "Output",
      nodes: [
        { text: "Append Search Result & Source columns", type: "output" },
        { text: "Download enriched Excel report", type: "output" },
      ],
    },
  ],
};
