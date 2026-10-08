import { useEffect, useState, type FormEvent } from "react";
import { Link, useParams } from "react-router";
import { useQuery } from "@tanstack/react-query";
import { useAuth } from "../auth/AuthContext";
import { CapturarMovimiento } from "../components/formularios/MovimientoForm";
import { CrearProyecto, DetalleProyecto } from "../components/formularios/ProyectoForm";
import { RegistrarSalida } from "../components/formularios/SalidaForm";
import { Icono } from "../components/Icono";
import { SelectorEmpresa, SelectorUsuario } from "../components/Selectores";
import { useToast } from "../components/Toast";
import {
  Aviso,
  Boton,
  Campo,
  Cargando,
  ErrorApi,
  Input,
  Insignia,
  Modal,
  Monto,
  PieModal,
  Tabla,
  Tarjeta,
  Td,
  Th,
  Vacio,
} from "../components/ui";
import { api } from "../lib/api";
import { SIN_EMPRESA, TEXTO_SIN_EMPRESA } from "../lib/empresa";
import { fecha, fechaHoraLocal, porcentaje } from "../lib/format";
import { useInvalidarDinero } from "../lib/invalidar";
import { useNombresEmpresa, useNombresUsuario } from "../lib/queries";
import type { MovimientoCliente, Pagina, Proyecto, Saldo, Terminal } from "../lib/types";
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

/** Asociar el cliente a una empresa o dejarlo sin empresa, mostrando antes cuánto saldo se mueve. */
function CambiarEmpresa({ cliente, abierto, onCerrar }: { cliente: Terminal; abierto: boolean; onCerrar: () => void }) {
  const avisar = useToast();
  const invalidar = useInvalidarDinero();
  const nombresEmpresa = useNombresEmpresa();
  const [destino, setDestino] = useState("");
  const [motivo, setMotivo] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [enviando, setEnviando] = useState(false);
  const saldo = useQuery({
    queryKey: ["saldo", "cambio-empresa", cliente.id],
    queryFn: () => api.get<Saldo>(`/terminales/${cliente.id}/saldo`),
    enabled: abierto,
  });

  useEffect(() => {
    if (abierto) {
      setDestino("");
      setMotivo("");
      setError(null);
    }
  }, [abierto]);

  const actual = cliente.empresa_id ? (nombresEmpresa.get(cliente.empresa_id) ?? "su empresa") : TEXTO_SIN_EMPRESA;
  const nuevo = destino === SIN_EMPRESA ? TEXTO_SIN_EMPRESA : (nombresEmpresa.get(destino) ?? "");
  const mismo = (destino === SIN_EMPRESA && !cliente.empresa_id) || destino === cliente.empresa_id;

  async function guardar(e: FormEvent) {
    e.preventDefault();
    setEnviando(true);
    setError(null);
    try {
      await api.post<Terminal>(`/terminales/${cliente.id}/empresa`, {
        empresa_id: destino === SIN_EMPRESA ? null : destino,
        motivo: motivo.trim() || null,
      });
      invalidar();
      avisar(`Cliente movido a «${nuevo}». Puedes revertirlo desde su historial.`);
      onCerrar();
    } catch (err) {
      setError(err);
    } finally {
      setEnviando(false);
    }
  }

  return (
    <Modal abierto={abierto} titulo="Cambiar empresa del cliente" onCerrar={onCerrar}
      descripcion={`Hoy está en: ${actual}. Se mueve con todos sus proyectos, entradas y salidas.`}>
      <form onSubmit={guardar} className="space-y-4">
        <Campo etiqueta="Nueva empresa" requerido>
          {(id) => <SelectorEmpresa id={id} required conSinEmpresa valor={destino} onCambiar={setDestino} />}
        </Campo>
        {destino && !mismo && saldo.data && (
          <div className="rounded-lg bg-slate-50 p-3 text-sm ring-1 ring-slate-200">
            <p className="font-medium text-slate-900">
              Se moverá un saldo de <Monto valor={saldo.data.saldo} resaltarNegativo /> de «{actual}» a «{nuevo}».
            </p>
            <p className="mt-1 text-xs text-slate-500">
              Entradas netas <Monto valor={saldo.data.ingresos_netos} /> · Salidas <Monto valor={saldo.data.salidas} /> ·
              Comisiones <Monto valor={saldo.data.comisiones} />
            </p>
          </div>
        )}
        {mismo && destino && <Aviso tono="info">El cliente ya está ahí.</Aviso>}
        <Campo etiqueta="Motivo" ayuda="Queda en la bitácora y en el historial del cliente.">
          {(id) => <Input id={id} maxLength={500} placeholder="Ej. El cliente pertenece a esta empresa" value={motivo} onChange={(e) => setMotivo(e.target.value)} />}
        </Campo>
        <ErrorApi error={error} />
        <PieModal>
          <Boton variante="secundario" onClick={onCerrar}>Cancelar</Boton>
          <Boton type="submit" cargando={enviando} disabled={!destino || mismo}>Mover cliente</Boton>
        </PieModal>
      </form>
    </Modal>
  );
}

