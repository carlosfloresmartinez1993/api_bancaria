import { useEffect, useState, type FormEvent } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../../lib/api";
import { fecha, hoyISO, porcentaje } from "../../lib/format";
import { useInvalidarDinero } from "../../lib/invalidar";
import type { CambioPorcentajeOut, HistorialPorcentaje, Terminal } from "../../lib/types";
import { SelectorEmpresa } from "../Selectores";
import { useToast } from "../Toast";
import { Aviso, Boton, Campo, Cargando, ErrorApi, Input, Insignia, Modal, PieModal, Tabla, Td, Textarea, Th } from "../ui";

/** datos_extra es un objeto libre; se edita como JSON. */
function parsearExtra(texto: string): Record<string, unknown> {
  if (!texto.trim()) return {};
  const valor: unknown = JSON.parse(texto);
  if (!valor || typeof valor !== "object" || Array.isArray(valor)) throw new Error("Debe ser un objeto JSON");
  return valor as Record<string, unknown>;
}

function textoExtra(extra: Record<string, unknown>): string {
  return Object.keys(extra).length ? JSON.stringify(extra, null, 2) : "";
}

export function CrearTerminal({
  abierto,
  onCerrar,
  empresaInicial = "",
}: {
  abierto: boolean;
  onCerrar: () => void;
  empresaInicial?: string;
}) {
  const avisar = useToast();
  const invalidar = useInvalidarDinero();
  const [empresaId, setEmpresaId] = useState(empresaInicial);
  const [identificador, setIdentificador] = useState("");
  const [pct, setPct] = useState("");
  const [desde, setDesde] = useState(hoyISO());
  const [modelo, setModelo] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [enviando, setEnviando] = useState(false);

  useEffect(() => {
    if (abierto) {
      setEmpresaId(empresaInicial);
      setIdentificador("");
      setPct("");
      setDesde(hoyISO());
      setModelo("");
      setError(null);
    }
  }, [abierto, empresaInicial]);

  async function guardar(e: FormEvent) {
    e.preventDefault();
    setEnviando(true);
    setError(null);
    try {
      await api.post<Terminal>("/terminales", {
        empresa_id: empresaId,
        identificador_terminal: identificador.trim(),
        porcentaje_inicial: pct,
        vigente_desde: desde,
        datos_extra: modelo.trim() ? { modelo: modelo.trim() } : {},
      });
      invalidar();
      avisar("Terminal registrada");
      onCerrar();
    } catch (err) {
      setError(err);
    } finally {
      setEnviando(false);
    }
  }

  return (
    <Modal abierto={abierto} titulo="Nueva terminal" onCerrar={onCerrar}>
      <form onSubmit={guardar} className="space-y-4">
        <Campo etiqueta="Empresa" requerido>
          {(id) => <SelectorEmpresa id={id} required valor={empresaId} onCambiar={setEmpresaId} />}
        </Campo>
        <Campo etiqueta="Identificador de la terminal" requerido ayuda="Único dentro de la empresa. Ej. TPV-1234">
          {(id) => <Input id={id} required maxLength={100} value={identificador} onChange={(e) => setIdentificador(e.target.value)} />}
        </Campo>
        <div className="grid gap-4 sm:grid-cols-2">
          <Campo etiqueta="Comisión inicial (%)" requerido>
            {(id) => <Input id={id} type="number" required min="0" max="99.99" step="0.01" placeholder="3.50" value={pct} onChange={(e) => setPct(e.target.value)} />}
          </Campo>
          <Campo etiqueta="Vigente desde" requerido ayuda="Debe cubrir la fecha de los movimientos que se capturen.">
            {(id) => <Input id={id} type="date" required max={hoyISO()} value={desde} onChange={(e) => setDesde(e.target.value)} />}
          </Campo>
        </div>
        <Campo etiqueta="Modelo (opcional)">
          {(id) => <Input id={id} placeholder="Ej. Verifone V200c" value={modelo} onChange={(e) => setModelo(e.target.value)} />}
        </Campo>
        <ErrorApi error={error} />
        <PieModal>
          <Boton variante="secundario" onClick={onCerrar}>Cancelar</Boton>
          <Boton type="submit" cargando={enviando}>Registrar terminal</Boton>
        </PieModal>
      </form>
    </Modal>
  );
}

