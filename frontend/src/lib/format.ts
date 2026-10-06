const moneda = new Intl.NumberFormat("es-MX", { style: "currency", currency: "MXN" });
const numero = new Intl.NumberFormat("es-MX");
const fechaCorta = new Intl.DateTimeFormat("es-MX", { day: "2-digit", month: "short", year: "numeric" });
const fechaHora = new Intl.DateTimeFormat("es-MX", {
  day: "2-digit",
  month: "short",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
});

export function dinero(valor: string | number | null | undefined): string {
  if (valor === null || valor === undefined || valor === "") return "—";
  const n = typeof valor === "number" ? valor : Number(valor);
  return Number.isFinite(n) ? moneda.format(n) : String(valor);
}

export function porcentaje(valor: string | number | null | undefined): string {
  if (valor === null || valor === undefined || valor === "") return "—";
  return `${Number(valor).toFixed(2)} %`;
}

export function entero(valor: number | string): string {
  return numero.format(Number(valor));
}

/** "2026-10-05" → "05 oct 2026" (sin desfase de zona horaria). */
export function fecha(valor: string | null | undefined): string {
  if (!valor) return "—";
  const [a, m, d] = valor.slice(0, 10).split("-").map(Number);
  return fechaCorta.format(new Date(a, m - 1, d));
}

export function fechaHoraLocal(valor: string | null | undefined): string {
  if (!valor) return "—";
  return fechaHora.format(new Date(valor));
}

/** Fecha de hoy en formato AAAA-MM-DD según el reloj del navegador. */
export function hoyISO(): string {
  const d = new Date();
  const p = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}

export function primerDiaMesISO(): string {
  return `${hoyISO().slice(0, 8)}01`;
}

export function esNegativo(valor: string | number | null | undefined): boolean {
  return Number(valor ?? 0) < 0;
}