/** Solo admin: cambiar el responsable de un cliente sin empresa. */
function ReasignarCliente({ cliente, abierto, onCerrar }: { cliente: Terminal; abierto: boolean; onCerrar: () => void }) {
  const avisar = useToast();
  const invalidar = useInvalidarDinero();
  const [usuarioId, setUsuarioId] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [enviando, setEnviando] = useState(false);

  async function guardar(e: FormEvent) {
    e.preventDefault();
    setEnviando(true);
    setError(null);
    try {
      await api.post(`/terminales/${cliente.id}/reasignar`, { usuario_id: usuarioId });
      invalidar();
      avisar("Cliente reasignado");
      onCerrar();
    } catch (err) {
      setError(err);
    } finally {
      setEnviando(false);
    }
  }

  return (
    <Modal abierto={abierto} titulo="Reasignar cliente" onCerrar={onCerrar}
      descripcion="El cliente sin empresa pasa a otro contador con sus proyectos, entradas y salidas.">
      <form onSubmit={guardar} className="space-y-4">
        <Campo etiqueta="Nuevo responsable" requerido>
          {(id) => <SelectorUsuario id={id} required rol="contador" valor={usuarioId} onCambiar={setUsuarioId} />}
        </Campo>
        <ErrorApi error={error} />
        <PieModal>
          <Boton variante="secundario" onClick={onCerrar}>Cancelar</Boton>
          <Boton type="submit" cargando={enviando}>Reasignar</Boton>
        </PieModal>
      </form>
    </Modal>
  );
}

/** Historial de cambios de empresa, con la opción de revertir el último. */
function HistorialEmpresa({ cliente }: { cliente: Terminal }) {
  const avisar = useToast();
  const invalidar = useInvalidarDinero();
  const [revirtiendo, setRevirtiendo] = useState<MovimientoCliente | null>(null);
  const [motivo, setMotivo] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [enviando, setEnviando] = useState(false);
  const historial = useQuery({
    queryKey: ["terminales", cliente.id, "historial-empresa", cliente.empresa_id],
    queryFn: () => api.get<MovimientoCliente[]>(`/terminales/${cliente.id}/historial-empresa`),
  });

  if (!historial.data?.length) return null;

  async function revertir() {
    setEnviando(true);
    setError(null);
    try {
      await api.post<Terminal>(`/terminales/${cliente.id}/revertir-movimiento`, { motivo: motivo.trim() || null });
      invalidar();
      avisar("Cambio revertido: el cliente volvió a donde estaba");
      setRevirtiendo(null);
      setMotivo("");
    } catch (err) {
      setError(err);
    } finally {
      setEnviando(false);
    }
  }

  return (
    <Tarjeta className="lg:col-span-3">
      <div className="px-5 py-4">
        <h2 className="text-base font-semibold text-slate-900">Historial de empresa</h2>
        <p className="text-xs text-slate-500">Cambios de empresa del cliente. El último se puede revertir si los saldos no cuadran.</p>
      </div>
      <Tabla>
        <thead>
          <tr>
            <Th>Fecha</Th>
            <Th>De</Th>
            <Th>A</Th>
            <Th derecha>Saldo movido</Th>
            <Th>Realizó</Th>
            <Th>Motivo</Th>
            <Th><span className="sr-only">Acciones</span></Th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {historial.data.map((h) => (
            <tr key={h.id}>
              <Td className="whitespace-nowrap">{fechaHoraLocal(h.fecha)}</Td>
              <Td>{h.empresa_antes}</Td>
              <Td className="font-medium text-slate-900">
                {h.empresa_despues} {h.es_reversion && <Insignia tono="aviso">Reversión</Insignia>}
              </Td>
              <Td derecha><Monto valor={h.saldo_movido} resaltarNegativo /></Td>
              <Td className="whitespace-nowrap">{h.realizado_por}</Td>
              <Td className="text-slate-500">{h.motivo ?? "—"}</Td>
              <Td className="text-right">
                {h.se_puede_revertir && (
                  <Boton variante="secundario" tamano="sm" onClick={() => { setRevirtiendo(h); setError(null); }}>
                    Revertir
                  </Boton>
                )}
              </Td>
            </tr>
          ))}
        </tbody>
      </Tabla>

      <Modal abierto={revirtiendo !== null} titulo="Revertir cambio de empresa" onCerrar={() => setRevirtiendo(null)}>
        {revirtiendo && (
          <div className="space-y-4">
            <p className="text-sm text-slate-600">
              El cliente volverá de <strong>«{revirtiendo.empresa_despues}»</strong> a{" "}
              <strong>«{revirtiendo.empresa_antes}»</strong>, con el mismo responsable que tenía. Sus proyectos,
              entradas y salidas regresan con él, así que los saldos de ambas quedan como estaban.
            </p>
            <Campo etiqueta="Motivo">
              {(id) => <Input id={id} maxLength={500} placeholder="Ej. Los saldos no cuadraban" value={motivo} onChange={(e) => setMotivo(e.target.value)} />}
            </Campo>
            <ErrorApi error={error} />
          </div>
        )}
        <PieModal>
          <Boton variante="secundario" onClick={() => setRevirtiendo(null)}>Cancelar</Boton>
          <Boton cargando={enviando} onClick={revertir}>Revertir</Boton>
        </PieModal>
      </Modal>
    </Tarjeta>
  );
}

