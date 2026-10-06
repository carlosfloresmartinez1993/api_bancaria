import { useState } from "react";
import { useSearchParams } from "react-router";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useAuth } from "../auth/AuthContext";
import { Icono } from "../components/Icono";
import { SelectorEmpresa, SelectorTerminal, SelectorUsuario } from "../components/Selectores";
import { useToast } from "../components/Toast";
import { Aviso, Boton, Campo, Cargando, EncabezadoPagina, ErrorApi, Input, Select, Tabla, Tarjeta, Td, Th, Vacio } from "../components/ui";
import { api, guardarBlob, type Query } from "../lib/api";
import { cn } from "../lib/cn";
import { dinero, entero, fecha, fechaHoraLocal, hoyISO, porcentaje, primerDiaMesISO } from "../lib/format";
import { ACCIONES_BITACORA, type Reporte } from "../lib/types";

// ------------------------------------------------------------------ catálogo
type TipoParam = "fecha" | "empresa" | "terminal" | "usuario" | "anio" | "mes" | "texto" | "accion";

interface Param {
  nombre: string;
  etiqueta: string;
  tipo: TipoParam;
  requerido?: boolean;
  /** Valor inicial al abrir el reporte. */
  inicial?: () => string;
}

interface DefReporte {
  id: string;
  titulo: string;
  descripcion: string;
  soloAdmin?: boolean;
  params: Param[];
}

const DESDE: Param = { nombre: "desde", etiqueta: "Desde", tipo: "fecha", inicial: primerDiaMesISO };
const HASTA: Param = { nombre: "hasta", etiqueta: "Hasta", tipo: "fecha", inicial: hoyISO };
const EMPRESA: Param = { nombre: "empresa_id", etiqueta: "Empresa", tipo: "empresa" };

const REPORTES: DefReporte[] = [
  { id: "saldos", titulo: "Saldos de empresas", descripcion: "Ingresos netos, salidas y saldo de cada empresa a una fecha.",
    params: [{ nombre: "al_dia", etiqueta: "Al día", tipo: "fecha", inicial: hoyISO }] },
  { id: "estado-cuenta", titulo: "Estado de cuenta", descripcion: "Ingresos y salidas de una empresa con saldo corrido.",
    params: [{ ...EMPRESA, requerido: true }, { ...DESDE, requerido: true }, { ...HASTA, requerido: true }] },
  { id: "movimientos-por-empresa", titulo: "Movimientos por empresa", descripcion: "Detalle de cada movimiento de una empresa.",
    params: [{ ...EMPRESA, requerido: true }, DESDE, HASTA] },
  { id: "movimientos-por-terminal", titulo: "Movimientos por terminal", descripcion: "Detalle de cada movimiento de una terminal.",
    params: [{ nombre: "terminal_id", etiqueta: "Terminal", tipo: "terminal", requerido: true }, DESDE, HASTA] },
  { id: "conciliacion-diaria", titulo: "Conciliación diaria", descripcion: "Totales de un día por terminal, para cuadrar contra el banco.",
    params: [{ nombre: "fecha", etiqueta: "Fecha", tipo: "fecha", requerido: true, inicial: hoyISO }, EMPRESA,
      { nombre: "terminal_id", etiqueta: "Terminal", tipo: "terminal" }] },
  { id: "salidas", titulo: "Historial de salidas", descripcion: "Salidas registradas, con búsqueda por destino.",
    params: [EMPRESA, DESDE, HASTA, { nombre: "texto", etiqueta: "Destino contiene", tipo: "texto" }] },
  { id: "totales-por-empresa", titulo: "Totales por empresa", descripcion: "Bruto, comisión y neto acumulados por empresa.", soloAdmin: true,
    params: [EMPRESA, DESDE, HASTA] },
  { id: "resumen-mensual", titulo: "Resumen mensual / anual", descripcion: "Ingresos, comisiones, salidas y flujo neto por mes.", soloAdmin: true,
    params: [{ nombre: "anio", etiqueta: "Año", tipo: "anio", requerido: true, inicial: () => hoyISO().slice(0, 4) },
      { nombre: "mes", etiqueta: "Mes", tipo: "mes" }, EMPRESA] },
  { id: "comisiones-por-terminal", titulo: "Comisiones por terminal", descripcion: "Cuánto cobró el banco en cada terminal.", soloAdmin: true,
    params: [EMPRESA, DESDE, HASTA] },
  { id: "auditoria-captura", titulo: "Auditoría de captura", descripcion: "Movimientos y correcciones de cada contador.", soloAdmin: true,
    params: [{ nombre: "usuario_id", etiqueta: "Contador", tipo: "usuario" }, DESDE, HASTA] },
  { id: "bitacora", titulo: "Bitácora de auditoría", descripcion: "Cambios registrados en el sistema (solo lectura).", soloAdmin: true,
    params: [{ nombre: "accion", etiqueta: "Acción", tipo: "accion" }, { nombre: "usuario_id", etiqueta: "Usuario", tipo: "usuario" },
      { nombre: "entidad", etiqueta: "Entidad", tipo: "texto" },
      { ...DESDE, inicial: undefined }, { ...HASTA, inicial: undefined }] },
  { id: "cierre-diario", titulo: "Cierre diario", descripcion: "Resumen del día por contador; se envía por correo a los admins.", soloAdmin: true,
    params: [{ nombre: "fecha", etiqueta: "Fecha", tipo: "fecha", inicial: hoyISO }] },
];

