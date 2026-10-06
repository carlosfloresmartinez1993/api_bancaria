import { useState } from "react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useAuth } from "../auth/AuthContext";
import { ConfirmarEliminacion } from "../components/formularios/ConfirmarEliminacion";
import { CapturarMovimiento, EditarMovimiento } from "../components/formularios/MovimientoForm";
import { Icono } from "../components/Icono";
import { SelectorCliente, SelectorEmpresa, SelectorMetodoPago, SelectorProyecto, SelectorUsuario } from "../components/Selectores";
import { useToast } from "../components/Toast";
import {
  Boton,
  Campo,
  Cargando,
  EncabezadoPagina,
  ErrorApi,
  Input,
  Insignia,
  Monto,
  Paginacion,
  Select,
  Tabla,
  Tarjeta,
  Td,
  Th,
  Vacio,
} from "../components/ui";
import { api } from "../lib/api";
import { fecha, fechaHoraLocal, porcentaje } from "../lib/format";
import { useFiltros } from "../lib/filtros";
import { useInvalidarDinero } from "../lib/invalidar";
import { useNombresEmpresa, useNombresMetodoPago, useNombresProyecto, useNombresTerminal, useNombresUsuario } from "../lib/queries";
import type { Movimiento, Pagina } from "../lib/types";

const LIMITE = 50;
const CLAVES = ["empresa_id", "terminal_id", "proyecto_id", "metodo_pago_id", "requiere_factura", "capturo_id", "desde", "hasta"] as const;

