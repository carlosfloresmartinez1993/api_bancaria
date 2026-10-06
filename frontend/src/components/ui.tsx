import {
  useEffect,
  useId,
  type ButtonHTMLAttributes,
  type InputHTMLAttributes,
  type ReactNode,
  type SelectHTMLAttributes,
  type TextareaHTMLAttributes,
} from "react";
import { cn } from "../lib/cn";

// ------------------------------------------------------------------ botones
type Variante = "primario" | "secundario" | "peligro" | "fantasma";

const VARIANTES: Record<Variante, string> = {
  primario: "bg-teal-700 text-white hover:bg-teal-800 focus-visible:outline-teal-700 shadow-sm",
  secundario:
    "bg-white text-slate-700 ring-1 ring-inset ring-slate-300 hover:bg-slate-50 focus-visible:outline-slate-400 shadow-sm",
  peligro: "bg-rose-600 text-white hover:bg-rose-700 focus-visible:outline-rose-600 shadow-sm",
  fantasma: "text-slate-600 hover:bg-slate-100 hover:text-slate-900 focus-visible:outline-slate-400",
};

interface BotonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variante?: Variante;
  tamano?: "sm" | "md";
  cargando?: boolean;
}

export function Boton({
  variante = "primario",
  tamano = "md",
  cargando = false,
  disabled,
  className,
  children,
  type = "button",
  ...props
}: BotonProps) {
  return (
    <button
      type={type}
      disabled={disabled || cargando}
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-lg font-medium transition-colors",
        "focus-visible:outline-2 focus-visible:outline-offset-2 disabled:cursor-not-allowed disabled:opacity-60",
        tamano === "sm" ? "px-2.5 py-1.5 text-xs" : "px-3.5 py-2 text-sm",
        VARIANTES[variante],
        className,
      )}
      {...props}
    >
      {cargando && <Spinner className="size-4" />}
      {children}
    </button>
  );
}

// ------------------------------------------------------------------ campos
const CAMPO =
  "block w-full rounded-lg border-0 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm ring-1 ring-inset " +
  "ring-slate-300 placeholder:text-slate-400 focus:ring-2 focus:ring-inset focus:ring-teal-600 " +
  "disabled:bg-slate-50 disabled:text-slate-500";

export function Input({ className, ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return <input className={cn(CAMPO, className)} {...props} />;
}

export function Textarea({ className, ...props }: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea rows={3} className={cn(CAMPO, className)} {...props} />;
}

export function Select({ className, children, ...props }: SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select className={cn(CAMPO, "pr-8", className)} {...props}>
      {children}
    </select>
  );
}

interface CampoProps {
  etiqueta: string;
  ayuda?: ReactNode;
  requerido?: boolean;
  className?: string;
  children: (id: string) => ReactNode;
}

/** Envuelve un control con su etiqueta; `children` recibe el id para enlazarlos. */
export function Campo({ etiqueta, ayuda, requerido, className, children }: CampoProps) {
  const id = useId();
  return (
    <div className={className}>
      <label htmlFor={id} className="mb-1 block text-sm font-medium text-slate-700">
        {etiqueta}
        {requerido && <span className="ml-0.5 text-rose-600">*</span>}
      </label>
      {children(id)}
      {ayuda && <p className="mt-1 text-xs text-slate-500">{ayuda}</p>}
    </div>
  );
}

// ------------------------------------------------------------------ estructura
export function Tarjeta({ className, children }: { className?: string; children: ReactNode }) {
  return <div className={cn("rounded-xl bg-white shadow-sm ring-1 ring-slate-200", className)}>{children}</div>;
}

export function EncabezadoPagina({
  titulo,
  descripcion,
  acciones,
}: {
  titulo: ReactNode;
  descripcion?: ReactNode;
  acciones?: ReactNode;
}) {
  return (
    <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
      <div className="min-w-0">
        <h1 className="text-2xl font-semibold tracking-tight text-slate-900">{titulo}</h1>
        {descripcion && <p className="mt-1 text-sm text-slate-500">{descripcion}</p>}
      </div>
      {acciones && <div className="flex shrink-0 flex-wrap gap-2">{acciones}</div>}
    </div>
  );
}

type Tono = "neutro" | "exito" | "aviso" | "peligro" | "info";

