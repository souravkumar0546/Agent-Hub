import EditableField from './EditableField.jsx';
import { useBrand } from '../lib/brand.js';

/**
 * Live preview of FORM-GMP-QA-0504 — rendered as a white "paper" on a
 * gray backdrop, visually matching Devio's TemplatePanel. Every user-editable
 * field is wired to `onEdit(field_id, new_value)`.
 *
 * Fields not present on the backend (decorative sub-rows on GEMBA,
 * 5-Why chain, fishbone 6M cells, signatures) are rendered as static
 * placeholders — they exist in the printed form but aren't in our session state.
 */

function Cell({ children, header = false, className = '', colSpan, rowSpan }) {
  return (
    <td
      colSpan={colSpan}
      rowSpan={rowSpan}
      className={`tp-cell ${header ? 'tp-cell--header' : ''} ${className}`}
    >
      {children}
    </td>
  );
}

function Field({ id, fields, busy, onEdit, placeholder = '', multiline = true }) {
  const f = fields[id] || {};
  return (
    <EditableField
      value={f.value || ''}
      status={f.status || 'empty'}
      placeholder={placeholder}
      multiline={multiline}
      busy={busy}
      onSave={(v) => onEdit(id, v)}
      paper
    />
  );
}

function SectionHead({ num, title }) {
  return <h2 className="tp-section-head">{num}. {title}</h2>;
}

function SubHead({ text }) {
  return <p className="tp-subhead">{text}</p>;
}

function StaticField({ placeholder = '—' }) {
  return <div className="ef ef--paper ef--empty" aria-disabled>{placeholder}</div>;
}

const SOURCES = ['Deviation', 'OOS', 'OOT', 'Customer Complaint', 'Any other'];

