import { useCallback, useEffect, useState, type FormEvent } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../../lib/api";
import { dinero, hoyISO, porcentaje } from "../../lib/format";
import { useInvalidarDinero } from "../../lib/invalidar";
import { useMetodosPago } from "../../lib/queries";
import type { HistorialPorcentaje, Movimiento } from "../../lib/types";
import { SelectorMetodoPago, SelectorProyecto } from "../Selectores";
import { useToast } from "../Toast";
import { Aviso, Boton, Campo, ErrorApi, Input, Modal, PieModal, Textarea } from "../ui";
import { CADENA_VACIA, CadenaProyecto, type Cadena } from "./CadenaProyecto";
import { MAX_FACTURA_MB, SelectorPdf, subirFactura } from "./FacturaEntrada";

/** Método de pago que se propone por defecto: Transferencia si existe, si no el primero. */
export function useMetodoPorDefecto(): string {
  const { data } = useMetodosPago();
  return (data?.find((m) => m.nombre === "Transferencia") ?? data?.[0])?.id ?? "";
}

/** Muestra el % que regía para el proyecto en esa fecha y el neto estimado. */
function VistaPrevia({ proyectoId, dia, monto }: { proyectoId: string; dia: string; monto: string }) {
  const { data, error, isFetching } = useQuery({
    queryKey: ["porcentajes", proyectoId, "vigente", dia],
    queryFn: () => api.get<HistorialPorcentaje>(`/proyectos/${proyectoId}/porcentaje-vigente`, { dia }),
    enabled: Boolean(proyectoId && dia),
  });
  if (!proyectoId || !dia) return null;
  if (error) return <Aviso tono="aviso">{(error as Error).message}</Aviso>;
  if (!data) return isFetching ? <p className="text-xs text-slate-500">Consultando porcentaje…</p> : null;

  const bruto = Number(monto);
  const pct = Number(data.porcentaje);
  const neto = bruto > 0 ? Math.round(bruto * (1 - pct / 100) * 100) / 100 : null;
  return (
    <div className="grid grid-cols-3 gap-3 rounded-lg bg-slate-50 p-3 text-sm ring-1 ring-slate-200">
      <div>
        <p className="text-xs text-slate-500">Comisión del proyecto</p>
        <p className="font-medium tabular-nums">{porcentaje(data.porcentaje)}</p>
      </div>
      <div>
        <p className="text-xs text-slate-500">Comisión</p>
        <p className="font-medium tabular-nums">{neto !== null ? dinero(bruto - neto) : "—"}</p>
      </div>
      <div>
        <p className="text-xs text-slate-500">Neto estimado</p>
        <p className="font-semibold tabular-nums text-teal-700">{neto !== null ? dinero(neto) : "—"}</p>
      </div>
    </div>
  );
}

function CasillaFactura({ valor, onCambiar }: { valor: boolean; onCambiar: (v: boolean) => void }) {
  return (
    <label className="flex cursor-pointer items-center gap-3 rounded-lg p-3 ring-1 ring-slate-200 hover:bg-slate-50">
      <input type="checkbox" checked={valor} onChange={(e) => onCambiar(e.target.checked)}
        className="size-4 rounded border-slate-300 accent-teal-700" />
      <span className="text-sm">
        <span className="font-medium text-slate-900">Requiere factura</span>
        <span className="block text-xs text-slate-500">Marca si este ingreso se debe facturar.</span>
      </span>
    </label>
  );
}

