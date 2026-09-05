import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";

export type LogKind = "cmd" | "ok" | "err" | "info";

export interface LogEntry {
  id: number;
  kind: LogKind;
  text: string;
}

interface JournalContextValue {
  entries: LogEntry[];
  running: boolean;
  runningLabel: string | null;
  append: (text: string, kind?: LogKind) => void;
  clear: () => void;
  setRunning: (label: string | null) => void;
}

const MAX_ENTRIES = 100;

const JournalContext = createContext<JournalContextValue | null>(null);

export const JournalProvider = ({ children }: { children: ReactNode }) => {
  const [entries, setEntries] = useState<LogEntry[]>([]);
  const [running, setRunning] = useState(false);
  const [runningLabel, setRunningLabel] = useState<string | null>(null);
  const nextId = useRef(1);

  const append = useCallback((text: string, kind: LogKind = "info") => {
    setEntries((prev) => {
      const entry: LogEntry = { id: nextId.current++, kind, text };
      const next = [...prev, entry];
      return next.length > MAX_ENTRIES ? next.slice(next.length - MAX_ENTRIES) : next;
    });
  }, []);

  const clear = useCallback(() => setEntries([]), []);

  const updateRunning = useCallback((label: string | null) => {
    setRunning(label !== null);
    setRunningLabel(label);
  }, []);

  const value = useMemo(
    () => ({
      entries,
      running,
      runningLabel,
      append,
      clear,
      setRunning: updateRunning,
    }),
    [entries, running, runningLabel, append, clear, updateRunning]
  );

  return <JournalContext.Provider value={value}>{children}</JournalContext.Provider>;
};

export const useJournal = (): JournalContextValue => {
  const context = useContext(JournalContext);
  if (!context) {
    throw new Error("useJournal must be used within a JournalProvider");
  }
  return context;
};
