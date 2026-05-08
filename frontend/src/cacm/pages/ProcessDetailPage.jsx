import React, { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import AppShell from "../../components/AppShell.jsx";
import { getProcess, listSchedules, startRun } from "../api.js";
import ScheduleModal from "../components/ScheduleModal.jsx";
import "../styles.css";

/** ProcessDetailPage — /agents/cacm/processes/:processKey. Each KRI row
 *  has explicit Run + Schedule actions, and an eye-icon view button when
 *  a schedule already exists for that KRI.
 */
export default function ProcessDetailPage() {
  const { processKey } = useParams();
  const navigate = useNavigate();
  const [process, setProcess] = useState(null);
  const [schedulesByKri, setSchedulesByKri] = useState(new Map());
  const [err, setErr] = useState("");
  const [starting, setStarting] = useState(false);
  const [startError, setStartError] = useState("");
  const [modal, setModal] = useState(null); // { mode, kriName, schedule? }

  async function loadSchedules() {
    try {
      const data = await listSchedules({ processKey });
      const map = new Map();
      for (const s of data.schedules || []) {
        map.set(s.kri_name, s);
      }
      setSchedulesByKri(map);
      return map;
    } catch (e) {
      console.error("listSchedules failed", e);
      return null;
    }
  }

  useEffect(() => {
    let cancelled = false;
    setProcess(null);
    setErr("");
    getProcess(processKey)
      .then((data) => {
        if (cancelled) return;
        setProcess(data);
      })
      .catch((e) => {
        if (cancelled) return;
        const status = e.response?.status;
        if (status === 404) setErr("Process not found.");
        else
          setErr(
            e.response?.data?.detail || e.message || "Failed to load process."
          );
      });
    loadSchedules();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [processKey]);

  async function handleRun(kri) {
    if (!kri.kpi_type || starting) return;
    setStarting(true);
    setStartError("");
    try {
      const data = await startRun(kri.kpi_type);
      if (!data?.run_id) throw new Error("Backend did not return a run_id.");
      navigate(`/agents/cacm/run/${data.run_id}`);
    } catch (e) {
      setStartError(
        e.response?.data?.detail || e.message || "Failed to start run."
      );
    } finally {
      setStarting(false);
    }
  }

  function openCreate(kri) {
    setModal({ mode: "create", kriName: kri.name });
  }
  async function openEdit(kri) {
    // Refetch first so we never open the modal with a stale next_run
    // (the scheduler advances next_run_at every minute as runs fire).
    const fresh = await loadSchedules();
    const existing = (fresh || schedulesByKri).get(kri.name);
    if (!existing) return;
    setModal({ mode: "edit", kriName: kri.name, schedule: existing });
  }

  const kris = useMemo(() => process?.kris || [], [process]);

  return (
    <AppShell crumbs={["Agent Hub", "Prism", process?.name || "Process"]}>
      <div className="cacm-hero">
        <div style={{ flex: 1, minWidth: 0 }}>
          <Link to="/agents/cacm" className="cacm-back-link">
            ← All Processes
          </Link>
          <h1 className="page-title" style={{ marginTop: 8, marginBottom: 6 }}>
            {process?.name || "…"}
          </h1>
          {process && (
            <div className="page-subtitle" style={{ marginBottom: 10 }}>
              {process.intro}
            </div>
          )}
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <Link to="/agents/cacm/runs" className="btn">
            Run history
          </Link>
          <Link to="/agents/cacm" className="btn">
            ← All processes
          </Link>
        </div>
      </div>

      {err && <div className="inv-warning">{err}</div>}
      {startError && <div className="inv-warning">{startError}</div>}
      {starting && <div className="cacm-loading">Starting run…</div>}

      {!err && process === null && (
        <div className="cacm-loading">Loading process…</div>
      )}

      {!err && process && kris.length > 0 && (
        <div className="cacm-kri-list">
          {kris.map((kri, idx) => {
            const scheduled = schedulesByKri.get(kri.name);
            return (
              <div
                key={`${kri.kpi_type || "kri"}-${idx}`}
                className="cacm-kri-row"
              >
                <div className="cacm-kri-item-main">
                  <div className="cacm-kri-item-name">{kri.name}</div>
                </div>
                <div className="cacm-kri-actions">
                  <button
                    type="button"
                    className="btn btn-primary"
                    onClick={() => handleRun(kri)}
                    disabled={!kri.kpi_type || starting}
                  >
                    ▶ Run
                  </button>
                  <button
                    type="button"
                    className="btn"
                    onClick={() => openCreate(kri)}
                    disabled={starting}
                    title="Create / replace recurring schedule"
                  >
                    ⏱ Schedule
                  </button>
                  {scheduled && (
                    <button
                      type="button"
                      className="cacm-kri-eye"
                      aria-label="View schedule"
                      title="View schedule"
                      onClick={() => openEdit(kri)}
                    >
                      👁
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {modal && (
        <ScheduleModal
          mode={modal.mode}
          processKey={processKey}
          kriName={modal.kriName}
          schedule={modal.schedule}
          onClose={() => setModal(null)}
          onSaved={(updated) => {
            // Update the map directly from the server response so a
            // re-open of the eye icon never sees stale data, even before
            // the background refresh lands.
            setSchedulesByKri((prev) => {
              const next = new Map(prev);
              next.set(updated.kri_name, updated);
              return next;
            });
            setModal(null);
            loadSchedules();
          }}
          onDeleted={() => {
            setSchedulesByKri((prev) => {
              const next = new Map(prev);
              if (modal.schedule) next.delete(modal.schedule.kri_name);
              return next;
            });
            setModal(null);
            loadSchedules();
          }}
        />
      )}
    </AppShell>
  );
}