function CambiarPorcentaje({ terminal, inicioAbierto, onListo }: { terminal: Terminal; inicioAbierto?: string; onListo: () => void }) {
  const avisar = useToast();
  const invalidar = useInvalidarDinero();
  const [pct, setPct] = useState("");
  const [desde, setDesde] = useState(hoyISO());
  const [motivo, setMotivo] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [enviando, setEnviando] = useState(false);

  async function guardar(e: FormEvent) {
    e.preventDefault();
    setEnviando(true);
    setError(null);
    try {
      const r = await api.post<CambioPorcentajeOut>(`/terminales/${terminal.id}/porcentajes`, {
        porcentaje: pct,
        vigente_desde: desde,
        motivo: motivo.trim() || null,
      });
      invalidar();
      avisar(
        r.movimientos_recalculados
          ? `Porcentaje actualizado · ${r.movimientos_recalculados} movimiento(s) recalculado(s)`
          : "Porcentaje actualizado",
      );
      setPct("");
      setMotivo("");
      onListo();
    } catch (err) {
      setError(err);
    } finally {
      setEnviando(false);
    }
  }

  return (
    <form onSubmit={guardar} className="space-y-3 rounded-lg bg-slate-50 p-4 ring-1 ring-slate-200">
      <p className="text-sm font-medium text-slate-900">Cambiar porcentaje</p>
      <div className="grid gap-3 sm:grid-cols-2">
        <Campo etiqueta="Nuevo porcentaje (%)" requerido>
          {(id) => <Input id={id} type="number" required min="0" max="99.99" step="0.01" value={pct} onChange={(e) => setPct(e.target.value)} />}
        </Campo>
        <Campo etiqueta="Vigente desde" requerido>
          {(id) => <Input id={id} type="date" required min={inicioAbierto} value={desde} onChange={(e) => setDesde(e.target.value)} />}
        </Campo>
      </div>
      <Campo etiqueta="Motivo">
        {(id) => <Input id={id} maxLength={500} placeholder="Ej. Ajuste de tarifa del banco" value={motivo} onChange={(e) => setMotivo(e.target.value)} />}
      </Campo>
      {desde < hoyISO() && (
        <Aviso tono="aviso">
          Los movimientos de esta terminal con fecha desde el {fecha(desde)} se recalcularán con el nuevo porcentaje.
        </Aviso>
      )}
      <ErrorApi error={error} />
      <div className="flex justify-end">
        <Boton type="submit" cargando={enviando}>Aplicar cambio</Boton>
      </div>
    </form>
  );
}

