import { useState, type ReactNode } from "react";
import { Boton, Campo, ErrorApi, Modal, PieModal, Textarea } from "../ui";

/** Confirmación de borrado con motivo opcional, que el backend guarda en la bitácora. */
export function ConfirmarEliminacion({
  abierto,
  titulo,
  children,
  onCerrar,
  onConfirmar,
}: {
  abierto: boolean;
  titulo: string;
  children: ReactNode;
  onCerrar: () => void;
  onConfirmar: (motivo: string | undefined) => Promise<unknown>;
}) {
  const [motivo, setMotivo] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [enviando, setEnviando] = useState(false);

  function cerrar() {
    setMotivo("");
    setError(null);
    onCerrar();
  }

  async function confirmar() {
    setEnviando(true);
    setError(null);
    try {
      await onConfirmar(motivo.trim() || undefined);
      cerrar();
    } catch (e) {
      setError(e);
    } finally {
      setEnviando(false);
    }
  }

  return (
    <Modal abierto={abierto} titulo={titulo} onCerrar={cerrar}>
      <div className="space-y-4">
        <div className="text-sm text-slate-600">{children}</div>
        <Campo etiqueta="Motivo" ayuda="Queda registrado en la bitácora de auditoría junto con el registro eliminado.">
          {(id) => (
            <Textarea id={id} maxLength={500} value={motivo} onChange={(e) => setMotivo(e.target.value)}
              placeholder="Ej. Captura duplicada" />
          )}
        </Campo>
        <ErrorApi error={error} />
      </div>
      <PieModal>
        <Boton variante="secundario" onClick={cerrar}>Cancelar</Boton>
        <Boton variante="peligro" cargando={enviando} onClick={confirmar}>Eliminar</Boton>
      </PieModal>
    </Modal>
  );
}
