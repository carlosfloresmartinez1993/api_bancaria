import { useState, type FormEvent } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useToast } from "../components/Toast";
import { Boton, Cargando, EncabezadoPagina, ErrorApi, Input, Insignia, Tabla, Tarjeta, Td, Th } from "../components/ui";
import { api } from "../lib/api";
import { fecha } from "../lib/format";
import { useMetodosPago } from "../lib/queries";
import type { MetodoPago } from "../lib/types";

export default function MetodosPago() {
  const qc = useQueryClient();
  const avisar = useToast();
  const { data, isLoading, error } = useMetodosPago(true);
  const [nuevo, setNuevo] = useState("");
  const [errorAlta, setErrorAlta] = useState<unknown>(null);
  const [enviando, setEnviando] = useState(false);
  const [editando, setEditando] = useState<{ id: string; nombre: string } | null>(null);

  const refrescar = () => qc.invalidateQueries({ queryKey: ["metodos-pago"] });

  async function agregar(e: FormEvent) {
    e.preventDefault();
    setEnviando(true);
    setErrorAlta(null);
    try {
      await api.post<MetodoPago>("/metodos-pago", { nombre: nuevo.trim() });
      avisar(`Método «${nuevo.trim()}» agregado`);
      setNuevo("");
      refrescar();
    } catch (err) {
      setErrorAlta(err);
    } finally {
      setEnviando(false);
    }
  }

  async function actualizar(m: MetodoPago, cambios: Partial<Pick<MetodoPago, "nombre" | "activo">>) {
    try {
      await api.patch<MetodoPago>(`/metodos-pago/${m.id}`, cambios);
      setEditando(null);
      refrescar();
      avisar("activo" in cambios ? (cambios.activo ? "Método activado" : "Método desactivado") : "Método actualizado");
    } catch (err) {
      avisar((err as Error).message, "error");
    }
  }

  return (
    <>
      <EncabezadoPagina
        titulo="Métodos de pago"
        descripcion="Se usan en las entradas y en las salidas. No se borran: si ya no se usan, se desactivan."
      />

      <Tarjeta className="mb-4 p-4">
        <form onSubmit={agregar} className="flex flex-col gap-3 sm:flex-row sm:items-end">
          <div className="flex-1">
            <label htmlFor="nuevo-metodo" className="mb-1 block text-sm font-medium text-slate-700">Nuevo método de pago</label>
            <Input id="nuevo-metodo" required maxLength={50} placeholder="Ej. Cheque, Tarjeta, PayPal"
              value={nuevo} onChange={(e) => setNuevo(e.target.value)} />
          </div>
          <Boton type="submit" cargando={enviando}>Agregar</Boton>
        </form>
        <ErrorApi error={errorAlta} className="mt-3" />
      </Tarjeta>

      <ErrorApi error={error} className="mb-4" />

      <Tarjeta>
        {isLoading ? (
          <Cargando />
        ) : (
          <Tabla>
            <thead>
              <tr>
                <Th>Método</Th>
                <Th>Estado</Th>
                <Th>Alta</Th>
                <Th><span className="sr-only">Acciones</span></Th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {data?.map((m) => (
                <tr key={m.id} className="hover:bg-slate-50">
                  <Td className="font-medium text-slate-900">
                    {editando?.id === m.id ? (
                      <form className="flex gap-2" onSubmit={(e) => { e.preventDefault(); actualizar(m, { nombre: editando.nombre.trim() }); }}>
                        <Input autoFocus required maxLength={50} value={editando.nombre}
                          onChange={(e) => setEditando({ id: m.id, nombre: e.target.value })} />
                        <Boton type="submit" tamano="sm">Guardar</Boton>
                        <Boton variante="fantasma" tamano="sm" onClick={() => setEditando(null)}>Cancelar</Boton>
                      </form>
                    ) : (
                      m.nombre
                    )}
                  </Td>
                  <Td>{m.activo ? <Insignia tono="exito">Activo</Insignia> : <Insignia>Inactivo</Insignia>}</Td>
                  <Td className="whitespace-nowrap">{fecha(m.fecha_registro)}</Td>
                  <Td className="whitespace-nowrap text-right">
                    {editando?.id !== m.id && (
                      <>
                        <Boton variante="fantasma" tamano="sm" onClick={() => setEditando({ id: m.id, nombre: m.nombre })}>Renombrar</Boton>
                        <Boton variante="fantasma" tamano="sm" onClick={() => actualizar(m, { activo: !m.activo })}
                          className={m.activo ? "hover:text-rose-600" : "text-teal-700"}>
                          {m.activo ? "Desactivar" : "Activar"}
                        </Boton>
                      </>
                    )}
                  </Td>
                </tr>
              ))}
            </tbody>
          </Tabla>
        )}
      </Tarjeta>
    </>
  );
}
