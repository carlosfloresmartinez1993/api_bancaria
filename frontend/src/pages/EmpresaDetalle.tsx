import { useRef, useState, type FormEvent, type ReactNode } from "react";
import { Link, useParams } from "react-router";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "../auth/AuthContext";
import { EmpresaForm } from "../components/formularios/EmpresaForm";
import { CapturarMovimiento } from "../components/formularios/MovimientoForm";
import { RegistrarSalida } from "../components/formularios/SalidaForm";
import { CrearTerminal, DetalleTerminal } from "../components/formularios/TerminalForm";
import { Icono } from "../components/Icono";
import { LogoEmpresa } from "../components/LogoEmpresa";
import { SelectorUsuario } from "../components/Selectores";
import { useToast } from "../components/Toast";
import {
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
import { api, guardarBlob } from "../lib/api";
import { fecha, hoyISO, porcentaje } from "../lib/format";
import { useNombresUsuario } from "../lib/queries";
import type { Empresa, Pagina, Saldo, Terminal, TipoArchivo } from "../lib/types";

const ARCHIVOS: { tipo: TipoArchivo; titulo: string; acepta: string; ayuda: string }[] = [
  { tipo: "pdf1", titulo: "Documento PDF 1", acepta: "application/pdf", ayuda: "PDF" },
  { tipo: "pdf2", titulo: "Documento PDF 2", acepta: "application/pdf", ayuda: "PDF" },
  { tipo: "logo", titulo: "Logo", acepta: "image/png,image/jpeg,image/webp", ayuda: "PNG, JPG o WEBP" },
];

function Dato({ etiqueta, children }: { etiqueta: string; children: ReactNode }) {
  return (
    <div>
      <dt className="text-xs font-medium text-slate-500">{etiqueta}</dt>
      <dd className="mt-0.5 text-sm text-slate-900">{children}</dd>
    </div>
  );
}

function TarjetaSaldo({ empresaId }: { empresaId: string }) {
  const [alDia, setAlDia] = useState(hoyISO());
  const { data, error } = useQuery({
    queryKey: ["saldo", empresaId, alDia],
    queryFn: () => api.get<Saldo>(`/empresas/${empresaId}/saldo`, { al_dia: alDia }),
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
          <dt className="text-slate-500">Ingresos netos</dt>
          <dd className="font-medium"><Monto valor={data?.ingresos_netos ?? null} /></dd>
        </div>
        <div className="flex justify-between">
          <dt className="text-slate-500">Salidas</dt>
          <dd className="font-medium">− <Monto valor={data?.salidas ?? null} /></dd>
        </div>
      </dl>
      {data && Number(data.saldo) < 0 && (
        <p className="mt-3 rounded-md bg-amber-50 p-2 text-xs text-amber-900">Saldo negativo: probablemente falta capturar algún ingreso.</p>
      )}
    </Tarjeta>
  );
}

function Archivos({ empresa }: { empresa: Empresa }) {
  const qc = useQueryClient();
  const avisar = useToast();
  const [ocupado, setOcupado] = useState<TipoArchivo | null>(null);
  const [error, setError] = useState<unknown>(null);
  const entradas = useRef<Partial<Record<TipoArchivo, HTMLInputElement | null>>>({});

  async function ejecutar(tipo: TipoArchivo, accion: () => Promise<unknown>, mensaje?: string) {
    setOcupado(tipo);
    setError(null);
    try {
      await accion();
      if (mensaje) {
        avisar(mensaje);
        await qc.invalidateQueries({ queryKey: ["empresas"] });
      }
    } catch (e) {
      setError(e);
    } finally {
      setOcupado(null);
    }
  }

  return (
    <Tarjeta className="p-5">
      <h2 className="text-base font-semibold text-slate-900">Documentos</h2>
      <ErrorApi error={error} className="mt-3" />
      <ul className="mt-3 divide-y divide-slate-100">
        {ARCHIVOS.map(({ tipo, titulo, acepta, ayuda }) => {
          const ruta = empresa.archivos[tipo];
          return (
            <li key={tipo} className="flex items-center justify-between gap-3 py-3">
              <div className="flex min-w-0 items-center gap-3">
                <Icono nombre="documento" className={`size-5 shrink-0 ${ruta ? "text-teal-600" : "text-slate-300"}`} />
                <div className="min-w-0">
                  <p className="text-sm font-medium text-slate-900">{titulo}</p>
                  <p className="text-xs text-slate-500">{ruta ? "Cargado" : `Sin archivo · ${ayuda}`}</p>
                </div>
              </div>
              <div className="flex shrink-0 gap-1">
                <input
                  type="file"
                  accept={acepta}
                  className="hidden"
                  ref={(el) => { entradas.current[tipo] = el; }}
                  onChange={(e) => {
                    const archivo = e.target.files?.[0];
                    e.target.value = "";
                    if (!archivo) return;
                    const datos = new FormData();
                    datos.append("archivo", archivo);
                    ejecutar(tipo, () => api.put(`/empresas/${empresa.id}/archivos/${tipo}`, datos), `${titulo} cargado`);
                  }}
                />
                {ruta && (
                  <Boton variante="fantasma" tamano="sm" aria-label={`Descargar ${titulo}`}
                    onClick={() => ejecutar(tipo, async () => {
                      const blob = await api.blob(ruta);
                      const ext = blob.type === "application/pdf" ? "pdf" : blob.type.split("/")[1] ?? "bin";
                      guardarBlob(blob, `${empresa.nombre} - ${titulo}.${ext}`);
                    })}>
                    <Icono nombre="descargar" className="size-4" />
                  </Boton>
                )}
                <Boton variante="secundario" tamano="sm" cargando={ocupado === tipo} onClick={() => entradas.current[tipo]?.click()}>
                  <Icono nombre="subir" className="size-4" />
                  {ruta ? "Reemplazar" : "Subir"}
                </Boton>
                {ruta && (
                  <Boton variante="fantasma" tamano="sm" aria-label={`Eliminar ${titulo}`} className="hover:text-rose-600"
                    onClick={() => confirm(`¿Eliminar ${titulo}?`) &&
                      ejecutar(tipo, () => api.delete(`/empresas/${empresa.id}/archivos/${tipo}`), `${titulo} eliminado`)}>
                    <Icono nombre="basura" className="size-4" />
                  </Boton>
                )}
              </div>
            </li>
          );
        })}
      </ul>
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
      descripcion="La empresa pasa a otro contador con sus terminales, movimientos y salidas.">
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
  const nombresUsuario = useNombresUsuario();
  const [editando, setEditando] = useState(false);
  const [reasignando, setReasignando] = useState(false);
  const [creandoTerminal, setCreandoTerminal] = useState(false);
  const [terminal, setTerminal] = useState<Terminal | null>(null);
  const [capturando, setCapturando] = useState(false);
  const [registrandoSalida, setRegistrandoSalida] = useState(false);

  const empresa = useQuery({
    queryKey: ["empresas", id],
    queryFn: () => api.get<Empresa>(`/empresas/${id}`),
  });
  const terminales = useQuery({
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
          <LogoEmpresa empresa={e} className="size-16" />
          <div>
            <h1 className="text-2xl font-semibold tracking-tight text-slate-900">{e.nombre}</h1>
            <p className="text-sm text-slate-500">{e.csf}</p>
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          {esAdmin && <Boton variante="secundario" onClick={() => setReasignando(true)}>Reasignar</Boton>}
          <Boton variante="secundario" onClick={() => setEditando(true)}>
            <Icono nombre="lapiz" className="size-4" /> Editar
          </Boton>
          <Boton variante="secundario" onClick={() => setRegistrandoSalida(true)}>Registrar salida</Boton>
          <Boton onClick={() => setCapturando(true)}>
            <Icono nombre="mas" className="size-4" /> Capturar movimiento
          </Boton>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <Tarjeta className="p-5">
            <h2 className="mb-4 text-base font-semibold text-slate-900">Datos de la empresa</h2>
            <dl className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              <Dato etiqueta="Banco">{e.banco}</Dato>
              <Dato etiqueta="Número de cuenta"><span className="tabular-nums">{e.numero_cuenta}</span></Dato>
              <Dato etiqueta="CLABE"><span className="tabular-nums">{e.clabe ?? "—"}</span></Dato>
              {esAdmin && <Dato etiqueta="Contador">{nombresUsuario.get(e.usuario_id) ?? "—"}</Dato>}
              <Dato etiqueta="Registrada">{fecha(e.fecha_registro)}</Dato>
            </dl>
            <div className="mt-5 flex flex-wrap gap-4 border-t border-slate-100 pt-4 text-sm">
              <Link to={`/movimientos?empresa_id=${e.id}`} className="font-medium text-teal-700 hover:text-teal-800">Ver movimientos →</Link>
              <Link to={`/salidas?empresa_id=${e.id}`} className="font-medium text-teal-700 hover:text-teal-800">Ver salidas →</Link>
              <Link to={`/reportes?r=estado-cuenta&empresa_id=${e.id}`} className="font-medium text-teal-700 hover:text-teal-800">Estado de cuenta →</Link>
            </div>
          </Tarjeta>

          <Tarjeta>
            <div className="flex items-center justify-between px-5 py-4">
              <h2 className="text-base font-semibold text-slate-900">Terminales</h2>
              <Boton variante="secundario" tamano="sm" onClick={() => setCreandoTerminal(true)}>
                <Icono nombre="mas" className="size-4" /> Nueva terminal
              </Boton>
            </div>
            {terminales.isLoading ? (
              <Cargando />
            ) : !terminales.data?.items.length ? (
              <Vacio titulo="Sin terminales" descripcion="Registra una terminal para poder capturar sus movimientos." />
            ) : (
              <Tabla>
                <thead>
                  <tr>
                    <Th>Terminal</Th>
                    <Th>Estado</Th>
                    <Th derecha>Comisión vigente</Th>
                    <Th><span className="sr-only">Acciones</span></Th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {terminales.data.items.map((t) => (
                    <tr key={t.id} className="cursor-pointer hover:bg-slate-50" onClick={() => setTerminal(t)}>
                      <Td className="font-medium text-slate-900">{t.identificador_terminal}</Td>
                      <Td>{t.activa ? <Insignia tono="exito">Activa</Insignia> : <Insignia>Inactiva</Insignia>}</Td>
                      <Td derecha>{porcentaje(t.porcentaje_vigente)}</Td>
                      <Td className="text-right"><Boton variante="fantasma" tamano="sm">Detalle</Boton></Td>
                    </tr>
                  ))}
                </tbody>
              </Tabla>
            )}
          </Tarjeta>
        </div>

        <div className="space-y-6">
          <TarjetaSaldo empresaId={e.id} />
          <Archivos empresa={e} />
        </div>
      </div>

      <EmpresaForm abierto={editando} empresa={e} onCerrar={() => setEditando(false)} />
      {esAdmin && <Reasignar empresa={e} abierto={reasignando} onCerrar={() => setReasignando(false)} />}
      <CrearTerminal abierto={creandoTerminal} onCerrar={() => setCreandoTerminal(false)} empresaInicial={e.id} />
      <DetalleTerminal terminal={terminal} onCerrar={() => setTerminal(null)} />
      <CapturarMovimiento abierto={capturando} onCerrar={() => setCapturando(false)} empresaInicial={e.id} />
      <RegistrarSalida abierto={registrandoSalida} onCerrar={() => setRegistrandoSalida(false)} empresaInicial={e.id} />
    </>
  );
}