const MESES = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"];

const FORMATOS = [
  { valor: "xlsx", texto: "Excel" },
  { valor: "pdf", texto: "PDF" },
  { valor: "csv", texto: "CSV" },
] as const;

// ------------------------------------------------------------------ celdas
const MONTO = /^-?\d+\.\d{2}$/;
const FECHA = /^\d{4}-\d{2}-\d{2}$/;
const FECHA_HORA = /^\d{4}-\d{2}-\d{2}T/;

function celda(clave: string, valor: unknown): { texto: string; numerico: boolean; negativo?: boolean } {
  if (valor === null || valor === undefined || valor === "") return { texto: "—", numerico: false };
  if (typeof valor === "number") return { texto: entero(valor), numerico: true };
  if (typeof valor === "object") return { texto: JSON.stringify(valor), numerico: false };
  const s = String(valor);
  if (clave.includes("porcentaje")) return { texto: porcentaje(s), numerico: true };
  if (MONTO.test(s)) return { texto: dinero(s), numerico: true, negativo: s.startsWith("-") };
  if (FECHA_HORA.test(s)) return { texto: fechaHoraLocal(s), numerico: false };
  if (FECHA.test(s)) return { texto: fecha(s), numerico: false };
  return { texto: s, numerico: false };
}

function TablaReporte({ reporte }: { reporte: Reporte }) {
  if (!reporte.filas.length) return <Vacio titulo="El reporte no tiene datos" descripcion="Prueba con otro rango de fechas u otros filtros." />;
  // Una columna es numérica si alguno de sus valores lo es; así se alinea a la derecha completa.
  const numericas = new Set(
    reporte.columnas.filter((c) => reporte.filas.some((f) => celda(c.clave, f[c.clave]).numerico)).map((c) => c.clave),
  );
  return (
    <Tabla>
      <thead>
        <tr>
          {reporte.columnas.map((c) => (
            <Th key={c.clave} derecha={numericas.has(c.clave)}>{c.etiqueta}</Th>
          ))}
        </tr>
      </thead>
      <tbody className="divide-y divide-slate-100">
        {reporte.filas.map((f, i) => (
          <tr key={i} className="hover:bg-slate-50">
            {reporte.columnas.map((c) => {
              const { texto, negativo } = celda(c.clave, f[c.clave]);
              const largo = typeof f[c.clave] === "object" && f[c.clave] !== null;
              const esFecha = typeof f[c.clave] === "string" && FECHA.test((f[c.clave] as string).slice(0, 10));
              return (
                <Td key={c.clave} derecha={numericas.has(c.clave)}
                  className={cn(negativo && "text-rose-600", largo && "max-w-md font-mono text-xs break-all",
                    (esFecha || numericas.has(c.clave)) && "whitespace-nowrap")}>
                  {texto}
                </Td>
              );
            })}
          </tr>
        ))}
      </tbody>
      {reporte.totales && (
        <tfoot className="border-t-2 border-slate-200 bg-slate-50 font-semibold">
          <tr>
            {reporte.columnas.map((c, i) => {
              const v = reporte.totales?.[c.clave];
              const { texto, negativo } = v === undefined ? { texto: "", negativo: false } : celda(c.clave, v);
              return (
                <Td key={c.clave} derecha={numericas.has(c.clave)} className={cn("text-slate-900", negativo && "text-rose-600")}>
                  {i === 0 && v === undefined ? "Total" : texto}
                </Td>
              );
            })}
          </tr>
        </tfoot>
      )}
    </Tabla>
  );
}

