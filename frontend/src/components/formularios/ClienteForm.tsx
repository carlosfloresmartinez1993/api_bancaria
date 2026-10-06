import { useEffect, useState, type FormEvent } from "react";
import { useNavigate } from "react-router";
import { api } from "../../lib/api";
import { useInvalidarDinero } from "../../lib/invalidar";
import type { Terminal } from "../../lib/types";
import { SelectorEmpresa } from "../Selectores";
import { useToast } from "../Toast";
import { Boton, Campo, ErrorApi, Input, Modal, PieModal } from "../ui";

/** Alta de un cliente (terminal). Después se abre su detalle para agregarle proyectos. */
export function CrearCliente({
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
  const navigate = useNavigate();
  const [empresaId, setEmpresaId] = useState(empresaInicial);
  const [identificador, setIdentificador] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [enviando, setEnviando] = useState(false);

  useEffect(() => {
    if (abierto) {
      setEmpresaId(empresaInicial);
      setIdentificador("");
      setError(null);
    }
  }, [abierto, empresaInicial]);

  async function guardar(e: FormEvent) {
    e.preventDefault();
    setEnviando(true);
    setError(null);
    try {
      const cliente = await api.post<Terminal>("/terminales", {
        empresa_id: empresaId,
        identificador_terminal: identificador.trim(),
      });
      invalidar();
      avisar("Cliente registrado. Ahora agrégale sus proyectos.");
      onCerrar();
      navigate(`/clientes/${cliente.id}`);
    } catch (err) {
      setError(err);
    } finally {
      setEnviando(false);
    }
  }

  return (
    <Modal abierto={abierto} titulo="Nuevo cliente" descripcion="Un cliente es una terminal de la empresa; sus proyectos llevan la comisión."
      onCerrar={onCerrar}>
      <form onSubmit={guardar} className="space-y-4">
        <Campo etiqueta="Empresa" requerido>
          {(id) => <SelectorEmpresa id={id} required valor={empresaId} onCambiar={setEmpresaId} />}
        </Campo>
        <Campo etiqueta="Cliente (número o nombre de la terminal)" requerido ayuda="Único dentro de la empresa. Ej. 1234">
          {(id) => <Input id={id} required maxLength={100} value={identificador} onChange={(e) => setIdentificador(e.target.value)} />}
        </Campo>
        <ErrorApi error={error} />
        <PieModal>
          <Boton variante="secundario" onClick={onCerrar}>Cancelar</Boton>
          <Boton type="submit" cargando={enviando}>Registrar cliente</Boton>
        </PieModal>
      </form>
    </Modal>
  );
}
