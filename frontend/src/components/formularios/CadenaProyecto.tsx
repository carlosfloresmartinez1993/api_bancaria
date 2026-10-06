import { useEffect } from "react";
import { useTerminalesCatalogo } from "../../lib/queries";
import { SelectorCliente, SelectorEmpresa, SelectorProyecto } from "../Selectores";
import { Campo } from "../ui";

export interface Cadena {
  empresaId: string;
  clienteId: string;
  proyectoId: string;
}

export const CADENA_VACIA: Cadena = { empresaId: "", clienteId: "", proyectoId: "" };

/**
 * Elegir empresa → cliente → proyecto en cascada. Al cambiar un nivel se limpian los de abajo,
 * y si un nivel tiene una sola opción activa se elige sola.
 */
export function CadenaProyecto({ valor, onCambiar }: { valor: Cadena; onCambiar: (c: Cadena) => void }) {
  const { data: clientes } = useTerminalesCatalogo(valor.empresaId || undefined);
  const activos = (clientes ?? []).filter((c) => c.activa);
  const unicoCliente = valor.empresaId && activos.length === 1 ? activos[0].id : null;

  useEffect(() => {
    if (unicoCliente && !valor.clienteId) onCambiar({ ...valor, clienteId: unicoCliente, proyectoId: "" });
  }, [unicoCliente, valor, onCambiar]);

  return (
    <div className="grid gap-4 sm:grid-cols-3">
      <Campo etiqueta="Empresa" requerido>
        {(id) => (
          <SelectorEmpresa id={id} required valor={valor.empresaId}
            onCambiar={(empresaId) => onCambiar({ empresaId, clienteId: "", proyectoId: "" })} />
        )}
      </Campo>
      <Campo etiqueta="Cliente" requerido>
        {(id) => (
          <SelectorCliente id={id} required soloActivos valor={valor.clienteId} empresaId={valor.empresaId}
            disabled={!valor.empresaId}
            onCambiar={(clienteId) => onCambiar({ ...valor, clienteId, proyectoId: "" })} />
        )}
      </Campo>
      <Campo etiqueta="Proyecto" requerido>
        {(id) => (
          <SelectorProyecto id={id} required soloActivos autoSeleccionar valor={valor.proyectoId}
            terminalId={valor.clienteId || undefined} disabled={!valor.clienteId}
            onCambiar={(proyectoId) => onCambiar({ ...valor, proyectoId })} />
        )}
      </Campo>
    </div>
  );
}
