import { useEffect, useState, type FormEvent } from "react";
import { Link, useParams } from "react-router";
import { useQuery } from "@tanstack/react-query";
import { CapturarMovimiento } from "../components/formularios/MovimientoForm";
import { CrearProyecto, DetalleProyecto } from "../components/formularios/ProyectoForm";
import { RegistrarSalida } from "../components/formularios/SalidaForm";
import { Icono } from "../components/Icono";
import { useToast } from "../components/Toast";
import { Boton, Campo, Cargando, ErrorApi, Input, Insignia, Modal, PieModal, Tabla, Tarjeta, Td, Th, Vacio } from "../components/ui";
import { api } from "../lib/api";
import { fecha, porcentaje } from "../lib/format";
import { useInvalidarDinero } from "../lib/invalidar";
import { useNombresEmpresa } from "../lib/queries";
import type { Pagina, Proyecto, Terminal } from "../lib/types";
import { TarjetaSaldo } from "./EmpresaDetalle";

function Renombrar({ cliente, abierto, onCerrar }: { cliente: Terminal; abierto: boolean; onCerrar: () => void }) {
  const avisar = useToast();
  const invalidar = useInvalidarDinero();
  const [identificador, setIdentificador] = useState(cliente.identificador_terminal);
  const [error, setError] = useState<unknown>(null);
  const [enviando, setEnviando] = useState(false);

  useEffect(() => {
    if (abierto) {
      setIdentificador(cliente.identificador_terminal);
      setError(null);
    }
  }, [abierto, cliente]);

  async function guardar(e: FormEvent) {
    e.preventDefault();
    setEnviando(true);
    setError(null);
    try {
      await api.patch(`/terminales/${cliente.id}`, { identificador_terminal: identificador.trim() });
      invalidar();
      avisar("Cliente actualizado");
      onCerrar();
    } catch (err) {
      setError(err);
    } finally {
      setEnviando(false);
    }
  }

  return (
    <Modal abierto={abierto} titulo="Editar cliente" onCerrar={onCerrar}>
      <form onSubmit={guardar} className="space-y-4">
        <Campo etiqueta="Cliente (número o nombre de la terminal)" requerido>
          {(id) => <Input id={id} required maxLength={100} value={identificador} onChange={(e) => setIdentificador(e.target.value)} />}
        </Campo>
        <ErrorApi error={error} />
        <PieModal>
          <Boton variante="secundario" onClick={onCerrar}>Cancelar</Boton>
          <Boton type="submit" cargando={enviando}>Guardar</Boton>
        </PieModal>
      </form>
    </Modal>
  );
}