export function CapturarMovimiento({
  abierto,
  onCerrar,
  inicial = CADENA_VACIA,
}: {
  abierto: boolean;
  onCerrar: () => void;
  inicial?: Partial<Cadena>;
}) {
  const avisar = useToast();
  const invalidar = useInvalidarDinero();
  const metodoDefecto = useMetodoPorDefecto();
  const [cadena, setCadena] = useState<Cadena>(CADENA_VACIA);
  const [dia, setDia] = useState(hoyISO());
  const [monto, setMonto] = useState("");
  const [metodo, setMetodo] = useState("");
  const [factura, setFactura] = useState(false);
  const [observaciones, setObservaciones] = useState("");
  const [pdf, setPdf] = useState<File | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [enviando, setEnviando] = useState(false);

  const { empresaId = "", clienteId = "", proyectoId = "" } = inicial;
  useEffect(() => {
    if (abierto) {
      setCadena({ empresaId, clienteId, proyectoId });
      setError(null);
    }
  }, [abierto, empresaId, clienteId, proyectoId]);

  useEffect(() => {
    if (!metodo && metodoDefecto) setMetodo(metodoDefecto);
  }, [metodo, metodoDefecto]);

  const cambiarCadena = useCallback((c: Cadena) => setCadena(c), []);

  async function guardar(e: { preventDefault(): void }, otro: boolean) {
    e.preventDefault();
    setEnviando(true);
    setError(null);
    try {
      const mov = await api.post<Movimiento>("/movimientos", {
        proyecto_id: cadena.proyectoId,
        fecha_movimiento: dia,
        monto_bruto: monto,
        metodo_pago_id: metodo,
        requiere_factura: factura,
        observaciones: observaciones.trim() || null,
      });
      let aviso = `Entrada capturada · neto ${dinero(mov.monto_neto)}`;
      if (pdf) {
        try {
          await subirFactura(mov.id, pdf);
          aviso += " · factura adjunta";
        } catch (err) {
          // La entrada ya quedó guardada: se avisa y la factura se puede subir después desde la tabla.
          aviso += ` · la factura no se subió (${(err as Error).message}); súbela desde la tabla de Entradas`;
        }
      }
      invalidar();
      avisar(aviso);
      setMonto("");
      setFactura(false);
      setObservaciones("");
      setPdf(null);
      if (!otro) onCerrar();
    } catch (err) {
      setError(err);
    } finally {
      setEnviando(false);
    }
  }

  return (
    <Modal abierto={abierto} titulo="Capturar entrada" descripcion="Ingreso del corte de un cliente, asignado a un proyecto."
      onCerrar={onCerrar} ancho="lg">
      <form onSubmit={(e) => guardar(e, false)} className="space-y-4">
        <CadenaProyecto valor={cadena} onCambiar={cambiarCadena} />
        <div className="grid gap-4 sm:grid-cols-3">
          <Campo etiqueta="Fecha" requerido>
            {(id) => <Input id={id} type="date" required max={hoyISO()} value={dia} onChange={(e) => setDia(e.target.value)} />}
          </Campo>
          <Campo etiqueta="Monto bruto" requerido>
            {(id) => (
              <Input id={id} type="number" required min="0.01" step="0.01" inputMode="decimal" placeholder="0.00"
                value={monto} onChange={(e) => setMonto(e.target.value)} />
            )}
          </Campo>
          <Campo etiqueta="Método de pago" requerido>
            {(id) => <SelectorMetodoPago id={id} required valor={metodo} onCambiar={setMetodo} />}
          </Campo>
        </div>
        <VistaPrevia proyectoId={cadena.proyectoId} dia={dia} monto={monto} />
        <CasillaFactura valor={factura} onCambiar={setFactura} />
        <Campo etiqueta="Factura (PDF)" ayuda={`Opcional. Máximo ${MAX_FACTURA_MB} MB; también se puede subir después.`}>
          {(id) => <SelectorPdf id={id} archivo={pdf} onCambiar={setPdf} />}
        </Campo>
        <Campo etiqueta="Observaciones">
          {(id) => <Textarea id={id} rows={2} maxLength={2000} value={observaciones} onChange={(e) => setObservaciones(e.target.value)} />}
        </Campo>
        <ErrorApi error={error} />
        <PieModal>
          <Boton variante="secundario" onClick={onCerrar}>Cancelar</Boton>
          <Boton variante="secundario" cargando={enviando}
            onClick={(e) => (e.currentTarget.form?.reportValidity() ? guardar(e, true) : undefined)}>
            Guardar y capturar otra
          </Boton>
          <Boton type="submit" cargando={enviando}>Guardar</Boton>
        </PieModal>
      </form>
    </Modal>
  );
}