export default function ClienteDetalle() {
  const { id = "" } = useParams();
  const { esAdmin } = useAuth();
  const avisar = useToast();
  const invalidar = useInvalidarDinero();
  const nombresEmpresa = useNombresEmpresa();
  const nombresUsuario = useNombresUsuario();
  const [renombrando, setRenombrando] = useState(false);
  const [cambiandoEmpresa, setCambiandoEmpresa] = useState(false);
  const [reasignando, setReasignando] = useState(false);
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
  const cadena = { empresaId: c.empresa_id ?? SIN_EMPRESA, clienteId: c.id };

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
      {c.empresa_id ? (
        <Link to={`/empresas/${c.empresa_id}`} className="mb-4 inline-flex items-center gap-1 text-sm font-medium text-slate-500 hover:text-slate-700">
          <Icono nombre="flecha" className="size-4" /> {nombresEmpresa.get(c.empresa_id) ?? "Empresa"}
        </Link>
      ) : (
        <Link to="/clientes" className="mb-4 inline-flex items-center gap-1 text-sm font-medium text-slate-500 hover:text-slate-700">
          <Icono nombre="flecha" className="size-4" /> Clientes
        </Link>
      )}

      <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-sm font-medium text-slate-500">Cliente</p>
          <h1 className="flex flex-wrap items-center gap-3 text-2xl font-semibold tracking-tight text-slate-900">
            {c.identificador_terminal}
            {c.activa ? <Insignia tono="exito">Activo</Insignia> : <Insignia>Inactivo</Insignia>}
            {!c.empresa_id && <Insignia tono="info">{TEXTO_SIN_EMPRESA}</Insignia>}
          </h1>
          <p className="text-sm text-slate-500">
            Registrado el {fecha(c.fecha_registro)}
            {esAdmin && <> · Responsable: {nombresUsuario.get(c.usuario_id) ?? "—"}</>}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Boton variante="secundario" onClick={() => setRenombrando(true)}>
            <Icono nombre="lapiz" className="size-4" /> Editar
          </Boton>
          <Boton variante="secundario" onClick={() => setCambiandoEmpresa(true)}>Cambiar empresa</Boton>
          {esAdmin && !c.empresa_id && <Boton variante="secundario" onClick={() => setReasignando(true)}>Reasignar</Boton>}
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
                      <Link to={`/reportes?r=constructor&empresa_id=${cadena.empresaId}&proyecto_id=${p.id}&agrupar=detalle`}
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

        <HistorialEmpresa cliente={c} />
      </div>

      <Renombrar cliente={c} abierto={renombrando} onCerrar={() => setRenombrando(false)} />
      <CambiarEmpresa cliente={c} abierto={cambiandoEmpresa} onCerrar={() => setCambiandoEmpresa(false)} />
      {esAdmin && <ReasignarCliente cliente={c} abierto={reasignando} onCerrar={() => setReasignando(false)} />}
      <CrearProyecto abierto={creandoProyecto} onCerrar={() => setCreandoProyecto(false)} terminalId={c.id}
        cliente={c.identificador_terminal} />
      <DetalleProyecto proyecto={proyecto} onCerrar={() => setProyecto(null)} />
      <CapturarMovimiento abierto={capturando} onCerrar={() => setCapturando(false)} inicial={cadena} />
      <RegistrarSalida abierto={registrandoSalida} onCerrar={() => setRegistrandoSalida(false)} inicial={cadena} />
    </>
  );
}
