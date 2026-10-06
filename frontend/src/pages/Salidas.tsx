import { useEffect, useState } from "react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { ConfirmarEliminacion } from "../components/formularios/ConfirmarEliminacion";
import { EditarSalida, RegistrarSalida } from "../components/formularios/SalidaForm";
import { Icono } from "../components/Icono";
import { SelectorCliente, SelectorEmpresa, SelectorMetodoPago, SelectorProyecto } from "../components/Selectores";
import { useToast } from "../components/Toast";
import {
  Boton,
  Campo,
  Cargando,
  EncabezadoPagina,
  ErrorApi,
  Input,
  Monto,
  Paginacion,
  Tabla,
  Tarjeta,
  Td,
  Th,
  Vacio,
} from "../components/ui";
import { api } from "../lib/api";
import { fecha } from "../lib/format";
import { useFiltros } from "../lib/filtros";
import { useInvalidarDinero } from "../lib/invalidar";
import { useNombresEmpresa, useNombresMetodoPago, useNombresProyecto, useNombresTerminal } from "../lib/queries";
import type { Pagina, Salida, Saldo } from "../lib/types";

const LIMITE = 50;
const CLAVES = ["empresa_id", "terminal_id", "proyecto_id", "metodo_pago_id", "desde", "hasta", "texto"] as const;

/** Saldo del nivel más específico elegido en los filtros (proyecto, cliente o empresa). */
function SaldoFiltrado({ ruta, etiqueta }: { ruta: string; etiqueta: string }) {
  const { data } = useQuery({ queryKey: ["saldo", ruta], queryFn: () => api.get<Saldo>(ruta) });
  if (!data) return null;
  return (
    <div className="flex flex-wrap gap-x-6 gap-y-1 text-sm">
      <span className="font-medium text-slate-700">{etiqueta}</span>
      <span className="text-slate-500">Entradas netas <strong className="text-slate-900"><Monto valor={data.ingresos_netos} /></strong></span>
      <span className="text-slate-500">Salidas <strong className="text-slate-900"><Monto valor={data.salidas} /></strong></span>
      <span className="text-slate-500">Saldo <strong><Monto valor={data.saldo} resaltarNegativo /></strong></span>
    </div>
  );
}

