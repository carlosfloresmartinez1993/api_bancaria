import { useState, type ReactNode } from "react";
import { useSearchParams } from "react-router";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useAuth } from "../auth/AuthContext";
import { Icono } from "../components/Icono";
import { SelectorEmpresa, SelectorMetodoPago, SelectorUsuario } from "../components/Selectores";
import { useToast } from "../components/Toast";
import { Aviso, Boton, Campo, Cargando, EncabezadoPagina, ErrorApi, Input, Select, Tabla, Tarjeta, Td, Th, Vacio } from "../components/ui";
import { api, guardarBlob, type Query } from "../lib/api";
import { cn } from "../lib/cn";
import { dinero, entero, fecha, fechaHoraLocal, hoyISO, porcentaje, primerDiaMesISO } from "../lib/format";
import { filtroEmpresa } from "../lib/empresa";
import { useProyectosCatalogo, useTerminalesCatalogo } from "../lib/queries";
import { ACCIONES_BITACORA, type Reporte } from "../lib/types";

// ------------------------------------------------------------------ catálogo
type TipoParam = "fecha" | "usuario" | "anio" | "mes" | "texto" | "accion" | "empresa" | "metodo"
  | "contenido" | "agrupar" | "factura";

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
  /** Muestra la selección de clientes y proyectos de la empresa elegida. */
  alcance?: boolean;
}

const DESDE: Param = { nombre: "desde", etiqueta: "Desde", tipo: "fecha", inicial: primerDiaMesISO };
const HASTA: Param = { nombre: "hasta", etiqueta: "Hasta", tipo: "fecha", inicial: hoyISO };
const EMPRESA: Param = { nombre: "empresa_id", etiqueta: "Empresa", tipo: "empresa" };

