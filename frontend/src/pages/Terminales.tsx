import { useState } from "react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { CrearTerminal, DetalleTerminal } from "../components/formularios/TerminalForm";
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
import { fecha, porcentaje } from "../lib/format";
import { useFiltros } from "../lib/filtros";
import { useNombresEmpresa } from "../lib/queries";
import type { Pagina, Terminal } from "../lib/types";

const LIMITE = 50;
const CLAVES = ["empresa_id", "activa"] as const;

export default function Terminales() {
  const { filtros, offset, cambiar } = useFiltros(CLAVES);
  const nombresEmpresa = useNombresEmpresa();
  const [creando, setCreando] = useState(false);
  const [seleccionada, setSeleccionada] = useState<Terminal | null>(null);

  const { data, isLoading, error } = useQuery({
    queryKey: ["terminales", "lista", filtros, offset],
    queryFn: () => api.get<Pagina<Terminal>>("/terminales", { ...filtros, limit: LIMITE, offset }),
    placeholderData: keepPreviousData,
  });

  return (
    <>
      <EncabezadoPagina
        titulo="Terminales"
        descripcion="Terminales punto de venta de cada empresa y el porcentaje de comisión que cobra el banco."
        acciones={
          <Boton onClick={() => setCreando(true)}>
            <Icono nombre="mas" className="size-4" />
            Nueva terminal
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
                <option value="">Todas</option>
                <option value="true">Activas</option>
                <option value="false">Inactivas</option>
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
          <Vacio titulo="No hay terminales" descripcion="Registra una terminal para empezar a capturar sus cortes."
            accion={<Boton onClick={() => setCreando(true)}>Nueva terminal</Boton>} />
        ) : (
          <>
            <Tabla>
              <thead>
                <tr>
                  <Th>Terminal</Th>
                  <Th>Empresa</Th>
                  <Th>Estado</Th>
                  <Th derecha>Comisión vigente</Th>
                  <Th>Registrada</Th>
                  <Th><span className="sr-only">Acciones</span></Th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {data.items.map((t) => (
                  <tr key={t.id} className="cursor-pointer hover:bg-slate-50" onClick={() => setSeleccionada(t)}>
                    <Td>
                      <p className="font-medium text-slate-900">{t.identificador_terminal}</p>
                      {typeof t.datos_extra.modelo === "string" && <p className="text-xs text-slate-500">{t.datos_extra.modelo}</p>}
                    </Td>
                    <Td>{nombresEmpresa.get(t.empresa_id) ?? "—"}</Td>
                    <Td>{t.activa ? <Insignia tono="exito">Activa</Insignia> : <Insignia>Inactiva</Insignia>}</Td>
                    <Td derecha className="font-medium">{porcentaje(t.porcentaje_vigente)}</Td>
                    <Td className="whitespace-nowrap">{fecha(t.fecha_registro)}</Td>
                    <Td className="text-right">
                      <Boton variante="fantasma" tamano="sm">Ver detalle</Boton>
                    </Td>
                  </tr>
                ))}
              </tbody>
            </Tabla>
            <Paginacion total={data.total} limit={LIMITE} offset={offset} onCambiar={(o) => cambiar({ offset: o })} />
          </>
        )}
      </Tarjeta>

      <CrearTerminal abierto={creando} onCerrar={() => setCreando(false)} empresaInicial={filtros.empresa_id} />
      <DetalleTerminal terminal={seleccionada} onCerrar={() => setSeleccionada(null)} />
    </>
  );
}