export default function ClienteDetalle() {
  const { id = "" } = useParams();
  const avisar = useToast();
  const invalidar = useInvalidarDinero();
  const nombresEmpresa = useNombresEmpresa();
  const [renombrando, setRenombrando] = useState(false);
  const [creandoProyecto, setCreandoProyecto] = useState(false);
  const [proyecto, setProyecto] = useState<Proyecto | null>(null);
  const [capturando, setCapturando] = useState(false);
  const [registrandoSalida, setRegistrandoSalida] = useState(false);
  const [errorEstado, setErrorEstado] = useState<unknown>(null);

  const cliente = useQuery({
    queryKey: ["terminales", id],
    queryFn: () => api.get<Terminal>(`/terminales/${id}`),
  });
  const proyectos = useQuery({
    queryKey: ["proyectos", "cliente", id],
    queryFn: () => api.get<Pagina<Proyecto>>("/proyectos", { terminal_id: id, limit: 500 }),
  });

  if (cliente.isLoading) return <Cargando />;
  if (cliente.error || !cliente.data) {
    return (
      <div className="space-y-4">
        <ErrorApi error={cliente.error ?? new Error("Cliente no encontrado")} />
        <Link to="/clientes" className="text-sm font-medium text-teal-700">← Volver a clientes</Link>
      </div>
    );
  }
  const c = cliente.data;

  async function alternarEstado() {
    setErrorEstado(null);
    try {
      const t = await api.post<Terminal>(`/terminales/${c.id}/${c.activa ? "desactivar" : "activar"}`);
      invalidar();
      avisar(t.activa ? "Cliente activado" : "Cliente desactivado");
    } catch (err) {
      setErrorEstado(err);
    }
  }

  return (
    <>
      <Link to={`/empresas/${c.empresa_id}`} className="mb-4 inline-flex items-center gap-1 text-sm font-medium text-slate-500 hover:text-slate-700">
        <Icono nombre="flecha" className="size-4" /> {nombresEmpresa.get(c.empresa_id) ?? "Empresa"}
      </Link>

      <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-sm font-medium text-slate-500">Cliente</p>
          <h1 className="flex items-center gap-3 text-2xl font-semibold tracking-tight text-slate-900">
            {c.identificador_terminal}
            {c.activa ? <Insignia tono="exito">Activo</Insignia> : <Insignia>Inactivo</Insignia>}
          </h1>
          <p className="text-sm text-slate-500">Registrado el {fecha(c.fecha_registro)}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Boton variante="secundario" onClick={() => setRenombrando(true)}>
            <Icono nombre="lapiz" className="size-4" /> Editar
          </Boton>
          <Boton variante="secundario" onClick={alternarEstado}>{c.activa ? "Desactivar" : "Activar"}</Boton>
          <Boton variante="secundario" onClick={() => setRegistrandoSalida(true)}>Registrar salida</Boton>
          <Boton onClick={() => setCapturando(true)} disabled={!c.activa}>
            <Icono nombre="mas" className="size-4" /> Capturar entrada
          </Boton>
        </div>
      </div>
      <ErrorApi error={errorEstado} className="mb-4" />
      {!c.activa && (
        <p className="mb-4 rounded-lg bg-slate-100 p-3 text-sm text-slate-600">
          Este cliente está inactivo: no acepta entradas nuevas en ninguno de sus proyectos. Su historial se conserva.
        </p>
      )}

      <div className="grid gap-6 lg:grid-cols-3">
        <Tarjeta className="lg:col-span-2">
          <div className="flex items-center justify-between px-5 py-4">
            <div>
              <h2 className="text-base font-semibold text-slate-900">Proyectos</h2>
              <p className="text-xs text-slate-500">Cada proyecto tiene su propio % de comisión.</p>
            </div>
            <Boton variante="secundario" tamano="sm" onClick={() => setCreandoProyecto(true)}>
              <Icono nombre="mas" className="size-4" /> Nuevo proyecto
            </Boton>
          </div>
          {proyectos.isLoading ? (
            <Cargando />
          ) : !proyectos.data?.items.length ? (
            <Vacio titulo="Sin proyectos" descripcion="Agrega al menos un proyecto con su % para poder capturar entradas de este cliente."
              accion={<Boton onClick={() => setCreandoProyecto(true)}>Agregar el primero</Boton>} />
          ) : (
            <Tabla>
              <thead>
                <tr>
                  <Th>Proyecto</Th>
                  <Th derecha>Comisión vigente</Th>
                  <Th>Estado</Th>
                  <Th><span className="sr-only">Acciones</span></Th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {proyectos.data.items.map((p) => (
                  <tr key={p.id} className="cursor-pointer hover:bg-slate-50" onClick={() => setProyecto(p)}>
                    <Td className="font-medium text-slate-900">{p.nombre}</Td>
                    <Td derecha className="font-medium">{porcentaje(p.porcentaje_vigente)}</Td>
                    <Td>{p.activo ? <Insignia tono="exito">Activo</Insignia> : <Insignia>Inactivo</Insignia>}</Td>
                    <Td className="whitespace-nowrap text-right">
                      <Link to={`/reportes?r=constructor&empresa_id=${c.empresa_id}&proyecto_id=${p.id}&agrupar=detalle`}
                        onClick={(e) => e.stopPropagation()} className="mr-3 text-xs font-medium text-teal-700 hover:text-teal-800">
                        Reporte
                      </Link>
                      <Boton variante="fantasma" tamano="sm">Detalle</Boton>
                    </Td>
                  </tr>
                ))}
              </tbody>
            </Tabla>
          )}
        </Tarjeta>

        <TarjetaSaldo ruta={`/terminales/${c.id}/saldo`} claveCache={`cliente-${c.id}`} />
      </div>

      <Renombrar cliente={c} abierto={renombrando} onCerrar={() => setRenombrando(false)} />
      <CrearProyecto abierto={creandoProyecto} onCerrar={() => setCreandoProyecto(false)} terminalId={c.id}
        cliente={c.identificador_terminal} />
      <DetalleProyecto proyecto={proyecto} onCerrar={() => setProyecto(null)} />
      <CapturarMovimiento abierto={capturando} onCerrar={() => setCapturando(false)}
        inicial={{ empresaId: c.empresa_id, clienteId: c.id }} />
      <RegistrarSalida abierto={registrandoSalida} onCerrar={() => setRegistrandoSalida(false)}
        inicial={{ empresaId: c.empresa_id, clienteId: c.id }} />
    </>
  );
}