const TONOS_INSIGNIA: Record<Tono, string> = {
  neutro: "bg-slate-100 text-slate-700 ring-slate-500/20",
  exito: "bg-emerald-50 text-emerald-700 ring-emerald-600/20",
  aviso: "bg-amber-50 text-amber-800 ring-amber-600/20",
  peligro: "bg-rose-50 text-rose-700 ring-rose-600/20",
  info: "bg-sky-50 text-sky-700 ring-sky-600/20",
};

export function Insignia({ tono = "neutro", children }: { tono?: Tono; children: ReactNode }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium ring-1 ring-inset",
        TONOS_INSIGNIA[tono],
      )}
    >
      {children}
    </span>
  );
}

const TONOS_AVISO: Record<Exclude<Tono, "neutro">, string> = {
  exito: "bg-emerald-50 text-emerald-800 ring-emerald-200",
  aviso: "bg-amber-50 text-amber-900 ring-amber-200",
  peligro: "bg-rose-50 text-rose-800 ring-rose-200",
  info: "bg-sky-50 text-sky-800 ring-sky-200",
};

export function Aviso({
  tono = "info",
  titulo,
  children,
  className,
}: {
  tono?: Exclude<Tono, "neutro">;
  titulo?: ReactNode;
  children?: ReactNode;
  className?: string;
}) {
  return (
    <div role={tono === "peligro" ? "alert" : "status"} className={cn("rounded-lg p-3 text-sm ring-1", TONOS_AVISO[tono], className)}>
      {titulo && <p className="font-medium">{titulo}</p>}
      {children && <div className={titulo ? "mt-1" : undefined}>{children}</div>}
    </div>
  );
}

export function ErrorApi({ error, className }: { error: unknown; className?: string }) {
  if (!error) return null;
  const mensaje = error instanceof Error ? error.message : "Ocurrió un error";
  return (
    <Aviso tono="peligro" className={className}>
      {mensaje}
    </Aviso>
  );
}

export function Spinner({ className }: { className?: string }) {
  return (
    <svg className={cn("animate-spin", className ?? "size-5")} viewBox="0 0 24 24" fill="none" aria-hidden>
      <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" className="opacity-25" />
      <path d="M22 12a10 10 0 0 1-10 10" stroke="currentColor" strokeWidth="4" className="opacity-75" />
    </svg>
  );
}

export function Cargando({ texto = "Cargando…" }: { texto?: string }) {
  return (
    <div className="flex items-center justify-center gap-3 py-12 text-sm text-slate-500">
      <Spinner />
      {texto}
    </div>
  );
}

export function Vacio({ titulo, descripcion, accion }: { titulo: string; descripcion?: string; accion?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center px-6 py-12 text-center">
      <div className="mb-3 rounded-full bg-slate-100 p-3 text-slate-400">
        <svg className="size-6" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
          <path d="M3 7.5 12 3l9 4.5M4.5 9v8.25M19.5 9v8.25M9 9v8.25M15 9v8.25M3 20.25h18" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </div>
      <p className="text-sm font-medium text-slate-900">{titulo}</p>
      {descripcion && <p className="mt-1 max-w-sm text-sm text-slate-500">{descripcion}</p>}
      {accion && <div className="mt-4">{accion}</div>}
    </div>
  );
}

// ------------------------------------------------------------------ tablas
export function Tabla({ children }: { children: ReactNode }) {
  return (
    <div className="overflow-x-auto">
      <table className="min-w-full divide-y divide-slate-200 text-sm">{children}</table>
    </div>
  );
}

export function Th({ children, derecha, className }: { children?: ReactNode; derecha?: boolean; className?: string }) {
  return (
    <th
      scope="col"
      className={cn(
        "whitespace-nowrap bg-slate-50 px-4 py-2.5 text-xs font-semibold uppercase tracking-wide text-slate-500",
        derecha ? "text-right" : "text-left",
        className,
      )}
    >
      {children}
    </th>
  );
}

export function Td({ children, derecha, className }: { children?: ReactNode; derecha?: boolean; className?: string }) {
  return (
    <td className={cn("px-4 py-3 text-slate-700", derecha && "text-right tabular-nums", className)}>{children}</td>
  );
}

