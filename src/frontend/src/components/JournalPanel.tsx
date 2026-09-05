import { useEffect, useRef, useState } from "react";
import { useJournal } from "../context/JournalContext";

const JournalPanel = () => {
  const { entries, running, runningLabel, clear, setRunning } = useJournal();
  const [open, setOpen] = useState(true);
  const logRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = logRef.current;
    if (el) {
      el.scrollTop = el.scrollHeight;
    }
  }, [entries, open]);

  const handleClear = () => {
    setRunning(null);
    clear();
  };

  return (
    <section className={`journal ${open ? "" : "journal-collapsed"}`} data-testid="journal">
      <header className="journal-header">
        <button
          className="journal-toggle"
          onClick={() => setOpen((value) => !value)}
          aria-expanded={open}
        >
          <span className="journal-toggle-icon">{open ? "▾" : "▸"}</span>
          <span className="journal-title">Journal</span>
          {entries.length > 0 && (
            <span className="journal-count" aria-label="Log entries">
              {entries.length}
            </span>
          )}
        </button>
        <div className="journal-toolbar">
          {running && (
            <span className="operation-spinner" data-testid="journal-running">
              {runningLabel || "Running…"}
            </span>
          )}
          {entries.length > 0 && (
            <button className="journal-clear" onClick={handleClear}>
              Clear
            </button>
          )}
        </div>
      </header>
      {open && (
        <div className="operation-log" ref={logRef} data-testid="journal-log">
          {entries.length === 0 ? (
            <p className="log-placeholder">Operations will be shown here.</p>
          ) : (
            entries.map((entry) => (
              <div className={`log-line log-${entry.kind}`} key={entry.id}>
                {entry.text}
              </div>
            ))
          )}
        </div>
      )}
    </section>
  );
};

export default JournalPanel;
