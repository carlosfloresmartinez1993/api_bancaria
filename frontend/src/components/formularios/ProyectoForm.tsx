import { useEffect, useState, type FormEvent } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../../lib/api";
import { fecha, hoyISO, porcentaje } from "../../lib/format";
import { useInvalidarDinero } from "../../lib/invalidar";
import type { CambioPorcentajeOut, HistorialPorcentaje, Proyecto, Saldo } from "../../lib/types";
import { useToast } from "../Toast";
import { Aviso, Boton, Campo, Cargando, ErrorApi, Input, Insignia, Modal, Monto, PieModal, Tabla, Td, Th } from "../ui";

export function CrearProyecto({
  abierto,
  onCerrar,
  terminalId,
  cliente,
}: {
  abierto: boolean;
  onCerrar: () => void;
  terminalId: string;
  cliente: string;
}) {
  const avisar = useToast();
  const invalidar = useInvalidarDinero();
  const [nombre, setNombre] = useState("");
  const [pct, setPct] = useState("");
  const [desde, setDesde] = useState(hoyISO());
  const [error, setError] = useState<unknown>(null);
  const [enviando, setEnviando] = useState(false);

  useEffect(() => {
    if (abierto) {
      setNombre("");
      setPct("");
      setDesde(hoyISO());
      setError(null);
    }
  }, [abierto]);

  async function guardar(e: FormEvent) {
    e.preventDefault();
    setEnviando(true);
    setError(null);
    try {
      await api.post<Proyecto>("/proyectos", {
        terminal_id: terminalId,
        nombre: nombre.trim(),
        porcentaje_inicial: pct,
        vigente_desde: desde,
      });
      invalidar();
      avisar(`Proyecto «${nombre.trim()}» registrado`);
      onCerrar();
    } catch (err) {
      setError(err);
    } finally {
      setEnviando(false);
    }
  }

  return (
    <Modal abierto={abierto} titulo="Nuevo proyecto" descripcion={`Cliente ${cliente}`} onCerrar={onCerrar}>
      <form onSubmit={guardar} className="space-y-4">
        <Campo etiqueta="Nombre del proyecto" requerido ayuda="Único dentro del cliente. Ej. P1, Proyecto Norte">
          {(id) => <Input id={id} required maxLength={100} value={nombre} onChange={(e) => setNombre(e.target.value)} />}
        </Campo>
        <div className="grid gap-4 sm:grid-cols-2">
          <Campo etiqueta="Comisión (%)" requerido>
            {(id) => <Input id={id} type="number" required min="0" max="99.99" step="0.01" placeholder="3.00" value={pct} onChange={(e) => setPct(e.target.value)} />}
          </Campo>
          <Campo etiqueta="Vigente desde" requerido ayuda="Debe cubrir la fecha de las entradas que se capturen.">
            {(id) => <Input id={id} type="date" required max={hoyISO()} value={desde} onChange={(e) => setDesde(e.target.value)} />}
          </Campo>
        </div>
        <ErrorApi error={error} />
        <PieModal>
          <Boton variante="secundario" onClick={onCerrar}>Cancelar</Boton>
          <Boton type="submit" cargando={enviando}>Registrar proyecto</Boton>
        </PieModal>
      </form>
    </Modal>
  );
}

function CambiarPorcentaje({ proyecto, inicioAbierto, onListo }: { proyecto: Proyecto; inicioAbierto?: string; onListo: () => void }) {
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
      const r = await api.post<CambioPorcentajeOut>(`/proyectos/${proyecto.id}/porcentajes`, {
        porcentaje: pct,
        vigente_desde: desde,
        motivo: motivo.trim() || null,
      });
      invalidar();
      avisar(
        r.movimientos_recalculados
          ? `Porcentaje actualizado · ${r.movimientos_recalculados} entrada(s) recalculada(s)`
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
          Las entradas de este proyecto con fecha desde el {fecha(desde)} se recalcularán con el nuevo porcentaje.
        </Aviso>
      )}
      <ErrorApi error={error} />
      <div className="flex justify-end">
        <Boton type="submit" cargando={enviando}>Aplicar cambio</Boton>
      </div>
    </form>
  );
}

