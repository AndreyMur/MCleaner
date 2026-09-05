import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";

export type ToastKind = "success" | "error" | "info";

export interface ToastItem {
  id: number;
  kind: ToastKind;
  message: string;
  leaving: boolean;
}

interface ToastContextValue {
  toasts: ToastItem[];
  push: (kind: ToastKind, message: string) => void;
  dismiss: (id: number) => void;
}

const TOAST_DURATION = 4000;
const TOAST_EXIT = 180;

const ToastContext = createContext<ToastContextValue | null>(null);

export const ToastProvider = ({ children }: { children: ReactNode }) => {
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const nextId = useRef(1);

  const dismiss = useCallback((id: number) => {
    setToasts((prev) => {
      const toast = prev.find((item) => item.id === id);
      if (!toast || toast.leaving) return prev;
      return prev.map((item) =>
        item.id === id ? { ...item, leaving: true } : item
      );
    });
    window.setTimeout(() => {
      setToasts((prev) => prev.filter((toast) => toast.id !== id));
    }, TOAST_EXIT);
  }, []);

  const push = useCallback(
    (kind: ToastKind, message: string) => {
      const id = nextId.current++;
      setToasts((prev) => [
        ...prev.slice(-4),
        { id, kind, message, leaving: false },
      ]);
      window.setTimeout(() => dismiss(id), TOAST_DURATION);
    },
    [dismiss]
  );

  const value = useMemo(
    () => ({ toasts, push, dismiss }),
    [toasts, push, dismiss]
  );

  return <ToastContext.Provider value={value}>{children}</ToastContext.Provider>;
};

export const useToast = (): ToastContextValue => {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error("useToast must be used within a ToastProvider");
  }
  return context;
};
