import React, { useState } from "react";
import {
  createSchedule,
  deleteSchedule,
  updateSchedule,
} from "../api.js";

/** ScheduleModal — create/edit/delete a recurring schedule for a single KRI.
 *
 *  Props:
 *    mode:        "create" | "edit"
 *    processKey:  string
 *    kriName:     string
 *    schedule:    existing ScheduleSummary (only in edit mode)
 *    onClose():   user dismissed without saving
 *    onSaved(s):  successful create or update — receives ScheduleSummary
 *    onDeleted(): successful delete
 */
const FREQUENCY_OPTIONS = [
  { value: "daily", label: "Daily" },
  { value: "weekly", label: "Weekly" },
  { value: "monthly", label: "Monthly" },
  { value: "quarterly", label: "Quarterly" },
  { value: "half_yearly", label: "Half-yearly" },
  { value: "annually", label: "Annually" },
];

function _formatLocal(iso) {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

// time_of_day is stored UTC on the wire so the cron math is timezone-agnostic.
// The user enters local time in the modal — these helpers bridge the two by
// using a same-day Date object, which (outside of DST transitions) is enough
// to round-trip HH:MM through the local offset.
function _localHmToUtc(hm) {
  const [h, m] = hm.split(":").map(Number);
  if (Number.isNaN(h) || Number.isNaN(m)) return hm;
  const d = new Date();
  d.setHours(h, m, 0, 0);
  const uh = String(d.getUTCHours()).padStart(2, "0");
  const um = String(d.getUTCMinutes()).padStart(2, "0");
  return `${uh}:${um}`;
}
function _utcHmToLocal(hm) {
  const [h, m] = hm.split(":").map(Number);
  if (Number.isNaN(h) || Number.isNaN(m)) return hm;
  const d = new Date();
  d.setUTCHours(h, m, 0, 0);
  const lh = String(d.getHours()).padStart(2, "0");
  const lm = String(d.getMinutes()).padStart(2, "0");
  return `${lh}:${lm}`;
}

export default function ScheduleModal({
  mode,
  processKey,
  kriName,
  schedule,
  onClose,
  onSaved,
  onDeleted,
}) {
  const [frequency, setFrequency] = useState(
    schedule?.frequency || "daily"
  );
  // The input shows local time; the stored value is UTC, so flip on load.
  const [timeOfDay, setTimeOfDay] = useState(
    schedule?.time_of_day ? _utcHmToLocal(schedule.time_of_day) : "09:00"
  );
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const validTime = /^[0-2]\d:[0-5]\d$/.test(timeOfDay);
  const canSave = !!frequency && validTime && !busy;

  async function handleSave() {
    setBusy(true);
    setErr("");
    try {
      const utcTime = _localHmToUtc(timeOfDay);
      if (mode === "edit" && schedule) {
        const out = await updateSchedule(schedule.id, {
          frequency,
          time_of_day: utcTime,
        });
        onSaved(out);
      } else {
        const out = await createSchedule({
          process_key: processKey,
          kri_name: kriName,
          frequency,
          time_of_day: utcTime,
        });
        onSaved(out);
      }
    } catch (e) {
      setErr(
        e.response?.data?.detail || e.message || "Failed to save schedule."
      );
    } finally {
      setBusy(false);
    }
  }

  async function handleDelete() {
    if (!schedule) return;
    if (!window.confirm("Delete this schedule?")) return;
    setBusy(true);
    setErr("");
    try {
      await deleteSchedule(schedule.id);
      onDeleted();
    } catch (e) {
      setErr(
        e.response?.data?.detail || e.message || "Failed to delete schedule."
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="cacm-schedule-modal-overlay" onClick={onClose}>
      <div
        className="cacm-schedule-modal-card"
        role="dialog"
        aria-label="Schedule KRI"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="cacm-schedule-modal-head">
          <div className="cacm-schedule-modal-title">
            {mode === "edit" ? "Edit schedule" : "Schedule KRI"}
          </div>
          <div className="cacm-schedule-modal-sub">{kriName}</div>
        </div>

        <div className="cacm-schedule-modal-body">
          <label className="cacm-schedule-modal-field">
            <span>Frequency</span>
            <select
              value={frequency}
              onChange={(e) => setFrequency(e.target.value)}
              disabled={busy}
            >
              {FREQUENCY_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </label>

          <label className="cacm-schedule-modal-field">
            <span>Time of run</span>
            <input
              type="time"
              value={timeOfDay}
              onChange={(e) => setTimeOfDay(e.target.value)}
              disabled={busy}
            />
          </label>

          {mode === "edit" && schedule && (
            <div className="cacm-schedule-modal-meta">
              <div>
                <span>Next run</span>
                <strong>{_formatLocal(schedule.next_run_at)}</strong>
              </div>
              <div>
                <span>Last run</span>
                <strong>{_formatLocal(schedule.last_run_at)}</strong>
              </div>
            </div>
          )}

          {err && <div className="inv-warning">{err}</div>}
        </div>

        <div className="cacm-schedule-modal-foot">
          {mode === "edit" && (
            <button
              type="button"
              className="btn"
              onClick={handleDelete}
              disabled={busy}
            >
              Delete
            </button>
          )}
          <span style={{ flex: 1 }} />
          <button
            type="button"
            className="btn"
            onClick={onClose}
            disabled={busy}
          >
            Cancel
          </button>
          <button
            type="button"
            className="btn btn-primary"
            onClick={handleSave}
            disabled={!canSave}
          >
            {busy ? "Saving…" : mode === "edit" ? "Save changes" : "Save"}
          </button>
        </div>
      </div>
    </div>
  );
}