export function DetalleTerminal({ terminal, onCerrar }: { terminal: Terminal | null; onCerrar: () => void }) {
  const avisar = useToast();
  const invalidar = useInvalidarDinero();
  const [identificador, setIdentificador] = useState("");
  const [extra, setExtra] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [enviando, setEnviando] = useState(false);
  const [actual, setActual] = useState<Terminal | null>(terminal);

  useEffect(() => {
    setActual(terminal);
    if (terminal) {
      setIdentificador(terminal.identificador_terminal);
      setExtra(textoExtra(terminal.datos_extra));
      setError(null);
    }
  }, [terminal]);

  const historial = useQuery({
    queryKey: ["porcentajes", terminal?.id, "historial"],
    queryFn: () => api.get<HistorialPorcentaje[]>(`/terminales/${terminal!.id}/porcentajes`),
    enabled: Boolean(terminal),
  });

  if (!terminal || !actual) return null;
  const abierto = historial.data?.find((h) => h.fecha_fin_vigencia === null);

  async function guardar(e: FormEvent) {
    e.preventDefault();
    if (!actual) return;
    setError(null);
    let datosExtra: Record<string, unknown>;
    try {
      datosExtra = parsearExtra(extra);
    } catch (err) {
      setError(new Error(`Datos adicionales: ${(err as Error).message}`));
      return;
    }
    const cambios: Record<string, unknown> = {};
    if (identificador.trim() !== actual.identificador_terminal) cambios.identificador_terminal = identificador.trim();
    if (JSON.stringify(datosExtra) !== JSON.stringify(actual.datos_extra)) cambios.datos_extra = datosExtra;
    if (!Object.keys(cambios).length) {
      setError(new Error("No hiciste ningún cambio"));
      return;
    }
    setEnviando(true);
    try {
      setActual(await api.patch<Terminal>(`/terminales/${actual.id}`, cambios));
      invalidar();
      avisar("Terminal actualizada");
    } catch (err) {
      setError(err);
    } finally {
      setEnviando(false);
    }
  }

  async function alternarEstado() {
    if (!actual) return;
    setError(null);
    try {
      const t = await api.post<Terminal>(`/terminales/${actual.id}/${actual.activa ? "desactivar" : "activar"}`);
      setActual(t);
      invalidar();
      avisar(t.activa ? "Terminal activada" : "Terminal desactivada");
    } catch (err) {
      setError(err);
    }
  }

  return (
    <Modal
      abierto
      ancho="lg"
      titulo={
        <span className="flex items-center gap-2">
          Terminal {actual.identificador_terminal}
          {actual.activa ? <Insignia tono="exito">Activa</Insignia> : <Insignia>Inactiva</Insignia>}
        </span>
      }
      descripcion={`Comisión vigente hoy: ${porcentaje(actual.porcentaje_vigente)}`}
      onCerrar={onCerrar}
    >
      <div className="space-y-6">
        <form onSubmit={guardar} className="space-y-3">
          <Campo etiqueta="Identificador">
            {(id) => <Input id={id} required maxLength={100} value={identificador} onChange={(e) => setIdentificador(e.target.value)} />}
          </Campo>
          <Campo etiqueta="Datos adicionales (JSON)" ayuda='Ej. {"modelo": "Verifone V200c", "serie": "123"}'>
            {(id) => <Textarea id={id} rows={3} className="font-mono text-xs" value={extra} onChange={(e) => setExtra(e.target.value)} />}
          </Campo>
          <ErrorApi error={error} />
          <div className="flex flex-wrap justify-between gap-2">
            <Boton variante={actual.activa ? "secundario" : "primario"} onClick={alternarEstado}>
              {actual.activa ? "Desactivar terminal" : "Activar terminal"}
            </Boton>
            <Boton type="submit" variante="secundario" cargando={enviando}>Guardar datos</Boton>
          </div>
          {!actual.activa && (
            <p className="text-xs text-slate-500">Una terminal inactiva no acepta capturas nuevas; sus movimientos se conservan.</p>
          )}
        </form>

        <div>
          <h3 className="mb-2 text-sm font-semibold text-slate-900">Historial de porcentajes</h3>
          {historial.isLoading ? (
            <Cargando />
          ) : (
            <div className="overflow-hidden rounded-lg ring-1 ring-slate-200">
              <Tabla>
                <thead>
                  <tr>
                    <Th>Desde</Th>
                    <Th>Hasta</Th>
                    <Th derecha>Comisión</Th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {[...(historial.data ?? [])].reverse().map((h) => (
                    <tr key={h.id}>
                      <Td>{fecha(h.fecha_inicio_vigencia)}</Td>
                      <Td>{h.fecha_fin_vigencia ? fecha(h.fecha_fin_vigencia) : <Insignia tono="exito">Vigente</Insignia>}</Td>
                      <Td derecha className="font-medium">{porcentaje(h.porcentaje)}</Td>
                    </tr>
                  ))}
                </tbody>
              </Tabla>
            </div>
          )}
          <p className="mt-2 text-xs text-slate-500">
            Cada periodo rige desde su fecha de inicio (inclusive) hasta la fecha final (exclusiva).
          </p>
        </div>

        <CambiarPorcentaje
          terminal={actual}
          inicioAbierto={abierto?.fecha_inicio_vigencia}
          onListo={async () => {
            await historial.refetch();
            setActual(await api.get<Terminal>(`/terminales/${actual.id}`));
          }}
        />
      </div>
    </Modal>
  );
}
