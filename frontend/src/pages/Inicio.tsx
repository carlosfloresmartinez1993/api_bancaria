import { useState } from "react";
import { Link } from "react-router";
import { useQuery } from "@tanstack/react-query";
import { useAuth } from "../auth/AuthContext";
import { AvanceDelDia } from "../components/AvanceDelDia";
import { Icono } from "../components/Icono";
import { CapturarMovimiento } from "../components/formularios/MovimientoForm";
import { RegistrarSalida } from "../components/formularios/SalidaForm";
import { Boton, Cargando, EncabezadoPagina, ErrorApi, Insignia, Monto, Tabla, Tarjeta, Td, Th, Vacio } from "../components/ui";
import { api } from "../lib/api";
import { dinero, fecha, hoyISO, porcentaje } from "../lib/format";
import { useNombresEmpresa, useNombresProyecto, useNombresTerminal } from "../lib/queries";
import type { Movimiento, Pagina, Reporte } from "../lib/types";

function Indicador({ titulo, valor, detalle, tono }: { titulo: string; valor: string; detalle?: string; tono?: "peligro" }) {
  return (
    <Tarjeta className="p-5">
      <p className="text-sm font-medium text-slate-500">{titulo}</p>
      <p className={`mt-2 text-2xl font-semibold tracking-tight tabular-nums ${tono === "peligro" ? "text-rose-600" : "text-slate-900"}`}>
        {valor}
      </p>
      {detalle && <p className="mt-1 text-xs text-slate-500">{detalle}</p>}
    </Tarjeta>
  );
}

