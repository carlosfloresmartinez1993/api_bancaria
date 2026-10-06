import { useEffect, useState } from "react";
import { Link } from "react-router";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useAuth } from "../auth/AuthContext";
import { EmpresaForm } from "../components/formularios/EmpresaForm";
import { Icono } from "../components/Icono";
import { SelectorUsuario } from "../components/Selectores";
import { Boton, Campo, Cargando, EncabezadoPagina, ErrorApi, Iniciales, Input, Paginacion, Tarjeta, Vacio } from "../components/ui";
import { api } from "../lib/api";
import { fecha } from "../lib/format";
import { useFiltros } from "../lib/filtros";
import { useNombresUsuario } from "../lib/queries";
import type { Empresa, Pagina } from "../lib/types";

const LIMITE = 24;
const CLAVES = ["q", "usuario_id"] as const;

export default function Empresas() {
  const { esAdmin } = useAuth();
  const { filtros, offset, cambiar } = useFiltros(CLAVES);
  const nombresUsuario = useNombresUsuario();
  const [creando, setCreando] = useState(false);

  const [busqueda, setBusqueda] = useState(filtros.q);
  useEffect(() => {
    const t = setTimeout(() => busqueda !== filtros.q && cambiar({ q: busqueda }), 300);
    return () => clearTimeout(t);
  }, [busqueda, filtros.q, cambiar]);

  const { data, isLoading, error } = useQuery({
    queryKey: ["empresas", "lista", filtros, offset],
    queryFn: () => api.get<Pagina<Empresa>>("/empresas", { ...filtros, limit: LIMITE, offset }),
    placeholderData: keepPreviousData,
  });

  return (
    <>
      <EncabezadoPagina
        titulo="Empresas"
        descripcion={esAdmin ? "Todas las empresas del sistema." : "Empresas que tienes a tu cargo."}
        acciones={
          <Boton onClick={() => setCreando(true)}>
            <Icono nombre="mas" className="size-4" />
            Nueva empresa
          </Boton>
        }
      />

      <Tarjeta className="mb-4 p-4">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <Campo etiqueta="Buscar">
            {(id) => <Input id={id} type="search" placeholder="Nombre de la empresa" value={busqueda} onChange={(e) => setBusqueda(e.target.value)} />}
          </Campo>
          {esAdmin && (
            <Campo etiqueta="Contador">
              {(id) => <SelectorUsuario id={id} valor={filtros.usuario_id} vacio="Todos" onCambiar={(v) => cambiar({ usuario_id: v })} />}
            </Campo>
          )}
        </div>
      </Tarjeta>

      <ErrorApi error={error} className="mb-4" />

      {isLoading ? (
        <Cargando />
      ) : !data?.items.length ? (
        <Tarjeta>
          <Vacio titulo={filtros.q ? "Ninguna empresa coincide con la búsqueda" : "Aún no hay empresas"}
            accion={!filtros.q && <Boton onClick={() => setCreando(true)}>Registrar la primera</Boton>} />
        </Tarjeta>
      ) : (
        <>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {data.items.map((e) => (
              <Link key={e.id} to={`/empresas/${e.id}`}
                className="group rounded-xl bg-white p-5 shadow-sm ring-1 ring-slate-200 transition hover:shadow-md hover:ring-teal-300">
                <div className="flex items-start gap-3">
                  <Iniciales nombre={e.nombre} className="size-12" />
                  <div className="min-w-0">
                    <p className="truncate font-semibold text-slate-900 group-hover:text-teal-700">{e.nombre}</p>
                    <p className="truncate text-sm text-slate-500">{e.csf ?? "Sin CSF"}</p>
                  </div>
                </div>
                <dl className="mt-4 grid grid-cols-2 gap-3 text-sm">
                  <div>
                    <dt className="text-xs text-slate-500">Banco</dt>
                    <dd className="font-medium text-slate-700">{e.banco ?? "—"}</dd>
                  </div>
                  <div>
                    <dt className="text-xs text-slate-500">Clientes</dt>
                    <dd className="font-medium tabular-nums text-slate-700">{e.num_clientes}</dd>
                  </div>
                  {esAdmin && (
                    <div>
                      <dt className="text-xs text-slate-500">Contador</dt>
                      <dd className="truncate text-slate-700">{nombresUsuario.get(e.usuario_id) ?? "—"}</dd>
                    </div>
                  )}
                  <div>
                    <dt className="text-xs text-slate-500">Registrada</dt>
                    <dd className="text-slate-700">{fecha(e.fecha_registro)}</dd>
                  </div>
                </dl>
              </Link>
            ))}
          </div>
          <div className="mt-4 overflow-hidden rounded-xl bg-white ring-1 ring-slate-200">
            <Paginacion total={data.total} limit={LIMITE} offset={offset} onCambiar={(o) => cambiar({ offset: o })} />
          </div>
        </>
      )}

      <EmpresaForm abierto={creando} onCerrar={() => setCreando(false)} />
    </>
  );
}