export function Paginacion({
  total,
  limit,
  offset,
  onCambiar,
}: {
  total: number;
  limit: number;
  offset: number;
  onCambiar: (offset: number) => void;
}) {
  if (total <= limit) {
    return total > 0 ? (
      <div className="border-t border-slate-200 px-4 py-3 text-xs text-slate-500">{total} registro(s)</div>
    ) : null;
  }
  const desde = offset + 1;
  const hasta = Math.min(offset + limit, total);
  return (
    <div className="flex items-center justify-between border-t border-slate-200 px-4 py-3">
      <p className="text-xs text-slate-500">
        {desde}–{hasta} de {total}
      </p>
      <div className="flex gap-2">
        <Boton variante="secundario" tamano="sm" disabled={offset === 0} onClick={() => onCambiar(Math.max(0, offset - limit))}>
          Anterior
        </Boton>
        <Boton variante="secundario" tamano="sm" disabled={hasta >= total} onClick={() => onCambiar(offset + limit)}>
          Siguiente
        </Boton>
      </div>
    </div>
  );
}

// ------------------------------------------------------------------ modal
export function Modal({
  abierto,
  titulo,
  descripcion,
  onCerrar,
  children,
  ancho = "md",
}: {
  abierto: boolean;
  titulo: ReactNode;
  descripcion?: ReactNode;
  onCerrar: () => void;
  children: ReactNode;
  ancho?: "md" | "lg" | "xl";
}) {
  useEffect(() => {
    if (!abierto) return;
    const alTeclear = (e: KeyboardEvent) => e.key === "Escape" && onCerrar();
    document.addEventListener("keydown", alTeclear);
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", alTeclear);
      document.body.style.overflow = "";
    };
  }, [abierto, onCerrar]);

  if (!abierto) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center p-4 sm:items-center" role="dialog" aria-modal="true">
      <div className="absolute inset-0 bg-slate-900/40 backdrop-blur-[1px]" onClick={onCerrar} />
      <div
        className={cn(
          "relative max-h-[90vh] w-full overflow-y-auto rounded-xl bg-white shadow-xl ring-1 ring-slate-200",
          { md: "max-w-lg", lg: "max-w-2xl", xl: "max-w-4xl" }[ancho],
        )}
      >
        <div className="flex items-start justify-between gap-4 border-b border-slate-200 px-5 py-4">
          <div>
            <h2 className="text-base font-semibold text-slate-900">{titulo}</h2>
            {descripcion && <p className="mt-0.5 text-sm text-slate-500">{descripcion}</p>}
          </div>
          <button
            type="button"
            onClick={onCerrar}
            className="rounded-md p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600"
            aria-label="Cerrar"
          >
            <svg className="size-5" viewBox="0 0 20 20" fill="currentColor">
              <path d="M6.28 5.22a.75.75 0 0 0-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 1 0 1.06 1.06L10 11.06l3.72 3.72a.75.75 0 1 0 1.06-1.06L11.06 10l3.72-3.72a.75.75 0 0 0-1.06-1.06L10 8.94 6.28 5.22Z" />
            </svg>
          </button>
        </div>
        <div className="px-5 py-4">{children}</div>
      </div>
    </div>
  );
}

export function PieModal({ children }: { children: ReactNode }) {
  return <div className="-mx-5 -mb-4 mt-5 flex justify-end gap-2 border-t border-slate-200 bg-slate-50 px-5 py-3">{children}</div>;
}

// ------------------------------------------------------------------ montos
export function Monto({ valor, resaltarNegativo = false }: { valor: string | number | null | undefined; resaltarNegativo?: boolean }) {
  const negativo = Number(valor ?? 0) < 0;
  const texto = valor === null || valor === undefined || valor === ""
    ? "—"
    : new Intl.NumberFormat("es-MX", { style: "currency", currency: "MXN" }).format(Number(valor));
  return <span className={cn("tabular-nums", resaltarNegativo && negativo && "font-medium text-rose-600")}>{texto}</span>;
}

// ------------------------------------------------------------------ iniciales
/** Cuadro con las iniciales de un nombre (p. ej. "Mariscos El Güero" → "MG"). */
export function Iniciales({ nombre, className }: { nombre: string; className?: string }) {
  const palabras = nombre.split(/\s+/).filter((p) => p.length > 2);
  const iniciales = (palabras.slice(0, 2).map((p) => p[0]).join("") || nombre.slice(0, 2)).toUpperCase();
  return (
    <div className={cn("flex shrink-0 items-center justify-center rounded-lg bg-teal-50 ring-1 ring-teal-100", className ?? "size-10")}>
      <span className="text-sm font-semibold text-teal-700">{iniciales}</span>
    </div>
  );
}
