import { useEffect, useState, type FormEvent } from "react";
import { useNavigate } from "react-router";
import { useAuth } from "../../auth/AuthContext";
import { api } from "../../lib/api";
import { SIN_EMPRESA } from "../../lib/empresa";
import { useInvalidarDinero } from "../../lib/invalidar";
import type { Terminal } from "../../lib/types";
import { SelectorEmpresa, SelectorUsuario } from "../Selectores";
import { useToast } from "../Toast";
import { Boton, Campo, ErrorApi, Input, Modal, PieModal } from "../ui";

/** Alta de un cliente (terminal), con o sin empresa. Después se abre su detalle para agregarle proyectos. */
export function CrearCliente({
  abierto,
  onCerrar,
  empresaInicial = "",
}: {
  abierto: boolean;
  onCerrar: () => void;
  empresaInicial?: string;
}) {
  const { esAdmin, usuario } = useAuth();
  const avisar = useToast();
  const invalidar = useInvalidarDinero();
  const navigate = useNavigate();
  const [empresaId, setEmpresaId] = useState(empresaInicial);
  const [identificador, setIdentificador] = useState("");
  const [responsable, setResponsable] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [enviando, setEnviando] = useState(false);

  useEffect(() => {
    if (abierto) {
      setEmpresaId(empresaInicial);
      setIdentificador("");
      setResponsable("");
      setError(null);
    }
  }, [abierto, empresaInicial]);

  const sinEmpresa = empresaId === SIN_EMPRESA;

  async function guardar(e: FormEvent) {
    e.preventDefault();
    setEnviando(true);
    setError(null);
    try {
      const cliente = await api.post<Terminal>("/terminales", {
        empresa_id: sinEmpresa ? null : empresaId,
        identificador_terminal: identificador.trim(),
        usuario_id: sinEmpresa && esAdmin && responsable ? responsable : undefined,
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
    <Modal abierto={abierto} titulo="Nuevo cliente" descripcion="Un cliente es una terminal; puede pertenecer a una empresa o no. Sus proyectos llevan la comisión."
      onCerrar={onCerrar}>
      <form onSubmit={guardar} className="space-y-4">
        <Campo etiqueta="Empresa" requerido ayuda="Elige «Sin empresa» si el cliente no pertenece a ninguna; se le puede asignar una después.">
          {(id) => <SelectorEmpresa id={id} required conSinEmpresa valor={empresaId} onCambiar={setEmpresaId} />}
        </Campo>
        <Campo etiqueta="Cliente (número o nombre de la terminal)" requerido
          ayuda={sinEmpresa ? "No se puede repetir entre tus clientes sin empresa." : "Único dentro de la empresa. Ej. 1234"}>
          {(id) => <Input id={id} required maxLength={100} value={identificador} onChange={(e) => setIdentificador(e.target.value)} />}
        </Campo>
        {sinEmpresa && esAdmin && (
          <Campo etiqueta="Responsable" ayuda="Contador que verá y operará este cliente. Si lo dejas vacío, quedas tú.">
            {(id) => <SelectorUsuario id={id} valor={responsable} onCambiar={setResponsable} rol="contador"
              vacio={`${usuario?.nombre} ${usuario?.apellidos} (yo)`} />}
          </Campo>
        )}
        <ErrorApi error={error} />
        <PieModal>
          <Boton variante="secundario" onClick={onCerrar}>Cancelar</Boton>
          <Boton type="submit" cargando={enviando}>Registrar cliente</Boton>
        </PieModal>
      </form>
    </Modal>
  );
}
