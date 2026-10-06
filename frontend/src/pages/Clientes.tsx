import { useState } from "react";
import { useNavigate } from "react-router";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { CrearCliente } from "../components/formularios/ClienteForm";
import { Icono } from "../components/Icono";
import { SelectorEmpresa } from "../components/Selectores";
import {
  Boton,
  Campo,
  Cargando,
  EncabezadoPagina,
  ErrorApi,
  Insignia,
  Paginacion,
  Select,
  Tabla,
  Tarjeta,
  Td,
  Th,
  Vacio,
} from "../components/ui";
import { api } from "../lib/api";
import { fecha } from "../lib/format";
import { useFiltros } from "../lib/filtros";
import { useNombresEmpresa } from "../lib/queries";
import type { Pagina, Terminal } from "../lib/types";

const LIMITE = 50;
const CLAVES = ["empresa_id", "activa"] as const;

export default function Clientes() {
  const navigate = useNavigate();
  const { filtros, offset, cambiar } = useFiltros(CLAVES);
  const nombresEmpresa = useNombresEmpresa();
  const [creando, setCreando] = useState(false);

  const { data, isLoading, error } = useQuery({
    queryKey: ["terminales", "lista", filtros, offset],
    queryFn: () => api.get<Pagina<Terminal>>("/terminales", { ...filtros, limit: LIMITE, offset }),
    placeholderData: keepPreviousData,
  });

  return (
    <>
      <EncabezadoPagina
        titulo="Clientes"
        descripcion="Terminales de cada empresa. Cada cliente tiene sus proyectos, y cada proyecto su % de comisión."
        acciones={
          <Boton onClick={() => setCreando(true)}>
            <Icono nombre="mas" className="size-4" />
            Nuevo cliente
          </Boton>
        }
      />

      <Tarjeta className="mb-4 p-4">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Campo etiqueta="Empresa">
            {(id) => <SelectorEmpresa id={id} valor={filtros.empresa_id} vacio="Todas" onCambiar={(v) => cambiar({ empresa_id: v })} />}
          </Campo>
          <Campo etiqueta="Estado">
            {(id) => (
              <Select id={id} value={filtros.activa} onChange={(e) => cambiar({ activa: e.target.value })}>
                <option value="">Todos</option>
                <option value="true">Activos</option>
                <option value="false">Inactivos</option>
              </Select>
            )}
          </Campo>
        </div>
      </Tarjeta>

      <ErrorApi error={error} className="mb-4" />

      <Tarjeta>
        {isLoading ? (
          <Cargando />
        ) : !data?.items.length ? (
          <Vacio titulo="No hay clientes" descripcion="Registra un cliente para después agregarle sus proyectos."
            accion={<Boton onClick={() => setCreando(true)}>Nuevo cliente</Boton>} />
        ) : (
          <>
            <Tabla>
              <thead>
                <tr>
                  <Th>Cliente</Th>
                  <Th>Empresa</Th>
                  <Th derecha>Proyectos</Th>
                  <Th>Estado</Th>
                  <Th>Registrado</Th>
                  <Th><span className="sr-only">Acciones</span></Th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {data.items.map((t) => (
                  <tr key={t.id} className="cursor-pointer hover:bg-slate-50" onClick={() => navigate(`/clientes/${t.id}`)}>
                    <Td className="font-medium text-slate-900">{t.identificador_terminal}</Td>
                    <Td>{nombresEmpresa.get(t.empresa_id) ?? "—"}</Td>
                    <Td derecha>{t.num_proyectos}</Td>
                    <Td>{t.activa ? <Insignia tono="exito">Activo</Insignia> : <Insignia>Inactivo</Insignia>}</Td>
                    <Td className="whitespace-nowrap">{fecha(t.fecha_registro)}</Td>
                    <Td className="text-right">
                      <Boton variante="fantasma" tamano="sm">Ver proyectos</Boton>
                    </Td>
                  </tr>
                ))}
              </tbody>
            </Tabla>
            <Paginacion total={data.total} limit={LIMITE} offset={offset} onCambiar={(o) => cambiar({ offset: o })} />
          </>
        )}
      </Tarjeta>

      <CrearCliente abierto={creando} onCerrar={() => setCreando(false)} empresaInicial={filtros.empresa_id} />
    </>
  );
}
