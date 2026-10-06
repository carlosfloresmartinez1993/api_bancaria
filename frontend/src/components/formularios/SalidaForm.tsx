import { useEffect, useState, type FormEvent } from "react";
import { api } from "../../lib/api";
import { dinero, hoyISO } from "../../lib/format";
import { useInvalidarDinero } from "../../lib/invalidar";
import type { Salida, SalidaRegistrada } from "../../lib/types";
import { SelectorEmpresa } from "../Selectores";
import { useToast } from "../Toast";
import { Boton, Campo, ErrorApi, Input, Modal, PieModal, Textarea } from "../ui";

function useAvisoSaldo() {
  const avisar = useToast();
  return (r: SalidaRegistrada, accion: string) => {
    if (r.advertencia) avisar(r.advertencia, "aviso");
    else avisar(`${accion} · saldo de la empresa: ${dinero(r.saldo_empresa)}`);
  };
}

export function RegistrarSalida({
  abierto,
  onCerrar,
  empresaInicial = "",
}: {
  abierto: boolean;
  onCerrar: () => void;
  empresaInicial?: string;
}) {
  const invalidar = useInvalidarDinero();
  const avisarSaldo = useAvisoSaldo();
  const [empresaId, setEmpresaId] = useState(empresaInicial);
  const [monto, setMonto] = useState("");
  const [destino, setDestino] = useState("");
  const [dia, setDia] = useState(hoyISO());
  const [observaciones, setObservaciones] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [enviando, setEnviando] = useState(false);

  useEffect(() => {
    if (abierto) {
      setEmpresaId(empresaInicial);
      setMonto("");
      setDestino("");
      setDia(hoyISO());
      setObservaciones("");
      setError(null);
    }
  }, [abierto, empresaInicial]);

  async function guardar(e: FormEvent) {
    e.preventDefault();
    setEnviando(true);
    setError(null);
    try {
      const r = await api.post<SalidaRegistrada>("/salidas", {
        empresa_id: empresaId,
        monto,
        destino: destino.trim(),
        fecha: dia,
        observaciones: observaciones.trim() || null,
      });
      invalidar();
      avisarSaldo(r, "Salida registrada");
      onCerrar();
    } catch (err) {
      setError(err);
    } finally {
      setEnviando(false);
    }
  }

  return (
    <Modal abierto={abierto} titulo="Registrar salida"
      descripcion="Control de una salida de dinero; la transferencia real la hace contabilidad." onCerrar={onCerrar}>
      <form onSubmit={guardar} className="space-y-4">
        <Campo etiqueta="Empresa" requerido>
          {(id) => <SelectorEmpresa id={id} required valor={empresaId} onCambiar={setEmpresaId} />}
        </Campo>
        <div className="grid gap-4 sm:grid-cols-2">
          <Campo etiqueta="Monto" requerido>
            {(id) => <Input id={id} type="number" required min="0.01" step="0.01" placeholder="0.00" value={monto} onChange={(e) => setMonto(e.target.value)} />}
          </Campo>
          <Campo etiqueta="Fecha" requerido>
            {(id) => <Input id={id} type="date" required max={hoyISO()} value={dia} onChange={(e) => setDia(e.target.value)} />}
          </Campo>
        </div>
        <Campo etiqueta="Destino" requerido>
          {(id) => <Input id={id} required maxLength={255} placeholder="Ej. Pago a proveedor" value={destino} onChange={(e) => setDestino(e.target.value)} />}
        </Campo>
        <Campo etiqueta="Observaciones">
          {(id) => <Textarea id={id} maxLength={2000} value={observaciones} onChange={(e) => setObservaciones(e.target.value)} />}
        </Campo>
        <ErrorApi error={error} />
        <PieModal>
          <Boton variante="secundario" onClick={onCerrar}>Cancelar</Boton>
          <Boton type="submit" cargando={enviando}>Registrar</Boton>
        </PieModal>
      </form>
    </Modal>
  );
}

export function EditarSalida({ salida, onCerrar }: { salida: Salida | null; onCerrar: () => void }) {
  const invalidar = useInvalidarDinero();
  const avisarSaldo = useAvisoSaldo();
  const [monto, setMonto] = useState("");
  const [destino, setDestino] = useState("");
  const [dia, setDia] = useState("");
  const [observaciones, setObservaciones] = useState("");
  const [motivo, setMotivo] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [enviando, setEnviando] = useState(false);

  useEffect(() => {
    if (salida) {
      setMonto(salida.monto);
      setDestino(salida.destino);
      setDia(salida.fecha);
      setObservaciones(salida.observaciones ?? "");
      setMotivo("");
      setError(null);
    }
  }, [salida]);

  if (!salida) return null;

  async function guardar(e: FormEvent) {
    e.preventDefault();
    if (!salida) return;
    const cambios: Record<string, unknown> = {};
    if (Number(monto) !== Number(salida.monto)) cambios.monto = monto;
    if (destino.trim() !== salida.destino) cambios.destino = destino.trim();
    if (dia !== salida.fecha) cambios.fecha = dia;
    if ((observaciones.trim() || null) !== salida.observaciones) cambios.observaciones = observaciones.trim() || null;
    if (Object.keys(cambios).length === 0) {
      setError(new Error("No hiciste ningún cambio"));
      return;
    }
    setEnviando(true);
    setError(null);
    try {
      const r = await api.patch<SalidaRegistrada>(`/salidas/${salida.id}`, { ...cambios, motivo: motivo.trim() || null });
      invalidar();
      avisarSaldo(r, "Salida corregida");
      onCerrar();
    } catch (err) {
      setError(err);
    } finally {
      setEnviando(false);
    }
  }

  return (
    <Modal abierto titulo="Corregir salida" descripcion="El cambio queda registrado en la bitácora." onCerrar={onCerrar}>
      <form onSubmit={guardar} className="space-y-4">
        <div className="grid gap-4 sm:grid-cols-2">
          <Campo etiqueta="Monto">
            {(id) => <Input id={id} type="number" required min="0.01" step="0.01" value={monto} onChange={(e) => setMonto(e.target.value)} />}
          </Campo>
          <Campo etiqueta="Fecha">
            {(id) => <Input id={id} type="date" required max={hoyISO()} value={dia} onChange={(e) => setDia(e.target.value)} />}
          </Campo>
        </div>
        <Campo etiqueta="Destino">
          {(id) => <Input id={id} required maxLength={255} value={destino} onChange={(e) => setDestino(e.target.value)} />}
        </Campo>
        <Campo etiqueta="Observaciones">
          {(id) => <Textarea id={id} maxLength={2000} value={observaciones} onChange={(e) => setObservaciones(e.target.value)} />}
        </Campo>
        <Campo etiqueta="Motivo de la corrección" ayuda="Se guarda en la bitácora.">
          {(id) => <Input id={id} maxLength={500} value={motivo} onChange={(e) => setMotivo(e.target.value)} />}
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