// ------------------------------------------------------------------ parámetros
function ControlParam({ p, valor, valores, onCambiar }: {
  p: Param;
  valor: string;
  valores: Record<string, string>;
  onCambiar: (v: string) => void;
}) {
  return (
    <Campo etiqueta={p.etiqueta} requerido={p.requerido}>
      {(id) => {
        switch (p.tipo) {
          case "fecha":
            return <Input id={id} type="date" value={valor} onChange={(e) => onCambiar(e.target.value)} />;
          case "empresa":
            return <SelectorEmpresa id={id} valor={valor} onCambiar={onCambiar} vacio={p.requerido ? undefined : "Todas"} />;
          case "terminal":
            return <SelectorTerminal id={id} valor={valor} onCambiar={onCambiar} empresaId={valores.empresa_id}
              vacio={p.requerido ? undefined : "Todas"} />;
          case "usuario":
            return <SelectorUsuario id={id} valor={valor} onCambiar={onCambiar} vacio="Todos" />;
          case "anio":
            return <Input id={id} type="number" min={2000} max={2100} value={valor} onChange={(e) => onCambiar(e.target.value)} />;
          case "mes":
            return (
              <Select id={id} value={valor} onChange={(e) => onCambiar(e.target.value)}>
                <option value="">Todo el año</option>
                {MESES.map((m, i) => <option key={m} value={i + 1}>{m}</option>)}
              </Select>
            );
          case "accion":
            return (
              <Select id={id} value={valor} onChange={(e) => onCambiar(e.target.value)}>
                <option value="">Todas</option>
                {ACCIONES_BITACORA.map((a) => <option key={a} value={a}>{a.replaceAll("_", " ").toLowerCase()}</option>)}
              </Select>
            );
          case "texto":
            return <Input id={id} maxLength={100} value={valor} onChange={(e) => onCambiar(e.target.value)} />;
        }
      }}
    </Campo>
  );
}

function valoresIniciales(def: DefReporte, url: URLSearchParams): Record<string, string> {
  return Object.fromEntries(def.params.map((p) => [p.nombre, url.get(p.nombre) ?? p.inicial?.() ?? ""]));
}

function EnviarCierre({ dia }: { dia: string }) {
  const avisar = useToast();
  const [enviando, setEnviando] = useState(false);
  const [resultado, setResultado] = useState<{ estado: string; detalle?: { error?: string } } | null>(null);

  async function enviar(forzar: boolean) {
    setEnviando(true);
    setResultado(null);
    try {
      const r = await api.post<{ estado: string; detalle?: { error?: string } }>("/reportes/cierre-diario/enviar", undefined, { fecha: dia || undefined, forzar });
      setResultado(r);
      if (r.estado === "enviado") avisar("Cierre enviado por correo");
    } catch (e) {
      avisar((e as Error).message, "error");
    } finally {
      setEnviando(false);
    }
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-2">
        <Boton variante="secundario" cargando={enviando} onClick={() => enviar(false)}>
          <Icono nombre="correo" className="size-4" /> Enviar por correo
        </Boton>
        {resultado?.estado === "ya_enviado" && (
          <Boton variante="secundario" cargando={enviando} onClick={() => enviar(true)}>Reenviar de todos modos</Boton>
        )}
      </div>
      {resultado?.estado === "ya_enviado" && <Aviso tono="info">El cierre de ese día ya se había enviado.</Aviso>}
      {resultado?.estado === "en_proceso" && <Aviso tono="aviso">Otro proceso está enviando el cierre en este momento.</Aviso>}
      {resultado?.estado === "error" && <Aviso tono="peligro" titulo="No se pudo enviar">{resultado.detalle?.error}</Aviso>}
    </div>
  );
}

