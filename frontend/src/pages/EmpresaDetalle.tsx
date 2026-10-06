import { useState, type FormEvent, type ReactNode } from "react";
import { Link, useNavigate, useParams } from "react-router";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "../auth/AuthContext";
import { CrearCliente } from "../components/formularios/ClienteForm";
import { EmpresaForm } from "../components/formularios/EmpresaForm";
import { CapturarMovimiento } from "../components/formularios/MovimientoForm";
import { RegistrarSalida } from "../components/formularios/SalidaForm";
import { Icono } from "../components/Icono";
import { SelectorUsuario } from "../components/Selectores";
import { useToast } from "../components/Toast";
import {
  Boton,
  Campo,
  Cargando,
  ErrorApi,
  Iniciales,
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
import { fecha, hoyISO } from "../lib/format";
import { useNombresUsuario } from "../lib/queries";
import type { Empresa, Pagina, Saldo, Terminal } from "../lib/types";

function Dato({ etiqueta, children }: { etiqueta: string; children: ReactNode }) {
  return (
    <div>
      <dt className="text-xs font-medium text-slate-500">{etiqueta}</dt>
      <dd className="mt-0.5 text-sm text-slate-900">{children}</dd>
    </div>
  );
}

/** Tarjeta de saldo a una fecha; sirve para empresa, cliente o proyecto según la ruta. */
export function TarjetaSaldo({ ruta, claveCache }: { ruta: string; claveCache: string }) {
  const [alDia, setAlDia] = useState(hoyISO());
  const { data, error } = useQuery({
    queryKey: ["saldo", claveCache, alDia],
    queryFn: () => api.get<Saldo>(ruta, { al_dia: alDia }),
  });
  return (
    <Tarjeta className="p-5">
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-base font-semibold text-slate-900">Saldo</h2>
        <Input type="date" aria-label="Saldo al día" className="w-auto" value={alDia} max={hoyISO()}
          onChange={(e) => setAlDia(e.target.value || hoyISO())} />
      </div>
      <ErrorApi error={error} className="mt-3" />
      <p className="mt-4 text-3xl font-semibold tracking-tight">
        <Monto valor={data?.saldo ?? null} resaltarNegativo />
      </p>
      <dl className="mt-4 space-y-2 border-t border-slate-100 pt-4 text-sm">
        <div className="flex justify-between">
          <dt className="text-slate-500">Entradas brutas</dt>
          <dd className="font-medium"><Monto valor={data?.ingresos_brutos ?? null} /></dd>
        </div>
        <div className="flex justify-between">
          <dt className="text-slate-500">Comisiones</dt>
          <dd className="font-medium">− <Monto valor={data?.comisiones ?? null} /></dd>
        </div>
        <div className="flex justify-between">
          <dt className="text-slate-500">Entradas netas</dt>
          <dd className="font-medium"><Monto valor={data?.ingresos_netos ?? null} /></dd>
        </div>
        <div className="flex justify-between">
          <dt className="text-slate-500">Salidas</dt>
          <dd className="font-medium">− <Monto valor={data?.salidas ?? null} /></dd>
        </div>
      </dl>
      {data && Number(data.saldo) < 0 && (
        <p className="mt-3 rounded-md bg-amber-50 p-2 text-xs text-amber-900">Saldo negativo: probablemente falta capturar alguna entrada.</p>
      )}
    </Tarjeta>
  );
}

function Reasignar({ empresa, abierto, onCerrar }: { empresa: Empresa; abierto: boolean; onCerrar: () => void }) {
  const qc = useQueryClient();
  const avisar = useToast();
  const [usuarioId, setUsuarioId] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [enviando, setEnviando] = useState(false);

  async function guardar(e: FormEvent) {
    e.preventDefault();
    setEnviando(true);
    setError(null);
    try {
      await api.post(`/empresas/${empresa.id}/reasignar`, { usuario_id: usuarioId });
      await qc.invalidateQueries({ queryKey: ["empresas"] });
      avisar("Empresa reasignada");
      onCerrar();
    } catch (err) {
      setError(err);
    } finally {
      setEnviando(false);
    }
  }

  return (
    <Modal abierto={abierto} titulo="Reasignar empresa" onCerrar={onCerrar}
      descripcion="La empresa pasa a otro contador con sus clientes, proyectos, entradas y salidas.">
      <form onSubmit={guardar} className="space-y-4">
        <Campo etiqueta="Nuevo contador" requerido>
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

export default function EmpresaDetalle() {
  const { id = "" } = useParams();
  const { esAdmin } = useAuth();
  const navigate = useNavigate();
  const nombresUsuario = useNombresUsuario();
  const [editando, setEditando] = useState(false);
  const [reasignando, setReasignando] = useState(false);
  const [creandoCliente, setCreandoCliente] = useState(false);
  const [capturando, setCapturando] = useState(false);
  const [registrandoSalida, setRegistrandoSalida] = useState(false);

  const empresa = useQuery({
    queryKey: ["empresas", id],
    queryFn: () => api.get<Empresa>(`/empresas/${id}`),
  });
  const clientes = useQuery({
    queryKey: ["terminales", "empresa", id],
    queryFn: () => api.get<Pagina<Terminal>>("/terminales", { empresa_id: id, limit: 500 }),
  });

  if (empresa.isLoading) return <Cargando />;
  if (empresa.error || !empresa.data) {
    return (
      <div className="space-y-4">
        <ErrorApi error={empresa.error ?? new Error("Empresa no encontrada")} />
        <Link to="/empresas" className="text-sm font-medium text-teal-700">← Volver a empresas</Link>
      </div>
    );
  }
  const e = empresa.data;

  return (
    <>
      <Link to="/empresas" className="mb-4 inline-flex items-center gap-1 text-sm font-medium text-slate-500 hover:text-slate-700">
        <Icono nombre="flecha" className="size-4" /> Empresas
      </Link>

      <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-4">
          <Iniciales nombre={e.nombre} className="size-16" />
          <div>
            <h1 className="text-2xl font-semibold tracking-tight text-slate-900">{e.nombre}</h1>
            {e.csf && <p className="text-sm text-slate-500">{e.csf}</p>}
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          {esAdmin && <Boton variante="secundario" onClick={() => setReasignando(true)}>Reasignar</Boton>}
          <Boton variante="secundario" onClick={() => setEditando(true)}>
            <Icono nombre="lapiz" className="size-4" /> Editar
          </Boton>
          <Boton variante="secundario" onClick={() => setRegistrandoSalida(true)}>Registrar salida</Boton>
          <Boton onClick={() => setCapturando(true)}>
            <Icono nombre="mas" className="size-4" /> Capturar entrada
          </Boton>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <Tarjeta className="p-5">
            <h2 className="mb-4 text-base font-semibold text-slate-900">Datos de la empresa</h2>
            <dl className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              <Dato etiqueta="Banco">{e.banco ?? "—"}</Dato>
              <Dato etiqueta="Número de cuenta"><span className="tabular-nums">{e.numero_cuenta ?? "—"}</span></Dato>
              <Dato etiqueta="CLABE"><span className="tabular-nums">{e.clabe ?? "—"}</span></Dato>
              {esAdmin && <Dato etiqueta="Contador">{nombresUsuario.get(e.usuario_id) ?? "—"}</Dato>}
              <Dato etiqueta="Registrada">{fecha(e.fecha_registro)}</Dato>
            </dl>
            <div className="mt-5 flex flex-wrap gap-4 border-t border-slate-100 pt-4 text-sm">
              <Link to={`/movimientos?empresa_id=${e.id}`} className="font-medium text-teal-700 hover:text-teal-800">Ver entradas →</Link>
              <Link to={`/salidas?empresa_id=${e.id}`} className="font-medium text-teal-700 hover:text-teal-800">Ver salidas →</Link>
              <Link to={`/reportes?r=constructor&empresa_id=${e.id}`} className="font-medium text-teal-700 hover:text-teal-800">Reporte →</Link>
              <Link to={`/reportes?r=estado-cuenta&empresa_id=${e.id}`} className="font-medium text-teal-700 hover:text-teal-800">Estado de cuenta →</Link>
            </div>
          </Tarjeta>

          <Tarjeta>
            <div className="flex items-center justify-between px-5 py-4">
              <h2 className="text-base font-semibold text-slate-900">Clientes</h2>
              <Boton variante="secundario" tamano="sm" onClick={() => setCreandoCliente(true)}>
                <Icono nombre="mas" className="size-4" /> Nuevo cliente
              </Boton>
            </div>
            {clientes.isLoading ? (
              <Cargando />
            ) : !clientes.data?.items.length ? (
              <Vacio titulo="Sin clientes" descripcion="Registra un cliente (terminal) y después sus proyectos para poder capturar entradas." />
            ) : (
              <Tabla>
                <thead>
                  <tr>
                    <Th>Cliente</Th>
                    <Th>Estado</Th>
                    <Th derecha>Proyectos</Th>
                    <Th><span className="sr-only">Acciones</span></Th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {clientes.data.items.map((t) => (
                    <tr key={t.id} className="cursor-pointer hover:bg-slate-50" onClick={() => navigate(`/clientes/${t.id}`)}>
                      <Td className="font-medium text-slate-900">{t.identificador_terminal}</Td>
                      <Td>{t.activa ? <Insignia tono="exito">Activo</Insignia> : <Insignia>Inactivo</Insignia>}</Td>
                      <Td derecha>{t.num_proyectos}</Td>
                      <Td className="text-right"><Boton variante="fantasma" tamano="sm">Ver proyectos</Boton></Td>
                    </tr>
                  ))}
                </tbody>
              </Tabla>
            )}
          </Tarjeta>
        </div>

        <div className="space-y-6">
          <TarjetaSaldo ruta={`/empresas/${e.id}/saldo`} claveCache={`empresa-${e.id}`} />
        </div>
      </div>

      <EmpresaForm abierto={editando} empresa={e} onCerrar={() => setEditando(false)} />
      {esAdmin && <Reasignar empresa={e} abierto={reasignando} onCerrar={() => setReasignando(false)} />}
      <CrearCliente abierto={creandoCliente} onCerrar={() => setCreandoCliente(false)} empresaInicial={e.id} />
      <CapturarMovimiento abierto={capturando} onCerrar={() => setCapturando(false)} inicial={{ empresaId: e.id }} />
      <RegistrarSalida abierto={registrandoSalida} onCerrar={() => setRegistrandoSalida(false)} inicial={{ empresaId: e.id }} />
    </>
  );
}