export default function Salidas() {
  const avisar = useToast();
  const invalidar = useInvalidarDinero();
  const { filtros, offset, cambiar, limpiar, activos } = useFiltros(CLAVES);
  const nombresEmpresa = useNombresEmpresa();
  const nombresCliente = useNombresTerminal();
  const nombresProyecto = useNombresProyecto();
  const nombresMetodo = useNombresMetodoPago();
  const [registrando, setRegistrando] = useState(false);
  const [editando, setEditando] = useState<Salida | null>(null);
  const [eliminando, setEliminando] = useState<Salida | null>(null);

  // La búsqueda de texto espera a que el usuario deje de escribir.
  const [texto, setTexto] = useState(filtros.texto);
  useEffect(() => {
    const t = setTimeout(() => texto !== filtros.texto && cambiar({ texto }), 350);
    return () => clearTimeout(t);
  }, [texto, filtros.texto, cambiar]);

  const { data, isLoading, error, isFetching } = useQuery({
    queryKey: ["salidas", filtros, offset],
    queryFn: () => api.get<Pagina<Salida>>("/salidas", { ...filtros, limit: LIMITE, offset }),
    placeholderData: keepPreviousData,
  });

  const saldo = filtros.proyecto_id
    ? { ruta: `/proyectos/${filtros.proyecto_id}/saldo`, etiqueta: `Proyecto ${nombresProyecto.get(filtros.proyecto_id) ?? ""}` }
    : filtros.terminal_id
      ? { ruta: `/terminales/${filtros.terminal_id}/saldo`, etiqueta: `Cliente ${nombresCliente.get(filtros.terminal_id) ?? ""}` }
      : filtros.empresa_id
        ? { ruta: `/empresas/${filtros.empresa_id}/saldo`, etiqueta: nombresEmpresa.get(filtros.empresa_id) ?? "Empresa" }
        : null;

  return (
    <>
      <EncabezadoPagina
        titulo="Salidas de dinero"
        descripcion="Cada salida pertenece a un proyecto. Control paralelo: no se bloquean, pero se avisa si el saldo queda negativo."
        acciones={
          <Boton onClick={() => setRegistrando(true)}>
            <Icono nombre="mas" className="size-4" />
            Registrar salida
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
          <Campo etiqueta="Buscar en destino">
            {(id) => <Input id={id} type="search" maxLength={100} placeholder="Ej. nómina" value={texto} onChange={(e) => setTexto(e.target.value)} />}
          </Campo>
          <Campo etiqueta="Desde">
            {(id) => <Input id={id} type="date" value={filtros.desde} onChange={(e) => cambiar({ desde: e.target.value })} />}
          </Campo>
          <Campo etiqueta="Hasta">
            {(id) => <Input id={id} type="date" value={filtros.hasta} onChange={(e) => cambiar({ hasta: e.target.value })} />}
          </Campo>
        </div>
        {(saldo || activos) && (
          <div className="mt-3 flex flex-wrap items-center justify-between gap-2">
            {saldo ? <SaldoFiltrado ruta={saldo.ruta} etiqueta={saldo.etiqueta} /> : <span />}
            {activos && (
              <Boton variante="fantasma" tamano="sm" onClick={() => { setTexto(""); limpiar(); }}>Limpiar filtros</Boton>
            )}
          </div>
        )}
      </Tarjeta>

      <ErrorApi error={error} className="mb-4" />

      <Tarjeta className={isFetching && !isLoading ? "opacity-70 transition-opacity" : undefined}>
        {isLoading ? (
          <Cargando />
        ) : !data?.items.length ? (
          <Vacio
            titulo={activos ? "Ninguna salida coincide con los filtros" : "Aún no hay salidas"}
            accion={!activos && <Boton onClick={() => setRegistrando(true)}>Registrar la primera</Boton>}
          />
        ) : (
          <>
            <Tabla>
              <thead>
                <tr>
                  <Th>Fecha</Th>
                  <Th>Empresa / cliente / proyecto</Th>
                  <Th>Destino</Th>
                  <Th>Método</Th>
                  <Th derecha>Monto</Th>
                  <Th><span className="sr-only">Acciones</span></Th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {data.items.map((s) => (
                  <tr key={s.id} className="hover:bg-slate-50">
                    <Td className="whitespace-nowrap">{fecha(s.fecha)}</Td>
                    <Td>
                      <p className="font-medium text-slate-900">{nombresEmpresa.get(s.empresa_id) ?? "—"}</p>
                      <p className="text-xs text-slate-500">
                        {nombresCliente.get(s.terminal_id) ?? "—"} · {nombresProyecto.get(s.proyecto_id) ?? "—"}
                      </p>
                    </Td>
                    <Td>
                      <p>{s.destino}</p>
                      {s.observaciones && <p className="text-xs text-slate-500">{s.observaciones}</p>}
                    </Td>
                    <Td className="whitespace-nowrap">{nombresMetodo.get(s.metodo_pago_id) ?? "—"}</Td>
                    <Td derecha className="font-medium text-slate-900"><Monto valor={s.monto} /></Td>
                    <Td className="whitespace-nowrap text-right">
                      <Boton variante="fantasma" tamano="sm" onClick={() => setEditando(s)} aria-label="Corregir">
                        <Icono nombre="lapiz" className="size-4" />
                      </Boton>
                      <Boton variante="fantasma" tamano="sm" onClick={() => setEliminando(s)} aria-label="Eliminar"
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

      <RegistrarSalida abierto={registrando} onCerrar={() => setRegistrando(false)}
        inicial={{ empresaId: filtros.empresa_id, clienteId: filtros.terminal_id, proyectoId: filtros.proyecto_id }} />
      <EditarSalida salida={editando} onCerrar={() => setEditando(null)} />
      <ConfirmarEliminacion
        abierto={eliminando !== null}
        titulo="Eliminar salida"
        onCerrar={() => setEliminando(null)}
        onConfirmar={async (motivo) => {
          await api.delete(`/salidas/${eliminando!.id}`, { motivo });
          invalidar();
          avisar("Salida eliminada");
        }}
      >
        {eliminando && (
          <p>
            Se eliminará la salida del <strong>{fecha(eliminando.fecha)}</strong> por{" "}
            <strong><Monto valor={eliminando.monto} /></strong> ({eliminando.destino}).
          </p>
        )}
      </ConfirmarEliminacion>
    </>
  );
}
