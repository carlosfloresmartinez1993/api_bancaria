import { useEffect, useState, type FormEvent } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../../lib/api";
import { dinero, hoyISO, porcentaje } from "../../lib/format";
import { useInvalidarDinero } from "../../lib/invalidar";
import { useTerminalesCatalogo } from "../../lib/queries";
import type { HistorialPorcentaje, Movimiento } from "../../lib/types";
import { SelectorEmpresa, SelectorTerminal } from "../Selectores";
import { useToast } from "../Toast";
import { Aviso, Boton, Campo, ErrorApi, Input, Modal, PieModal, Textarea } from "../ui";

/** Muestra el % que regía para la terminal en esa fecha y el neto estimado. */
function VistaPrevia({ terminalId, dia, monto }: { terminalId: string; dia: string; monto: string }) {
  const { data, error, isFetching } = useQuery({
    queryKey: ["porcentajes", terminalId, "vigente", dia],
    queryFn: () => api.get<HistorialPorcentaje>(`/terminales/${terminalId}/porcentaje-vigente`, { dia }),
    enabled: Boolean(terminalId && dia),
  });
  if (!terminalId || !dia) return null;
  if (error) return <Aviso tono="aviso">{(error as Error).message}</Aviso>;
  if (!data) return isFetching ? <p className="text-xs text-slate-500">Consultando porcentaje…</p> : null;

  const bruto = Number(monto);
  const pct = Number(data.porcentaje);
  const neto = bruto > 0 ? Math.round(bruto * (1 - pct / 100) * 100) / 100 : null;
  return (
    <div className="grid grid-cols-3 gap-3 rounded-lg bg-slate-50 p-3 text-sm ring-1 ring-slate-200">
      <div>
        <p className="text-xs text-slate-500">Comisión vigente</p>
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

export function CapturarMovimiento({
  abierto,
  onCerrar,
  empresaInicial = "",
  terminalInicial = "",
}: {
  abierto: boolean;
  onCerrar: () => void;
  empresaInicial?: string;
  terminalInicial?: string;
}) {
  const avisar = useToast();
  const invalidar = useInvalidarDinero();
  const [empresaId, setEmpresaId] = useState(empresaInicial);
  const [terminalId, setTerminalId] = useState(terminalInicial);
  const [dia, setDia] = useState(hoyISO());
  const [monto, setMonto] = useState("");
  const [observaciones, setObservaciones] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [enviando, setEnviando] = useState(false);
  const { data: terminales } = useTerminalesCatalogo(empresaId || undefined);

  useEffect(() => {
    if (abierto) {
      setEmpresaId(empresaInicial);
      setTerminalId(terminalInicial);
      setError(null);
    }
  }, [abierto, empresaInicial, terminalInicial]);

  // Si la empresa elegida tiene una sola terminal activa, se selecciona sola.
  useEffect(() => {
    const activas = (terminales ?? []).filter((t) => t.activa);
    if (empresaId && activas.length === 1 && !terminalId) setTerminalId(activas[0].id);
  }, [terminales, empresaId, terminalId]);

  async function guardar(e: FormEvent, otro: boolean) {
    e.preventDefault();
    setEnviando(true);
    setError(null);
    try {
      const mov = await api.post<Movimiento>("/movimientos", {
        terminal_id: terminalId,
        fecha_movimiento: dia,
        monto_bruto: monto,
        observaciones: observaciones.trim() || null,
      });
      invalidar();
      avisar(`Movimiento capturado · neto ${dinero(mov.monto_neto)}`);
      setMonto("");
      setObservaciones("");
      if (!otro) onCerrar();
    } catch (err) {
      setError(err);
    } finally {
      setEnviando(false);
    }
  }

  return (
    <Modal abierto={abierto} titulo="Capturar movimiento" descripcion="Ingreso del corte de una terminal." onCerrar={onCerrar}>
      <form onSubmit={(e) => guardar(e, false)} className="space-y-4">
        <Campo etiqueta="Empresa">
          {(id) => (
            <SelectorEmpresa id={id} valor={empresaId} vacio="Todas las empresas"
              onCambiar={(v) => { setEmpresaId(v); setTerminalId(""); }} />
          )}
        </Campo>
        <Campo etiqueta="Terminal" requerido>
          {(id) => <SelectorTerminal id={id} required valor={terminalId} onCambiar={setTerminalId} empresaId={empresaId} soloActivas />}
        </Campo>
        <div className="grid gap-4 sm:grid-cols-2">
          <Campo etiqueta="Fecha del movimiento" requerido>
            {(id) => <Input id={id} type="date" required max={hoyISO()} value={dia} onChange={(e) => setDia(e.target.value)} />}
          </Campo>
          <Campo etiqueta="Monto bruto" requerido>
            {(id) => (
              <Input id={id} type="number" required min="0.01" step="0.01" inputMode="decimal" placeholder="0.00"
                value={monto} onChange={(e) => setMonto(e.target.value)} />
            )}
          </Campo>
        </div>
        <VistaPrevia terminalId={terminalId} dia={dia} monto={monto} />
        <Campo etiqueta="Observaciones">
          {(id) => <Textarea id={id} maxLength={2000} value={observaciones} onChange={(e) => setObservaciones(e.target.value)} />}
        </Campo>
        <ErrorApi error={error} />
        <PieModal>
          <Boton variante="secundario" onClick={onCerrar}>Cancelar</Boton>
          <Boton variante="secundario" cargando={enviando}
            onClick={(e) => (e.currentTarget.form?.reportValidity() ? guardar(e, true) : undefined)}>
            Guardar y capturar otro
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
  const [terminalId, setTerminalId] = useState("");
  const [dia, setDia] = useState("");
  const [monto, setMonto] = useState("");
  const [observaciones, setObservaciones] = useState("");
  const [motivo, setMotivo] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [enviando, setEnviando] = useState(false);

  useEffect(() => {
    if (movimiento) {
      setTerminalId(movimiento.terminal_id);
      setDia(movimiento.fecha_movimiento);
      setMonto(movimiento.monto_bruto);
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
    if (terminalId !== movimiento.terminal_id) cambios.terminal_id = terminalId;
    if (dia !== movimiento.fecha_movimiento) cambios.fecha_movimiento = dia;
    if (Number(monto) !== Number(movimiento.monto_bruto)) cambios.monto_bruto = monto;
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
      avisar("Movimiento corregido");
      onCerrar();
    } catch (err) {
      setError(err);
    } finally {
      setEnviando(false);
    }
  }

  return (
    <Modal abierto titulo="Corregir movimiento" descripcion="El cambio queda registrado en la bitácora con su estado anterior."
      onCerrar={onCerrar}>
      <form onSubmit={guardar} className="space-y-4">
        <Campo etiqueta="Terminal" ayuda="Solo se puede mover a otra terminal activa de la misma empresa.">
          {(id) => <SelectorTerminal id={id} valor={terminalId} onCambiar={setTerminalId} empresaId={movimiento.empresa_id} />}
        </Campo>
        <div className="grid gap-4 sm:grid-cols-2">
          <Campo etiqueta="Fecha del movimiento">
            {(id) => <Input id={id} type="date" required max={hoyISO()} value={dia} onChange={(e) => setDia(e.target.value)} />}
          </Campo>
          <Campo etiqueta="Monto bruto">
            {(id) => <Input id={id} type="number" required min="0.01" step="0.01" value={monto} onChange={(e) => setMonto(e.target.value)} />}
          </Campo>
        </div>
        {(terminalId !== movimiento.terminal_id || dia !== movimiento.fecha_movimiento) && (
          <Aviso tono="info">El porcentaje se recalculará con el que regía para la terminal en la nueva fecha.</Aviso>
        )}
        <VistaPrevia terminalId={terminalId} dia={dia} monto={monto} />
        <Campo etiqueta="Observaciones">
          {(id) => <Textarea id={id} maxLength={2000} value={observaciones} onChange={(e) => setObservaciones(e.target.value)} />}
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