export default function TemplatePreview({ fields = {}, busy = false, onEdit }) {
  const v = (id) => fields[id]?.value || '';
  const selectedSource = (v('source_type') || '').toLowerCase();
  // Show the current org's name in the FORM-GMP-QA-0504 masthead. The SOP
  // structure itself is Syngene-authored; the brand cell is the tenant name.
  const { displayName } = useBrand();

  return (
    <div className="tp-surface">
      <div className="tp-paper">

        {/* ── Header block ───────────────────────────────────────────── */}
        <div className="tp-page">
          <table className="tp-table">
            <tbody>
              <tr>
                <Cell className="tp-brand">{displayName}</Cell>
                <Cell className="tp-center tp-bold">Template</Cell>
                <Cell><b>Department:</b><br/>Quality Assurance</Cell>
              </tr>
              <tr><Cell colSpan={3} className="tp-bold">Reference SOP No.: SOP-GMP-QA-0066</Cell></tr>
              <tr><Cell colSpan={3} className="tp-bold">Title: ANNEXURE 02 - TEMPLATE FOR INVESTIGATION REPORT</Cell></tr>
              <tr>
                <Cell>Document No:<br/><b>FORM-GMP-QA-0504</b></Cell>
                <Cell>Version No.:<br/><b>3.0</b></Cell>
                <Cell>Effective date:<br/><b>04-Jul-2024</b></Cell>
              </tr>
            </tbody>
          </table>

          <h1 className="tp-title">INVESTIGATION REPORT</h1>
          <div className="tp-kv">
            <div className="tp-kv-row">
              <span className="tp-kv-label">DOCUMENT REFERENCE NO.:</span>
              <span className="tp-kv-value">
                <Field id="document_ref_number" placeholder="<<PR# / reference>>" multiline={false}
                  fields={fields} busy={busy} onEdit={onEdit} />
              </span>
            </div>
            <div className="tp-kv-row">
              <span className="tp-kv-label">DATE OF INITIATION:</span>
              <span className="tp-kv-value tp-kv-value--static">{new Date().toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })}</span>
            </div>
          </div>
        </div>

        <hr className="tp-divider" />

        {/* ── Section 1: Source ───────────────────────────────────── */}
        <div className="tp-page">
          <SectionHead num="1" title="SOURCE OF NON-CONFORMITY/UNEXPECTED OUTCOME" />
          <table className="tp-table">
            <thead>
              <tr>
                <Cell header className="tp-w40">Source of Non-Conformity</Cell>
                <Cell header className="tp-w30 tp-center">Category of Non-Conformity<br/>(Critical / Major / Minor)</Cell>
                <Cell header className="tp-w30 tp-center">Document Reference<br/>Number</Cell>
              </tr>
            </thead>
            <tbody>
              {SOURCES.map((src) => {
                const selected = selectedSource === src.toLowerCase();
                return (
                  <tr key={src}>
                    <Cell>
                      <label className="tp-checkbox">
                        <input
                          type="checkbox"
                          checked={selected}
                          onChange={() => !busy && onEdit('source_type', selected ? '' : src)}
                          disabled={busy}
                        />
                        <span className={selected ? 'tp-bold' : ''}>{src}</span>
                      </label>
                    </Cell>
                    <Cell className="tp-pad0">
                      {selected
                        ? <Field id="source_category" placeholder="Critical / Major / Minor" multiline={false}
                                 fields={fields} busy={busy} onEdit={onEdit} />
                        : <span className="tp-empty-line">&nbsp;</span>}
                    </Cell>
                    <Cell className="tp-pad0">
                      {selected
                        ? <Field id="document_ref_number" placeholder="PR# …" multiline={false}
                                 fields={fields} busy={busy} onEdit={onEdit} />
                        : <span className="tp-empty-line">&nbsp;</span>}
                    </Cell>
                  </tr>
                );
              })}
            </tbody>
          </table>

          {/* Section 2 */}
          <SectionHead num="2" title="DESCRIPTION OF THE NON-CONFORMITY/ UNEXPECTED OUTCOME" />
          <SubHead text="2.1. Description:" />
          <Field id="description" placeholder="Describe the non-conformity…" fields={fields} busy={busy} onEdit={onEdit} />
          <SubHead text="2.2. Reference Documents/Instruments/Equipment/Products/Others:" />
          <Field id="reference_docs" placeholder="SOP refs, equipment IDs…" fields={fields} busy={busy} onEdit={onEdit} />
          <SubHead text="2.3. Initiator Name and Department:" />
          <Field id="initiator" placeholder="Name, Employee ID, Department" multiline={false} fields={fields} busy={busy} onEdit={onEdit} />

          {/* Section 3 */}
          <SectionHead num="3" title="PRE-EVALUATION OF THE NON-CONFORMITY/UNEXPECTED OUTCOME" />
          <SubHead text="3.1. Initial/Preliminary Impact assessment:" />
          <Field id="preliminary_impact" fields={fields} busy={busy} onEdit={onEdit} />
          <SubHead text="3.2. Immediate Actions or Correction:" />
          <Field id="immediate_actions" fields={fields} busy={busy} onEdit={onEdit} />

          {/* Section 4 */}
          <SectionHead num="4" title="HISTORICAL CHECK" />
          <table className="tp-table">
            <tbody>
              {[
                ['Reference of relevant data source reviewed for historical check', 'historical_data_source'],
                ['Time frame of review', 'historical_timeframe'],
                ['Justification for selection of less than 12 months time period, if applicable.', 'historical_justification'],
                ['Similar in nature (Earlier PR numbers)', 'historical_similar_events'],
              ].map(([label, fid]) => (
                <tr key={fid}>
                  <Cell header className="tp-w50">{label}</Cell>
                  <Cell className="tp-pad0">
                    <Field id={fid} fields={fields} busy={busy} onEdit={onEdit} />
                  </Cell>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <hr className="tp-divider" />

        {/* ── Section 5: Investigation ────────────────────────────── */}
        <div className="tp-page">
          <SectionHead num="5" title="INVESTIGATION" />

          <SubHead text="5.1 Investigation team (Not mandatory for minor deviation investigations):" />
          <table className="tp-table">
            <thead>
              <tr>
                <Cell header>Name</Cell>
                <Cell header>Employee ID</Cell>
                <Cell header>Designation</Cell>
                <Cell header>Department</Cell>
              </tr>
            </thead>
            <tbody>
              <tr>
                <Cell colSpan={4} className="tp-pad0">
                  <Field id="investigation_team" placeholder="Name | Emp ID | Designation | Dept"
                    fields={fields} busy={busy} onEdit={onEdit} />
                </Cell>
              </tr>
            </tbody>
          </table>

          <SubHead text="5.2 Sequence of events (Not mandatory for minor deviation investigations):" />
          <table className="tp-table">
            <thead>
              <tr>
                <Cell header className="tp-w20">Date</Cell>
                <Cell header className="tp-w15">Time</Cell>
                <Cell header>Event</Cell>
              </tr>
            </thead>
            <tbody>
              <tr>
                <Cell colSpan={3} className="tp-pad0">
                  <Field id="sequence_of_events" fields={fields} busy={busy} onEdit={onEdit} />
                </Cell>
              </tr>
            </tbody>
          </table>

          <SubHead text="5.3 Root Cause Analysis (using investigation tools):" strong />
          <p className="tp-note">(Investigation must be concluded with the highest probable root cause as minimum.)</p>

          {/* 5.3.1 GEMBA */}
          <SubHead text="5.3.1 GEMBA WALK (if applicable):" strong />
          <table className="tp-table">
            <tbody>
              {['GEMBA Walk — Date and Time', 'Location', 'List of personnel', 'Findings'].map((lbl) => (
                <tr key={lbl}>
                  <Cell header className="tp-w40">{lbl}</Cell>
                  <Cell className="tp-pad0"><StaticField /></Cell>
                </tr>
              ))}
              <tr>
                <Cell header className="tp-w40">Inference</Cell>
                <Cell className="tp-pad0">
                  <Field id="gemba_walk" fields={fields} busy={busy} onEdit={onEdit} />
                </Cell>
              </tr>
            </tbody>
          </table>

          {/* 5.3.2 Process mapping */}
          <SubHead text="5.3.2 PROCESS MAPPING AND GAP ANALYSIS (if applicable):" strong />
          <table className="tp-table">
            <thead>
              <tr>
                <Cell header className="tp-w50">What should happen as per procedure</Cell>
                <Cell header>What happened</Cell>
              </tr>
            </thead>
            <tbody>
              <tr>
                <Cell colSpan={2} className="tp-pad0">
                  <Field id="process_mapping" fields={fields} busy={busy} onEdit={onEdit} />
                </Cell>
              </tr>
            </tbody>
          </table>

          {/* 5.3.3 Brainstorming */}
          <SubHead text="5.3.3 BRAINSTORMING (if applicable):" strong />
          <table className="tp-table">
            <tbody>
              {['Date and Time of Brainstorm', 'List of personnel involved', 'Problem statement', 'Possible factors identified'].map((lbl) => (
                <tr key={lbl}>
                  <Cell header className="tp-w45">{lbl}</Cell>
                  <Cell className="tp-pad0"><StaticField /></Cell>
                </tr>
              ))}
              <tr>
                <Cell header className="tp-w45">Inference</Cell>
                <Cell className="tp-pad0">
                  <Field id="brainstorming" fields={fields} busy={busy} onEdit={onEdit} />
                </Cell>
              </tr>
            </tbody>
          </table>

          {/* 5.3.4 Fishbone */}
          <SubHead text="5.3.4 Fishbone analysis (if applicable)" strong />
          <table className="tp-table">
            <tbody>
              <tr>
                <Cell className="tp-w50"><b>Man:</b></Cell>
                <Cell><b>Machine:</b></Cell>
              </tr>
              <tr>
                <Cell><b>Material:</b></Cell>
                <Cell><b>Measurement:</b></Cell>
              </tr>
              <tr>
                <Cell><b>Method:</b></Cell>
                <Cell><b>Mother Nature:</b></Cell>
              </tr>
              <tr>
                <Cell colSpan={2} className="tp-pad0">
                  <span className="tp-inline-label">Inference:</span>
                  <Field id="fishbone" fields={fields} busy={busy} onEdit={onEdit} />
                </Cell>
              </tr>
            </tbody>
          </table>

          {/* 5.3.5 Fault tree */}
          <SubHead text="5.3.5 Fault Tree Analysis (if applicable):" strong />
          <Field id="fault_tree" fields={fields} busy={busy} onEdit={onEdit} />

          {/* 5.3.6 Pareto */}
          <SubHead text="5.3.6 Pareto Analysis (if applicable):" strong />
          <Field id="pareto" fields={fields} busy={busy} onEdit={onEdit} />

          {/* 5.3.7 5-Why */}
          <SubHead text="5.3.7 5-WHY Analysis (if applicable):" strong />
          <table className="tp-table">
            <tbody>
              <tr><Cell colSpan={2} className="tp-bold">Problem Statement:</Cell></tr>
              {['Why 1', 'Why 2', 'Why 3', 'Why 4', 'Why 5'].map((lbl) => (
                <tr key={lbl}>
                  <Cell header className="tp-w15">{lbl}</Cell>
                  <Cell className="tp-pad0"><StaticField /></Cell>
                </tr>
              ))}
              <tr>
                <Cell header className="tp-w15">Inference</Cell>
                <Cell className="tp-pad0">
                  <Field id="five_why" fields={fields} busy={busy} onEdit={onEdit} />
                </Cell>
              </tr>
            </tbody>
          </table>

          <SubHead text="5.4 Summary of data and documents reviewed, and experiments done:" />
          <Field id="data_summary" fields={fields} busy={busy} onEdit={onEdit} />

          <SubHead text="5.5 Evaluation of root cause with historical check findings:" />
          <table className="tp-table">
            <thead>
              <tr>
                <Cell header>PR Number</Cell>
                <Cell header>Root cause</Cell>
                <Cell header>CAPA</Cell>
              </tr>
            </thead>
            <tbody>
              <tr>
                <Cell colSpan={3} className="tp-pad0">
                  <Field id="historical_root_cause_eval" fields={fields} busy={busy} onEdit={onEdit} />
                </Cell>
              </tr>
            </tbody>
          </table>

          <SubHead text="5.6 List of root causes and contributing factors:" />
          <table className="tp-table">
            <thead>
              <tr>
                <Cell header className="tp-w45">Type (Definitive / Most Probable / Contributing)</Cell>
                <Cell header>Cause description</Cell>
              </tr>
            </thead>
            <tbody>
              <tr>
                <Cell colSpan={2} className="tp-pad0">
                  <Field id="root_causes" fields={fields} busy={busy} onEdit={onEdit} />
                </Cell>
              </tr>
            </tbody>
          </table>
        </div>

        <hr className="tp-divider" />

        {/* ── Section 6: Impact ───────────────────────────────────── */}
        <div className="tp-page">
          <SectionHead num="6" title="IMPACT ASSESSMENT" />
          {[
            ['6.1', 'Impact on the quality of the product', 'impact_product_quality'],
            ['6.2', 'Impact on other products manufactured/analysed in the same facility/lab', 'impact_other_products'],
            ['6.3', 'Impact on other batches, equipment, facility, systems, documents', 'impact_other_batches'],
            ['6.4', 'Impact on quality management system, compliance and regulatory submission documents', 'impact_qms_regulatory'],
            ['6.5', 'Impact on validated state of product/process/method/stability', 'impact_validated_state'],
            ['6.6', 'Impact on preventive maintenance, calibration or qualification status', 'impact_pm_calibration'],
          ].map(([num, label, fid]) => (
            <div key={fid}>
              <SubHead text={`${num} ${label}:`} />
              <Field id={fid} fields={fields} busy={busy} onEdit={onEdit} />
            </div>
          ))}
        </div>

        <hr className="tp-divider" />

        {/* ── Section 7: CAPA ─────────────────────────────────────── */}
        <div className="tp-page">
          <SectionHead num="7" title="CORRECTIVE AND PREVENTIVE ACTIONS" />
          {[
            ['Correction', 'corrections', 'Timeline'],
            ['Corrective Action', 'corrective_actions', 'Target Timeline'],
            ['Preventive Action', 'preventive_actions', 'Target Timeline'],
          ].map(([label, fid, tl]) => (
            <table key={fid} className="tp-table">
              <thead>
                <tr>
                  <Cell header className="tp-w8">Sl. No.</Cell>
                  <Cell header className="tp-w40">{label}</Cell>
                  <Cell header className="tp-w26">Responsibility (Department)</Cell>
                  <Cell header>{tl}</Cell>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <Cell className="tp-center">1.</Cell>
                  <Cell colSpan={3} className="tp-pad0">
                    <Field id={fid} fields={fields} busy={busy} onEdit={onEdit} />
                  </Cell>
                </tr>
              </tbody>
            </table>
          ))}

          <SectionHead num="8" title="CONCLUSION" />
          <Field id="conclusion" fields={fields} busy={busy} onEdit={onEdit} />

          <SectionHead num="9" title="ATTACHMENTS (if applicable)" />
          <table className="tp-table">
            <thead>
              <tr>
                <Cell header className="tp-w20 tp-center">Attachment no.</Cell>
                <Cell header>Details</Cell>
              </tr>
            </thead>
            <tbody>
              {[1, 2].map((n) => (
                <tr key={n}>
                  <Cell className="tp-center">{n}.</Cell>
                  <Cell className="tp-pad0"><StaticField /></Cell>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <hr className="tp-divider" />

        {/* ── Sections 10 / 11 ────────────────────────────────────── */}
        <div className="tp-page">
          <SectionHead num="10" title="ABBREVIATIONS" />
          <Field id="abbreviations" fields={fields} busy={busy} onEdit={onEdit} />

          <SectionHead num="11" title="INVESTIGATION TEAM SIGNATURES" />
          <table className="tp-table">
            <thead>
              <tr>
                <Cell header className="tp-w26"></Cell>
                <Cell header className="tp-center">Name</Cell>
                <Cell header className="tp-center">Designation</Cell>
                <Cell header className="tp-center">Department</Cell>
                <Cell header className="tp-center">Sign &amp;<br/>Date</Cell>
              </tr>
            </thead>
            <tbody>
              {['Prepared by (User Department)', 'Reviewed by (HOD/Designee)', 'Reviewed by (Investigation Team)', 'Approved by (QA)'].map((role) => (
                <tr key={role}>
                  <Cell header className="tp-role">{role}</Cell>
                  <Cell className="tp-pad0"><StaticField /></Cell>
                  <Cell className="tp-pad0"><StaticField /></Cell>
                  <Cell className="tp-pad0"><StaticField /></Cell>
                  <Cell className="tp-pad0"><StaticField /></Cell>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

      </div>
    </div>
  );
}
