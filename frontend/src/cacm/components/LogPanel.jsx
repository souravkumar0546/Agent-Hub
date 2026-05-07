import React, { useEffect, useRef } from "react";

/** Dark monospace scroll panel that streams `[stage] message` lines as
 *  they arrive. Auto-scrolls the latest line into view on every update.
 */
export default function LogPanel({ events = [] }) {
  const endRef = useRef(null);

  useEffect(() => {
    if (endRef.current) {
      endRef.current.scrollIntoView({ behavior: "smooth", block: "end" });
    }
  }, [events.length]);

  return (
    <div className="cacm-log-panel">
      <div className="cacm-log-header">Live event stream</div>
      <div className="cacm-log-body">
        {events.length === 0 && (
          <div className="cacm-log-line cacm-log-line--muted">
            Waiting for events…
          </div>
        )}
        {events.map((evt) => (
          <div key={evt.seq} className="cacm-log-line">
            <span className="cacm-log-stage">[{evt.stage}]</span>{" "}
            <span className="cacm-log-message">{evt.message}</span>
          </div>
        ))}
        <div ref={endRef} />
      </div>
    </div>
  );
}
