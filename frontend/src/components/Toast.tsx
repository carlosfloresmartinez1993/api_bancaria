import { createContext, use, useCallback, useState, type ReactNode } from "react";
import { cn } from "../lib/cn";

type Tipo = "exito" | "error" | "aviso";
interface Toast {
  id: number;
  tipo: Tipo;
  mensaje: string;
}

const ToastContext = createContext<((mensaje: string, tipo?: Tipo) => void) | null>(null);

let siguienteId = 1;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const avisar = useCallback((mensaje: string, tipo: Tipo = "exito") => {
    const id = siguienteId++;
    setToasts((t) => [...t, { id, tipo, mensaje }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), tipo === "exito" ? 3500 : 7000);
  }, []);

  return (
    <ToastContext value={avisar}>
      {children}
      <div className="pointer-events-none fixed inset-x-0 bottom-4 z-[60] flex flex-col items-center gap-2 px-4 sm:items-end sm:pr-6">
        {toasts.map((t) => (
          <div
            key={t.id}
            role="status"
            className={cn(
              "pointer-events-auto w-full max-w-sm rounded-lg px-4 py-3 text-sm shadow-lg ring-1",
              t.tipo === "exito" && "bg-slate-900 text-white ring-slate-900",
              t.tipo === "error" && "bg-rose-600 text-white ring-rose-700",
              t.tipo === "aviso" && "bg-amber-50 text-amber-900 ring-amber-300",
            )}
          >
            {t.mensaje}
          </div>
        ))}
      </div>
    </ToastContext>
  );
}

export function useToast() {
  const ctx = use(ToastContext);
  if (!ctx) throw new Error("useToast debe usarse dentro de <ToastProvider>");
  return ctx;
}
