import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";
import { fecha, hoyISO } from "../lib/format";
import { useEmpresasCatalogo, useProyectosCatalogo, useTerminalesCatalogo, useUsuariosCatalogo } from "../lib/queries";
import type { Movimiento, Pagina } from "../lib/types";
import { Cargando, ErrorApi, Insignia, Tabla, Tarjeta, Td, Th } from "./ui";

/** Trae todas las entradas con fecha de hoy (el backend entrega como máximo 500 por página). */
async function entradasDeHoy(): Promise<Movimiento[]> {
  const hoy = hoyISO();
  const todas: Movimiento[] = [];
  for (let offset = 0; ; offset += 500) {
    const pagina = await api.get<Pagina<Movimiento>>("/movimientos", { desde: hoy, hasta: hoy, limit: 500, offset });
    todas.push(...pagina.items);
    if (todas.length >= pagina.total || pagina.items.length === 0) return todas;
  }
}

/**
 * Avance del día por trabajador (solo para admins).
 * Un proyecto está "procesado" si tiene al menos una entrada con fecha de hoy.
 * Cada contador responde por los proyectos activos de sus empresas.
 */
export function AvanceDelDia() {
  const usuarios = useUsuariosCatalogo();
  const empresas = useEmpresasCatalogo();
  const clientes = useTerminalesCatalogo();
  const proyectos = useProyectosCatalogo();
  const hoy = useQuery({
    queryKey: ["movimientos", "hoy", hoyISO()],
    queryFn: entradasDeHoy,
    refetchInterval: 60_000, // se actualiza solo cada minuto
  });

  const consultas = [usuarios, empresas, clientes, proyectos, hoy];
  const error = consultas.find((q) => q.error)?.error;
  const cargando = consultas.some((q) => q.isLoading);

  const duenoDeEmpresa = new Map((empresas.data ?? []).map((e) => [e.id, e.usuario_id]));
  const clienteActivo = new Map((clientes.data ?? []).map((c) => [c.id, c.activa]));
  const conEntradaHoy = new Set((hoy.data ?? []).map((m) => m.proyecto_id));

  const filas = (usuarios.data ?? [])
    .filter((u) => u.rol === "contador" && u.activo)
    .map((u) => {
      const suyos = (proyectos.data ?? []).filter(
        (p) => p.activo && clienteActivo.get(p.terminal_id) && duenoDeEmpresa.get(p.empresa_id) === u.id,
      );
      const procesados = suyos.filter((p) => conEntradaHoy.has(p.id)).length;
      return {
        id: u.id,
        nombre: `${u.nombre} ${u.apellidos}`,
        procesados,
        totales: suyos.length,
        pendientes: suyos.length - procesados,
      };
    })
    // Primero quienes tienen más pendientes
    .sort((a, b) => b.pendientes - a.pendientes || a.nombre.localeCompare(b.nombre));

  const sinNada = filas.filter((f) => f.totales > 0 && f.procesados === 0).length;

  return (
    <Tarjeta>
      <div className="flex flex-wrap items-center justify-between gap-2 px-5 py-4">
        <div>
          <h2 className="text-base font-semibold text-slate-900">Avance del día — {fecha(hoyISO())}</h2>
          <p className="text-xs text-slate-500">Proyectos activos de cada trabajador con al menos una entrada de hoy.</p>
        </div>
        {sinNada > 0 && <Insignia tono="peligro">{sinNada} trabajador(es) sin procesar nada hoy</Insignia>}
      </div>
      <ErrorApi error={error} className="mx-5 mb-4" />
      {cargando ? (
        <Cargando />
      ) : (
        <Tabla>
          <thead>
            <tr>
              <Th>Trabajador</Th>
              <Th derecha>Procesados</Th>
              <Th derecha>Proyectos Totales </Th>
              <Th derecha>No procesados</Th>
              <Th>Estado</Th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {filas.map((f) => (
              <tr key={f.id} className={f.totales > 0 && f.procesados === 0 ? "bg-rose-50/60" : "hover:bg-slate-50"}>
                <Td className="font-medium text-slate-900">{f.nombre}</Td>
                <Td derecha>{f.procesados}</Td>
                <Td derecha>{f.totales}</Td>
                                <Td derecha><span className={f.pendientes > 0 ? "font-semibold text-rose-600" : undefined}>{f.pendientes}</span></Td>
                <Td>
                  {f.totales === 0 ? (
                    <Insignia>Sin proyectos</Insignia>
                  ) : f.pendientes === 0 ? (
                    <Insignia tono="exito">Al día</Insignia>
                  ) : f.procesados === 0 ? (
                    <Insignia tono="peligro">Sin procesar</Insignia>
                  ) : (
                    <Insignia tono="aviso">Pendiente</Insignia>
                  )}
                </Td>
              </tr>
            ))}
          </tbody>
        </Tabla>
      )}
    </Tarjeta>
  );
}