export default function Movimientos() {
  const { esAdmin, usuario } = useAuth();
  const avisar = useToast();
  const invalidar = useInvalidarDinero();
  const { filtros, offset, cambiar, limpiar, activos } = useFiltros(CLAVES);
  const nombresEmpresa = useNombresEmpresa();
  const nombresCliente = useNombresTerminal();
  const nombresProyecto = useNombresProyecto();
  const nombresMetodo = useNombresMetodoPago();
  const nombresUsuario = useNombresUsuario();

  const [capturando, setCapturando] = useState(false);
  const [editando, setEditando] = useState<Movimiento | null>(null);
  const [eliminando, setEliminando] = useState<Movimiento | null>(null);

  const { data, isLoading, error, isFetching } = useQuery({
    queryKey: ["movimientos", filtros, offset],
    queryFn: () => api.get<Pagina<Movimiento>>("/movimientos", { ...filtros, limit: LIMITE, offset }),
    placeholderData: keepPreviousData,
  });

  const quienCapturo = (id: string) =>
    id === usuario?.id ? "Tú" : (nombresUsuario.get(id) ?? (esAdmin ? "—" : "Otro usuario"));

  return (
    <>
      <EncabezadoPagina
        titulo="Entradas"
        descripcion="Ingresos capturados por proyecto. El neto lo calcula la base de datos con el % vigente del proyecto ese día."
        acciones={
          <Boton onClick={() => setCapturando(true)}>
            <Icono nombre="mas" className="size-4" />
            Capturar entrada
          </Boton>
        }
      />

      <Tarjeta className="mb-4 p-4">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Campo etiqueta="Empresa">
            {(id) => (
              <SelectorEmpresa id={id} valor={filtros.empresa_id} vacio="Todas"
                onCambiar={(v) => cambiar({ empresa_id: v, terminal_id: "", proyecto_id: "" })} />
            )}
          </Campo>
          <Campo etiqueta="Cliente">
            {(id) => (
              <SelectorCliente id={id} valor={filtros.terminal_id} vacio="Todos" empresaId={filtros.empresa_id}
                onCambiar={(v) => cambiar({ terminal_id: v, proyecto_id: "" })} />
            )}
          </Campo>
          <Campo etiqueta="Proyecto">
            {(id) => (
              <SelectorProyecto id={id} valor={filtros.proyecto_id} vacio="Todos" empresaId={filtros.empresa_id || undefined}
                terminalId={filtros.terminal_id || undefined} onCambiar={(v) => cambiar({ proyecto_id: v })} />
            )}
          </Campo>
          <Campo etiqueta="Método de pago">
            {(id) => <SelectorMetodoPago id={id} valor={filtros.metodo_pago_id} vacio="Todos" onCambiar={(v) => cambiar({ metodo_pago_id: v })} />}
          </Campo>
          <Campo etiqueta="Factura">
            {(id) => (
              <Select id={id} value={filtros.requiere_factura} onChange={(e) => cambiar({ requiere_factura: e.target.value })}>
                <option value="">Todas</option>
                <option value="true">Requieren factura</option>
                <option value="false">Sin factura</option>
              </Select>
            )}
          </Campo>
          {esAdmin && (
            <Campo etiqueta="Capturó">
              {(id) => <SelectorUsuario id={id} valor={filtros.capturo_id} vacio="Cualquiera" onCambiar={(v) => cambiar({ capturo_id: v })} />}
            </Campo>
          )}
          <Campo etiqueta="Desde">
            {(id) => <Input id={id} type="date" value={filtros.desde} onChange={(e) => cambiar({ desde: e.target.value })} />}
          </Campo>
          <Campo etiqueta="Hasta">
            {(id) => <Input id={id} type="date" value={filtros.hasta} onChange={(e) => cambiar({ hasta: e.target.value })} />}
          </Campo>
        </div>
        {activos && (
          <div className="mt-3 flex justify-end">
            <Boton variante="fantasma" tamano="sm" onClick={limpiar}>Limpiar filtros</Boton>
          </div>
        )}
      </Tarjeta>

      <ErrorApi error={error} className="mb-4" />

      <Tarjeta className={isFetching && !isLoading ? "opacity-70 transition-opacity" : undefined}>
        {isLoading ? (
          <Cargando />
        ) : !data?.items.length ? (
          <Vacio
            titulo={activos ? "Ninguna entrada coincide con los filtros" : "Aún no hay entradas"}
            accion={!activos && <Boton onClick={() => setCapturando(true)}>Capturar la primera</Boton>}
          />
        ) : (
          <>
            <Tabla>
              <thead>
                <tr>
                  <Th>Fecha</Th>
                  <Th>Empresa / cliente / proyecto</Th>
                  <Th>Método</Th>
                  <Th derecha>Bruto</Th>
                  <Th derecha>%</Th>
                  <Th derecha>Comisión</Th>
                  <Th derecha>Neto</Th>
                  <Th>Capturó</Th>
                  <Th><span className="sr-only">Acciones</span></Th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {data.items.map((m) => (
                  <tr key={m.id} className="hover:bg-slate-50">
                    <Td className="whitespace-nowrap">{fecha(m.fecha_movimiento)}</Td>
                    <Td>
                      <p className="font-medium text-slate-900">{nombresEmpresa.get(m.empresa_id) ?? "—"}</p>
                      <p className="text-xs text-slate-500">
                        {nombresCliente.get(m.terminal_id) ?? "—"} · {nombresProyecto.get(m.proyecto_id) ?? "—"}
                        {m.observaciones && <span title={m.observaciones}> · {m.observaciones}</span>}
                      </p>
                    </Td>
                    <Td>
                      <p className="whitespace-nowrap">{nombresMetodo.get(m.metodo_pago_id) ?? "—"}</p>
                      {m.requiere_factura && <Insignia tono="info">Factura</Insignia>}
                    </Td>
                    <Td derecha><Monto valor={m.monto_bruto} /></Td>
                    <Td derecha><Insignia>{porcentaje(m.porcentaje_aplicado)}</Insignia></Td>
                    <Td derecha className="text-slate-500"><Monto valor={m.comision} /></Td>
                    <Td derecha className="font-medium text-slate-900"><Monto valor={m.monto_neto} /></Td>
                    <Td>
                      <p className="whitespace-nowrap">{quienCapturo(m.usuario_id)}</p>
                      <p className="whitespace-nowrap text-xs text-slate-500">{fechaHoraLocal(m.fecha_captura)}</p>
                    </Td>
                    <Td className="whitespace-nowrap text-right">
                      <Boton variante="fantasma" tamano="sm" onClick={() => setEditando(m)} aria-label="Corregir">
                        <Icono nombre="lapiz" className="size-4" />
                      </Boton>
                      <Boton variante="fantasma" tamano="sm" onClick={() => setEliminando(m)} aria-label="Eliminar"
                        className="hover:text-rose-600">
                        <Icono nombre="basura" className="size-4" />
                      </Boton>
                    </Td>
                  </tr>
                ))}
              </tbody>
            </Tabla>
            <Paginacion total={data.total} limit={LIMITE} offset={offset} onCambiar={(o) => cambiar({ offset: o })} />
          </>
        )}
      </Tarjeta>

      <CapturarMovimiento abierto={capturando} onCerrar={() => setCapturando(false)}
        inicial={{ empresaId: filtros.empresa_id, clienteId: filtros.terminal_id, proyectoId: filtros.proyecto_id }} />
      <EditarMovimiento movimiento={editando} onCerrar={() => setEditando(null)} />
      <ConfirmarEliminacion
        abierto={eliminando !== null}
        titulo="Eliminar entrada"
        onCerrar={() => setEliminando(null)}
        onConfirmar={async (motivo) => {
          await api.delete(`/movimientos/${eliminando!.id}`, { motivo });
          invalidar();
          avisar("Entrada eliminada");
        }}
      >
        {eliminando && (
          <p>
            Se eliminará la entrada del <strong>{fecha(eliminando.fecha_movimiento)}</strong> por{" "}
            <strong><Monto valor={eliminando.monto_bruto} /></strong> del proyecto{" "}
            <strong>{nombresProyecto.get(eliminando.proyecto_id)}</strong>. Los saldos se recalcularán.
          </p>
        )}
      </ConfirmarEliminacion>
    </>
  );
}