export function DetalleProyecto({ proyecto, onCerrar }: { proyecto: Proyecto | null; onCerrar: () => void }) {
  const avisar = useToast();
  const invalidar = useInvalidarDinero();
  const [nombre, setNombre] = useState("");
  const [actual, setActual] = useState<Proyecto | null>(proyecto);
  const [error, setError] = useState<unknown>(null);
  const [enviando, setEnviando] = useState(false);

  useEffect(() => {
    setActual(proyecto);
    if (proyecto) {
      setNombre(proyecto.nombre);
      setError(null);
    }
  }, [proyecto]);

  const historial = useQuery({
    queryKey: ["porcentajes", proyecto?.id, "historial"],
    queryFn: () => api.get<HistorialPorcentaje[]>(`/proyectos/${proyecto!.id}/porcentajes`),
    enabled: Boolean(proyecto),
  });
  const saldo = useQuery({
    queryKey: ["saldo", "proyecto", proyecto?.id],
    queryFn: () => api.get<Saldo>(`/proyectos/${proyecto!.id}/saldo`),
    enabled: Boolean(proyecto),
  });

  if (!proyecto || !actual) return null;
  const abierto = historial.data?.find((h) => h.fecha_fin_vigencia === null);

  async function renombrar(e: FormEvent) {
    e.preventDefault();
    if (!actual) return;
    if (nombre.trim() === actual.nombre) {
      setError(new Error("No hiciste ningún cambio"));
      return;
    }
    setEnviando(true);
    setError(null);
    try {
      setActual(await api.patch<Proyecto>(`/proyectos/${actual.id}`, { nombre: nombre.trim() }));
      invalidar();
      avisar("Proyecto actualizado");
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
      const p = await api.post<Proyecto>(`/proyectos/${actual.id}/${actual.activo ? "desactivar" : "activar"}`);
      setActual(p);
      invalidar();
      avisar(p.activo ? "Proyecto activado" : "Proyecto desactivado");
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
          Proyecto {actual.nombre}
          {actual.activo ? <Insignia tono="exito">Activo</Insignia> : <Insignia>Inactivo</Insignia>}
        </span>
      }
      descripcion={`Comisión vigente hoy: ${porcentaje(actual.porcentaje_vigente)}`}
      onCerrar={onCerrar}
    >
      <div className="space-y-6">
        {saldo.data && (
          <dl className="grid grid-cols-2 gap-3 rounded-lg bg-slate-50 p-3 text-sm ring-1 ring-slate-200 sm:grid-cols-4">
            <div><dt className="text-xs text-slate-500">Entradas netas</dt><dd className="font-medium"><Monto valor={saldo.data.ingresos_netos} /></dd></div>
            <div><dt className="text-xs text-slate-500">Comisiones</dt><dd className="font-medium"><Monto valor={saldo.data.comisiones} /></dd></div>
            <div><dt className="text-xs text-slate-500">Salidas</dt><dd className="font-medium"><Monto valor={saldo.data.salidas} /></dd></div>
            <div><dt className="text-xs text-slate-500">Saldo</dt><dd className="font-semibold"><Monto valor={saldo.data.saldo} resaltarNegativo /></dd></div>
          </dl>
        )}

        <form onSubmit={renombrar} className="space-y-3">
          <Campo etiqueta="Nombre">
            {(id) => <Input id={id} required maxLength={100} value={nombre} onChange={(e) => setNombre(e.target.value)} />}
          </Campo>
          <ErrorApi error={error} />
          <div className="flex flex-wrap justify-between gap-2">
            <Boton variante={actual.activo ? "secundario" : "primario"} onClick={alternarEstado}>
              {actual.activo ? "Desactivar proyecto" : "Activar proyecto"}
            </Boton>
            <Boton type="submit" variante="secundario" cargando={enviando}>Guardar nombre</Boton>
          </div>
          {!actual.activo && (
            <p className="text-xs text-slate-500">Un proyecto inactivo no acepta entradas ni salidas nuevas; su historial se conserva.</p>
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
          proyecto={actual}
          inicioAbierto={abierto?.fecha_inicio_vigencia}
          onListo={async () => {
            await historial.refetch();
            setActual(await api.get<Proyecto>(`/proyectos/${actual.id}`));
          }}
        />
      </div>
      <PieModal>
        <Boton variante="secundario" onClick={onCerrar}>Cerrar</Boton>
      </PieModal>
    </Modal>
  );
}