export function EditarMovimiento({ movimiento, onCerrar }: { movimiento: Movimiento | null; onCerrar: () => void }) {
  const avisar = useToast();
  const invalidar = useInvalidarDinero();
  const [proyectoId, setProyectoId] = useState("");
  const [dia, setDia] = useState("");
  const [monto, setMonto] = useState("");
  const [metodo, setMetodo] = useState("");
  const [factura, setFactura] = useState(false);
  const [observaciones, setObservaciones] = useState("");
  const [motivo, setMotivo] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [enviando, setEnviando] = useState(false);

  useEffect(() => {
    if (movimiento) {
      setProyectoId(movimiento.proyecto_id);
      setDia(movimiento.fecha_movimiento);
      setMonto(movimiento.monto_bruto);
      setMetodo(movimiento.metodo_pago_id);
      setFactura(movimiento.requiere_factura);
      setObservaciones(movimiento.observaciones ?? "");
      setMotivo("");
      setError(null);
    }
  }, [movimiento]);

  if (!movimiento) return null;

  async function guardar(e: FormEvent) {
    e.preventDefault();
    if (!movimiento) return;
    const cambios: Record<string, unknown> = {};
    if (proyectoId !== movimiento.proyecto_id) cambios.proyecto_id = proyectoId;
    if (dia !== movimiento.fecha_movimiento) cambios.fecha_movimiento = dia;
    if (Number(monto) !== Number(movimiento.monto_bruto)) cambios.monto_bruto = monto;
    if (metodo !== movimiento.metodo_pago_id) cambios.metodo_pago_id = metodo;
    if (factura !== movimiento.requiere_factura) cambios.requiere_factura = factura;
    if ((observaciones.trim() || null) !== movimiento.observaciones) cambios.observaciones = observaciones.trim() || null;
    if (Object.keys(cambios).length === 0) {
      setError(new Error("No hiciste ningún cambio"));
      return;
    }
    setEnviando(true);
    setError(null);
    try {
      await api.patch<Movimiento>(`/movimientos/${movimiento.id}`, { ...cambios, motivo: motivo.trim() || null });
      invalidar();
      avisar("Entrada corregida");
      onCerrar();
    } catch (err) {
      setError(err);
    } finally {
      setEnviando(false);
    }
  }

  return (
    <Modal abierto ancho="lg" titulo="Corregir entrada" descripcion="El cambio queda registrado en la bitácora con su estado anterior."
      onCerrar={onCerrar}>
      <form onSubmit={guardar} className="space-y-4">
        <Campo etiqueta="Proyecto" ayuda="Se puede mover a otro proyecto activo de la misma empresa (o del mismo cliente, si no tiene empresa).">
          {(id) => <SelectorProyecto id={id} valor={proyectoId} onCambiar={setProyectoId}
            empresaId={movimiento.empresa_id ?? undefined}
            terminalId={movimiento.empresa_id ? undefined : movimiento.terminal_id} />}
        </Campo>
        <div className="grid gap-4 sm:grid-cols-3">
          <Campo etiqueta="Fecha">
            {(id) => <Input id={id} type="date" required max={hoyISO()} value={dia} onChange={(e) => setDia(e.target.value)} />}
          </Campo>
          <Campo etiqueta="Monto bruto">
            {(id) => <Input id={id} type="number" required min="0.01" step="0.01" value={monto} onChange={(e) => setMonto(e.target.value)} />}
          </Campo>
          <Campo etiqueta="Método de pago">
            {(id) => <SelectorMetodoPago id={id} required valor={metodo} onCambiar={setMetodo} />}
          </Campo>
        </div>
        {(proyectoId !== movimiento.proyecto_id || dia !== movimiento.fecha_movimiento) && (
          <Aviso tono="info">El porcentaje se recalculará con el que regía para el proyecto en esa fecha.</Aviso>
        )}
        <VistaPrevia proyectoId={proyectoId} dia={dia} monto={monto} />
        <CasillaFactura valor={factura} onCambiar={setFactura} />
        <Campo etiqueta="Observaciones">
          {(id) => <Textarea id={id} rows={2} maxLength={2000} value={observaciones} onChange={(e) => setObservaciones(e.target.value)} />}
        </Campo>
        <Campo etiqueta="Motivo de la corrección" ayuda="Se guarda en la bitácora.">
          {(id) => <Input id={id} maxLength={500} placeholder="Ej. Capturé un cero de más" value={motivo} onChange={(e) => setMotivo(e.target.value)} />}
        </Campo>
        <ErrorApi error={error} />
        <PieModal>
          <Boton variante="secundario" onClick={onCerrar}>Cancelar</Boton>
          <Boton type="submit" cargando={enviando}>Guardar cambios</Boton>
        </PieModal>
      </form>
    </Modal>
  );
}