const REPORTES: DefReporte[] = [
  { id: "constructor", titulo: "Constructor de reportes",
    descripcion: "Elige la empresa, sus clientes y proyectos, y cómo agrupar las entradas y salidas.", alcance: true,
    params: [EMPRESA, DESDE, HASTA,
      { nombre: "contenido", etiqueta: "Mostrar", tipo: "contenido", inicial: () => "ambos" },
      { nombre: "agrupar", etiqueta: "Agrupar por", tipo: "agrupar", inicial: () => "proyecto" },
      { nombre: "metodo_pago_id", etiqueta: "Método de pago", tipo: "metodo" },
      { nombre: "requiere_factura", etiqueta: "Factura", tipo: "factura" },
      { nombre: "texto", etiqueta: "Buscar en destino / observaciones", tipo: "texto" }] },
  { id: "saldos", titulo: "Saldos de empresas", descripcion: "Entradas, comisiones, salidas y saldo de cada empresa a una fecha.",
    params: [{ nombre: "al_dia", etiqueta: "Al día", tipo: "fecha", inicial: hoyISO }] },
  { id: "estado-cuenta", titulo: "Estado de cuenta", descripcion: "Entradas y salidas en orden con saldo corrido.", alcance: true,
    params: [{ ...EMPRESA, requerido: true }, { ...DESDE, requerido: true }, { ...HASTA, requerido: true },
      { nombre: "metodo_pago_id", etiqueta: "Método de pago", tipo: "metodo" }] },
  { id: "conciliacion-diaria", titulo: "Conciliación diaria", descripcion: "Totales de un día por cliente y proyecto, para cuadrar contra el banco.",
    alcance: true,
    params: [{ nombre: "fecha", etiqueta: "Fecha", tipo: "fecha", requerido: true, inicial: hoyISO }, EMPRESA] },
  { id: "resumen-mensual", titulo: "Resumen mensual / anual", descripcion: "Entradas, comisiones, salidas y flujo neto por mes.", soloAdmin: true,
    params: [{ nombre: "anio", etiqueta: "Año", tipo: "anio", requerido: true, inicial: () => hoyISO().slice(0, 4) },
      { nombre: "mes", etiqueta: "Mes", tipo: "mes" }, EMPRESA] },
  { id: "auditoria-captura", titulo: "Auditoría de captura", descripcion: "Entradas y correcciones de cada contador.", soloAdmin: true,
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
                <Td key={c.clave} derecha={numericas.has(c.clave)}
                  className={cn("whitespace-nowrap text-slate-900", negativo && "text-rose-600")}>
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
type Valores = Record<string, string | string[]>;

function ControlParam({ p, valor, onCambiar }: { p: Param; valor: string; onCambiar: (v: string) => void }) {
  return (
    <Campo etiqueta={p.etiqueta} requerido={p.requerido}>
      {(id) => {
        switch (p.tipo) {
          case "fecha":
            return <Input id={id} type="date" value={valor} onChange={(e) => onCambiar(e.target.value)} />;
          case "empresa":
            return <SelectorEmpresa id={id} valor={valor} onCambiar={onCambiar} conSinEmpresa vacio={p.requerido ? undefined : "Todas"} />;
          case "usuario":
            return <SelectorUsuario id={id} valor={valor} onCambiar={onCambiar} vacio="Todos" />;
          case "metodo":
            return <SelectorMetodoPago id={id} valor={valor} onCambiar={onCambiar} vacio="Todos" />;
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
          case "contenido":
            return (
              <Select id={id} value={valor} onChange={(e) => onCambiar(e.target.value)}>
                <option value="ambos">Entradas y salidas</option>
                <option value="entradas">Solo entradas</option>
                <option value="salidas">Solo salidas</option>
              </Select>
            );
          case "agrupar":
            return (
              <Select id={id} value={valor} onChange={(e) => onCambiar(e.target.value)}>
                <option value="empresa">Empresa</option>
                <option value="cliente">Cliente</option>
                <option value="proyecto">Proyecto</option>
                <option value="metodo_pago">Método de pago</option>
                <option value="detalle">Sin agrupar (detalle)</option>
              </Select>
            );
          case "factura":
            return (
              <Select id={id} value={valor} onChange={(e) => onCambiar(e.target.value)}>
                <option value="">Todas</option>
                <option value="true">Solo con factura</option>
                <option value="false">Solo sin factura</option>
              </Select>
            );
          case "texto":
            return <Input id={id} maxLength={100} value={valor} onChange={(e) => onCambiar(e.target.value)} />;
        }
      }}
    </Campo>
  );
}

/** Lista de casillas con opción "Todos". Lista vacía = todos. */
function Casillas({ titulo, opciones, elegidos, onCambiar, vacio }: {
  titulo: string;
  opciones: { id: string; texto: ReactNode }[];
  elegidos: string[];
  onCambiar: (ids: string[]) => void;
  vacio: string;
}) {
  const todos = elegidos.length === 0;
  const alternar = (id: string) =>
    onCambiar(elegidos.includes(id) ? elegidos.filter((x) => x !== id) : [...elegidos, id]);
  return (
    <fieldset className="min-w-0">
      <legend className="mb-1 text-sm font-medium text-slate-700">{titulo}</legend>
      <div className="max-h-52 overflow-y-auto rounded-lg p-2 ring-1 ring-slate-200">
        {opciones.length === 0 ? (
          <p className="px-1 py-2 text-xs text-slate-500">{vacio}</p>
        ) : (
          <>
            <label className="flex cursor-pointer items-center gap-2 rounded px-1 py-1 text-sm font-medium hover:bg-slate-50">
              <input type="checkbox" className="size-4 accent-teal-700" checked={todos} onChange={() => onCambiar([])} />
              Todos
            </label>
            {opciones.map((o) => (
              <label key={o.id} className="flex cursor-pointer items-center gap-2 rounded px-1 py-1 text-sm hover:bg-slate-50">
                <input type="checkbox" className="size-4 accent-teal-700" checked={!todos && elegidos.includes(o.id)}
                  onChange={() => alternar(o.id)} />
                {o.texto}
              </label>
            ))}
          </>
        )}
      </div>
    </fieldset>
  );
}

/** Clientes y proyectos de la empresa elegida. Si se eligen clientes, solo se ofrecen sus proyectos. */
function SelectorAlcance({ empresaId, clientes, proyectos, onCambiar }: {
  empresaId: string;
  clientes: string[];
  proyectos: string[];
  onCambiar: (c: { clientes: string[]; proyectos: string[] }) => void;
}) {
  const { data: listaClientes } = useTerminalesCatalogo(empresaId || undefined);
  const { data: listaProyectos } = useProyectosCatalogo({ empresaId: empresaId || undefined });
  if (!empresaId) {
    return <p className="text-sm text-slate-500 sm:col-span-2">Elige una empresa para seleccionar sus clientes y proyectos.</p>;
  }
  const nombreCliente = new Map((listaClientes ?? []).map((c) => [c.id, c.identificador_terminal]));
  const visibles = (listaProyectos ?? []).filter((p) => clientes.length === 0 || clientes.includes(p.terminal_id));
  return (
    <>
      <Casillas titulo="Clientes" vacio="La empresa no tiene clientes." elegidos={clientes}
        opciones={(listaClientes ?? []).map((c) => ({ id: c.id, texto: c.identificador_terminal }))}
        onCambiar={(ids) => onCambiar({
          clientes: ids,
          // Al cambiar los clientes se descartan proyectos que ya no pertenecen a la selección.
          proyectos: proyectos.filter((pid) => ids.length === 0
            || ids.includes((listaProyectos ?? []).find((p) => p.id === pid)?.terminal_id ?? "")),
        })} />
      <Casillas titulo="Proyectos" vacio="No hay proyectos en la selección." elegidos={proyectos}
        opciones={visibles.map((p) => ({
          id: p.id,
          texto: <span>{p.nombre} <span className="text-xs text-slate-500">· {nombreCliente.get(p.terminal_id)} · {porcentaje(p.porcentaje_vigente)}</span></span>,
        }))}
        onCambiar={(ids) => onCambiar({ clientes, proyectos: ids })} />
    </>
  );
}

function valoresIniciales(def: DefReporte, url: URLSearchParams): Valores {
  const v: Valores = Object.fromEntries(def.params.map((p) => [p.nombre, url.get(p.nombre) ?? p.inicial?.() ?? ""]));
  if (def.alcance) {
    v.terminal_id = url.getAll("terminal_id");
    v.proyecto_id = url.getAll("proyecto_id");
  }
  return v;
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

  const [valores, setValores] = useState<Valores>(() => valoresIniciales(def, url));
  const [defActual, setDefActual] = useState(def.id);
  const [descargando, setDescargando] = useState<string | null>(null);

  // Al cambiar de reporte se reinician los parámetros (patrón "ajustar estado durante el render").
  if (defActual !== def.id) {
    setDefActual(def.id);
    setValores(valoresIniciales(def, new URLSearchParams()));
  }

  const texto = (k: string) => (typeof valores[k] === "string" ? (valores[k] as string) : "");
  const lista = (k: string) => (Array.isArray(valores[k]) ? (valores[k] as string[]) : []);
  const faltan = def.params.filter((p) => p.requerido && !texto(p.nombre));
  // "Sin empresa" viaja como sin_empresa=true (empresa_id solo acepta ids reales).
  const query: Query = { ...valores, empresa_id: undefined, ...filtroEmpresa(texto("empresa_id")) };
  if (texto("metodo_pago_id")) query.metodo_pago_id = [texto("metodo_pago_id")];

  const reporte = useQuery({
    queryKey: ["reporte", def.id, query],
    queryFn: () => api.get<Reporte>(`/reportes/${def.id}`, query),
    enabled: faltan.length === 0,
    placeholderData: keepPreviousData,
  });

  function elegir(id: string) {
    setUrl({ r: id }, { replace: true });
  }

  function cambiar(nombre: string, v: string) {
    setValores((s) => ({
      ...s,
      [nombre]: v,
      // Cambiar de empresa limpia la selección de clientes y proyectos.
      ...(nombre === "empresa_id" && def.alcance ? { terminal_id: [], proyecto_id: [] } : {}),
    }));
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

      <div className="grid gap-6 lg:grid-cols-[15rem_1fr]">
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
                <ControlParam key={p.nombre} p={p} valor={texto(p.nombre)} onCambiar={(v) => cambiar(p.nombre, v)} />
              ))}
            </div>
            {def.alcance && (
              <div className="mt-4 grid gap-4 sm:grid-cols-2">
                <SelectorAlcance empresaId={texto("empresa_id")} clientes={lista("terminal_id")} proyectos={lista("proyecto_id")}
                  onCambiar={({ clientes, proyectos }) => setValores((s) => ({ ...s, terminal_id: clientes, proyecto_id: proyectos }))} />
              </div>
            )}
            <div className="mt-4 flex flex-wrap items-center justify-between gap-3 border-t border-slate-100 pt-4">
              <div className="flex flex-wrap gap-2">
                {FORMATOS.map((f) => (
                  <Boton key={f.valor} variante="secundario" tamano="sm" disabled={faltan.length > 0}
                    cargando={descargando === f.valor} onClick={() => descargar(f.valor)}>
                    <Icono nombre="descargar" className="size-4" /> {f.texto}
                  </Boton>
                ))}
              </div>
              {def.id === "cierre-diario" && <EnviarCierre dia={texto("fecha")} />}
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
                    {reporte.data.elaborado_por && (
                      <p className="border-t border-slate-100 px-5 py-3 text-xs italic text-slate-500">
                        Elaborado por: {reporte.data.elaborado_por} — {fechaHoraLocal(new Date().toISOString())}
                      </p>
                    )}
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