export default function Inicio() {
  const { usuario, esAdmin } = useAuth();
  const [capturando, setCapturando] = useState(false);
  const [registrandoSalida, setRegistrandoSalida] = useState(false);
  const nombresEmpresa = useNombresEmpresa();
  const nombresCliente = useNombresTerminal();
  const nombresProyecto = useNombresProyecto();

  const saldos = useQuery({
    queryKey: ["reporte", "saldos", hoyISO()],
    queryFn: () => api.get<Reporte>("/reportes/saldos"),
  });
  const recientes = useQuery({
    queryKey: ["movimientos", "recientes"],
    queryFn: () => api.get<Pagina<Movimiento>>("/movimientos", { limit: 8 }),
  });

  const totales = saldos.data?.totales as Record<string, string> | undefined;
  const negativas = (saldos.data?.filas ?? []).filter((f) => Number(f.saldo) < 0);

  return (
    <>
      <EncabezadoPagina
        titulo={`Hola, ${usuario?.nombre}`}
        descripcion={esAdmin ? "Resumen de todas las empresas del sistema." : "Resumen de tus empresas."}
        acciones={
          <>
            <Boton variante="secundario" onClick={() => setRegistrandoSalida(true)}>
              <Icono nombre="salidas" className="size-4" />
              Registrar salida
            </Boton>
            <Boton onClick={() => setCapturando(true)}>
              <Icono nombre="mas" className="size-4" />
              Capturar entrada
            </Boton>
          </>
        }
      />

      <ErrorApi error={saldos.error} className="mb-6" />

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Indicador titulo="Entradas netas acumuladas" valor={dinero(totales?.ingresos_netos ?? 0)} detalle="Después de comisiones" />
        <Indicador titulo="Comisiones acumuladas" valor={dinero(totales?.comisiones ?? 0)}
          detalle={`Sobre ${dinero(totales?.ingresos_brutos ?? 0)} brutos`} />
        <Indicador titulo="Salidas acumuladas" valor={dinero(totales?.salidas ?? 0)} />
        <Indicador
          titulo="Saldo total"
          valor={dinero(totales?.saldo ?? 0)}
          tono={Number(totales?.saldo ?? 0) < 0 ? "peligro" : undefined}
          detalle={`${saldos.data?.filas.length ?? 0} empresa(s)`}
        />
      </div>

      {negativas.length > 0 && (
        <div className="mt-4 rounded-lg bg-amber-50 p-3 text-sm text-amber-900 ring-1 ring-amber-200">
          <span className="font-medium">{negativas.length} empresa(s) con saldo negativo:</span>{" "}
          {negativas.map((f) => String(f.empresa)).join(", ")}. Probablemente falta capturar alguna entrada.
        </div>
      )}
        {esAdmin && (
        <div className="mt-8">
          <AvanceDelDia />
        </div>
      )}


      <div className="mt-8 grid gap-6 2xl:grid-cols-5">
        <Tarjeta className="2xl:col-span-3">
          <div className="flex items-center justify-between px-5 py-4">
            <h2 className="text-base font-semibold text-slate-900">Saldo por empresa</h2>
            <Link to="/empresas" className="text-sm font-medium text-teal-700 hover:text-teal-800">
              Ver empresas
            </Link>
          </div>
          {saldos.isLoading ? (
            <Cargando />
          ) : !saldos.data?.filas.length ? (
            <Vacio titulo="Aún no hay empresas" descripcion="Registra una empresa para empezar a capturar entradas." />
          ) : (
            <Tabla>
              <thead>
                <tr>
                  <Th>Empresa</Th>
                  <Th derecha>Entradas netas</Th>
                  <Th derecha>Comisiones</Th>
                  <Th derecha>Salidas</Th>
                  <Th derecha>Saldo</Th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {saldos.data.filas.map((f) => (
                  <tr key={String(f.empresa)} className="hover:bg-slate-50">
                    <Td className="font-medium text-slate-900">{String(f.empresa)}</Td>
                    <Td derecha><Monto valor={f.ingresos_netos as string} /></Td>
                    <Td derecha className="text-slate-500"><Monto valor={f.comisiones as string} /></Td>
                    <Td derecha><Monto valor={f.salidas as string} /></Td>
                    <Td derecha className="font-medium"><Monto valor={f.saldo as string} resaltarNegativo /></Td>
                  </tr>
                ))}
              </tbody>
              {totales && (
                <tfoot className="border-t-2 border-slate-200 bg-slate-50 font-semibold text-slate-900">
                  <tr>
                    <Td>Total</Td>
                    <Td derecha><Monto valor={totales.ingresos_netos} /></Td>
                    <Td derecha><Monto valor={totales.comisiones} /></Td>
                    <Td derecha><Monto valor={totales.salidas} /></Td>
                    <Td derecha><Monto valor={totales.saldo} resaltarNegativo /></Td>
                  </tr>
                </tfoot>
              )}
            </Tabla>
          )}
        </Tarjeta>

        <Tarjeta className="2xl:col-span-2">
          <div className="flex items-center justify-between px-5 py-4">
            <h2 className="text-base font-semibold text-slate-900">Últimas entradas</h2>
            <Link to="/movimientos" className="text-sm font-medium text-teal-700 hover:text-teal-800">
              Ver todas
            </Link>
          </div>
          {recientes.isLoading ? (
            <Cargando />
          ) : !recientes.data?.items.length ? (
            <Vacio titulo="Sin entradas" descripcion="Los ingresos capturados aparecerán aquí." />
          ) : (
            <ul className="divide-y divide-slate-100 border-t border-slate-100">
              {recientes.data.items.map((m) => (
                <li key={m.id} className="flex items-center justify-between gap-4 px-5 py-3">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium text-slate-900">
                      {nombresEmpresa.get(m.empresa_id) ?? "Empresa"}
                    </p>
                    <p className="truncate text-xs text-slate-500">
                      {fecha(m.fecha_movimiento)} · {nombresCliente.get(m.terminal_id) ?? "Cliente"} ·{" "}
                      {nombresProyecto.get(m.proyecto_id) ?? "Proyecto"} <Insignia>{porcentaje(m.porcentaje_aplicado)}</Insignia>
                    </p>
                  </div>
                  <div className="text-right">
                    <p className="text-sm font-medium tabular-nums text-slate-900">{dinero(m.monto_neto)}</p>
                    <p className="text-xs tabular-nums text-slate-500">bruto {dinero(m.monto_bruto)}</p>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Tarjeta>
      </div>

      <CapturarMovimiento abierto={capturando} onCerrar={() => setCapturando(false)} />
      <RegistrarSalida abierto={registrandoSalida} onCerrar={() => setRegistrandoSalida(false)} />
    </>
  );
}