// ------------------------------------------------------------------ página
export default function Reportes() {
  const { esAdmin } = useAuth();
  const avisar = useToast();
  const [url, setUrl] = useSearchParams();
  const disponibles = REPORTES.filter((r) => esAdmin || !r.soloAdmin);
  const def = disponibles.find((r) => r.id === url.get("r")) ?? disponibles[0];

  const [valores, setValores] = useState(() => valoresIniciales(def, url));
  const [defActual, setDefActual] = useState(def.id);
  const [descargando, setDescargando] = useState<string | null>(null);

  // Al cambiar de reporte se reinician los parámetros (patrón "ajustar estado durante el render").
  if (defActual !== def.id) {
    setDefActual(def.id);
    setValores(valoresIniciales(def, new URLSearchParams()));
  }

  const faltan = def.params.filter((p) => p.requerido && !valores[p.nombre]);
  const query: Query = { ...valores };

  const reporte = useQuery({
    queryKey: ["reporte", def.id, valores],
    queryFn: () => api.get<Reporte>(`/reportes/${def.id}`, query),
    enabled: faltan.length === 0,
    placeholderData: keepPreviousData,
  });

  function elegir(id: string) {
    setUrl({ r: id }, { replace: true });
  }

  async function descargar(formato: string) {
    setDescargando(formato);
    try {
      const blob = await api.blob(`/reportes/${def.id}`, { ...query, formato });
      guardarBlob(blob, `${def.id}-${hoyISO()}.${formato}`);
    } catch (e) {
      avisar((e as Error).message, "error");
    } finally {
      setDescargando(null);
    }
  }

  return (
    <>
      <EncabezadoPagina titulo="Reportes" descripcion="Consulta en pantalla o descarga en Excel, PDF o CSV." />

      <div className="grid gap-6 lg:grid-cols-[16rem_1fr]">
        <nav className="flex gap-2 overflow-x-auto pb-1 lg:flex-col lg:gap-1 lg:overflow-visible">
          {disponibles.map((r) => (
            <button
              key={r.id}
              type="button"
              onClick={() => elegir(r.id)}
              className={cn(
                "shrink-0 rounded-lg px-3 py-2 text-left text-sm transition-colors",
                r.id === def.id ? "bg-teal-50 font-medium text-teal-800 ring-1 ring-teal-200" : "text-slate-600 hover:bg-white hover:text-slate-900",
              )}
            >
              {r.titulo}
              {r.soloAdmin && <span className="ml-1.5 text-[10px] uppercase tracking-wide text-slate-400">admin</span>}
            </button>
          ))}
        </nav>

        <div className="min-w-0 space-y-4">
          <Tarjeta className="p-5">
            <h2 className="text-base font-semibold text-slate-900">{def.titulo}</h2>
            <p className="mt-0.5 text-sm text-slate-500">{def.descripcion}</p>
            <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
              {def.params.map((p) => (
                <ControlParam key={p.nombre} p={p} valor={valores[p.nombre] ?? ""} valores={valores}
                  onCambiar={(v) => setValores((s) => ({ ...s, [p.nombre]: v, ...(p.tipo === "empresa" && "terminal_id" in s ? { terminal_id: "" } : {}) }))} />
              ))}
            </div>
            <div className="mt-4 flex flex-wrap items-center justify-between gap-3 border-t border-slate-100 pt-4">
              <div className="flex flex-wrap gap-2">
                {FORMATOS.map((f) => (
                  <Boton key={f.valor} variante="secundario" tamano="sm" disabled={faltan.length > 0}
                    cargando={descargando === f.valor} onClick={() => descargar(f.valor)}>
                    <Icono nombre="descargar" className="size-4" /> {f.texto}
                  </Boton>
                ))}
              </div>
              {def.id === "cierre-diario" && <EnviarCierre dia={valores.fecha} />}
            </div>
          </Tarjeta>

          {faltan.length > 0 ? (
            <Aviso tono="info">Completa: {faltan.map((p) => p.etiqueta.toLowerCase()).join(", ")}.</Aviso>
          ) : (
            <>
              <ErrorApi error={reporte.error} />
              <Tarjeta className={cn(reporte.isFetching && !reporte.isLoading && "opacity-70 transition-opacity")}>
                {reporte.isLoading ? <Cargando texto="Generando reporte…" /> : reporte.data && (
                  <>
                    <div className="px-5 py-4">
                      <h3 className="text-sm font-semibold text-slate-900">{reporte.data.titulo}</h3>
                      <p className="text-xs text-slate-500">{reporte.data.filas.length} fila(s)</p>
                    </div>
                    <TablaReporte reporte={reporte.data} />
                  </>
                )}
              </Tarjeta>
            </>
          )}
        </div>
      </div>
    </>
  );
}
