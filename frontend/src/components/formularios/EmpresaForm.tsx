import { useEffect, useState, type FormEvent } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router";
import { useAuth } from "../../auth/AuthContext";
import { api } from "../../lib/api";
import type { Empresa } from "../../lib/types";
import { SelectorUsuario } from "../Selectores";
import { useToast } from "../Toast";
import { Boton, Campo, ErrorApi, Input, Modal, PieModal } from "../ui";

interface Datos {
  nombre: string;
  csf: string;
  banco: string;
  numero_cuenta: string;
  clabe: string;
}

const VACIO: Datos = { nombre: "", csf: "", banco: "", numero_cuenta: "", clabe: "" };

/** Alta (empresa = null) o edición de una empresa. */
export function EmpresaForm({ abierto, empresa, onCerrar }: { abierto: boolean; empresa?: Empresa | null; onCerrar: () => void }) {
  const { esAdmin, usuario } = useAuth();
  const avisar = useToast();
  const qc = useQueryClient();
  const navigate = useNavigate();
  const [datos, setDatos] = useState<Datos>(VACIO);
  const [propietario, setPropietario] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [enviando, setEnviando] = useState(false);

  useEffect(() => {
    if (abierto) {
      setDatos(
        empresa
          ? { nombre: empresa.nombre, csf: empresa.csf, banco: empresa.banco, numero_cuenta: empresa.numero_cuenta, clabe: empresa.clabe ?? "" }
          : VACIO,
      );
      setPropietario("");
      setError(null);
    }
  }, [abierto, empresa]);

  const campo = (k: keyof Datos) => ({
    value: datos[k],
    onChange: (e: { target: { value: string } }) => setDatos((d) => ({ ...d, [k]: e.target.value })),
  });

  async function guardar(e: FormEvent) {
    e.preventDefault();
    setEnviando(true);
    setError(null);
    const cuerpo = {
      nombre: datos.nombre.trim(),
      csf: datos.csf.trim(),
      banco: datos.banco.trim(),
      numero_cuenta: datos.numero_cuenta.trim(),
      clabe: datos.clabe.trim() || null,
    };
    try {
      if (empresa) {
        await api.patch<Empresa>(`/empresas/${empresa.id}`, cuerpo);
        avisar("Empresa actualizada");
      } else {
        const nueva = await api.post<Empresa>("/empresas", {
          ...cuerpo,
          usuario_id: esAdmin && propietario ? propietario : undefined,
        });
        avisar("Empresa registrada");
        navigate(`/empresas/${nueva.id}`);
      }
      qc.invalidateQueries({ queryKey: ["empresas"] });
      qc.invalidateQueries({ queryKey: ["reporte"] });
      onCerrar();
    } catch (err) {
      setError(err);
    } finally {
      setEnviando(false);
    }
  }

  return (
    <Modal abierto={abierto} titulo={empresa ? "Editar empresa" : "Nueva empresa"} onCerrar={onCerrar}>
      <form onSubmit={guardar} className="space-y-4">
        <Campo etiqueta="Nombre" requerido>
          {(id) => <Input id={id} required maxLength={200} {...campo("nombre")} />}
        </Campo>
        <Campo etiqueta="Constancia de situación fiscal (CSF)" requerido ayuda="RFC o identificador de la constancia.">
          {(id) => <Input id={id} required maxLength={100} {...campo("csf")} />}
        </Campo>
        <div className="grid gap-4 sm:grid-cols-2">
          <Campo etiqueta="Banco" requerido>
            {(id) => <Input id={id} required maxLength={100} placeholder="Ej. BBVA" {...campo("banco")} />}
          </Campo>
          <Campo etiqueta="Número de cuenta" requerido>
            {(id) => <Input id={id} required maxLength={30} inputMode="numeric" {...campo("numero_cuenta")} />}
          </Campo>
        </div>
        <Campo etiqueta="CLABE" ayuda="18 dígitos (opcional).">
          {(id) => <Input id={id} pattern="\d{18}" maxLength={18} inputMode="numeric" title="La CLABE tiene 18 dígitos" {...campo("clabe")} />}
        </Campo>
        {esAdmin && !empresa && (
          <Campo etiqueta="Registrar a nombre de" ayuda="Si lo dejas vacío, la empresa queda a tu nombre.">
            {(id) => <SelectorUsuario id={id} valor={propietario} onCambiar={setPropietario} rol="contador"
              vacio={`${usuario?.nombre} ${usuario?.apellidos} (yo)`} />}
          </Campo>
        )}
        <ErrorApi error={error} />
        <PieModal>
          <Boton variante="secundario" onClick={onCerrar}>Cancelar</Boton>
          <Boton type="submit" cargando={enviando}>{empresa ? "Guardar cambios" : "Registrar empresa"}</Boton>
        </PieModal>
      </form>
    </Modal>
  );
}
