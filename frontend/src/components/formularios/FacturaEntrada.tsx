import { useEffect, useState } from "react";
import { api } from "../../lib/api";
import { fecha, fechaHoraLocal } from "../../lib/format";
import { useInvalidarDinero } from "../../lib/invalidar";
import type { Movimiento } from "../../lib/types";
import { Icono } from "../Icono";
import { useToast } from "../Toast";
import { Aviso, Boton, ErrorApi, Input, Modal, Monto, PieModal } from "../ui";

/** Debe coincidir con MAX_DOCUMENTO_MB del backend. */
export const MAX_FACTURA_MB = 5;

export function tamano(bytes: number): string {
  return bytes < 1024 * 1024 ? `${Math.max(1, Math.round(bytes / 1024))} KB` : `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

/** Revisión rápida en el navegador; el servidor vuelve a validar el contenido real del archivo. */
export function problemaConPdf(archivo: File): string | null {
  if (!archivo.name.toLowerCase().endsWith(".pdf") && archivo.type !== "application/pdf") return "Solo se aceptan archivos PDF";
  if (archivo.size > MAX_FACTURA_MB * 1024 * 1024) return `El archivo excede el máximo de ${MAX_FACTURA_MB} MB`;
  return null;
}

export function subirFactura(movimientoId: string, archivo: File) {
  const datos = new FormData();
  datos.append("archivo", archivo);
  return api.put<Movimiento>(`/movimientos/${movimientoId}/documento`, datos);
}

/** Abre el PDF en otra pestaña. La ventana se abre antes de descargar para que el navegador no la bloquee. */
export async function verFactura(movimientoId: string) {
  const ventana = window.open("", "_blank");
  try {
    const blob = await api.blob(`/movimientos/${movimientoId}/documento`);
    const url = URL.createObjectURL(new Blob([blob], { type: "application/pdf" }));
    if (ventana) ventana.location.href = url;
    else window.location.href = url;
    setTimeout(() => URL.revokeObjectURL(url), 60_000);
  } catch (err) {
    ventana?.close();
    throw err;
  }
}

/** Campo para elegir un PDF (opcional). */
export function SelectorPdf({ id, archivo, onCambiar }: { id?: string; archivo: File | null; onCambiar: (f: File | null) => void }) {
  const [problema, setProblema] = useState<string | null>(null);
  // Al limpiar el archivo desde fuera (p. ej. tras guardar), se vuelve a montar el campo vacío.
  const [version, setVersion] = useState(0);
  useEffect(() => {
    if (!archivo) setVersion((v) => v + 1);
  }, [archivo]);
  return (
    <div className="space-y-1">
      <Input
        key={version}
        id={id}
        type="file"
        accept="application/pdf,.pdf"
        className="file:mr-3 file:rounded-md file:border-0 file:bg-teal-50 file:px-3 file:py-1 file:text-sm file:font-medium file:text-teal-800"
        onChange={(e) => {
          const f = e.target.files?.[0] ?? null;
          const p = f ? problemaConPdf(f) : null;
          setProblema(p);
          onCambiar(p ? null : f);
          if (p) e.target.value = "";
        }}
      />
      {problema && <p className="text-xs text-rose-600">{problema}</p>}
      {archivo && <p className="text-xs text-slate-500">{archivo.name} · {tamano(archivo.size)}</p>}
    </div>
  );
}

/** Ver, subir, reemplazar o quitar la factura de una entrada. */
export function FacturaEntrada({ movimiento, onCerrar }: { movimiento: Movimiento | null; onCerrar: () => void }) {
  const avisar = useToast();
  const invalidar = useInvalidarDinero();
  const [actual, setActual] = useState<Movimiento | null>(null);
  const [archivo, setArchivo] = useState<File | null>(null);
  const [quitando, setQuitando] = useState(false);
  const [motivo, setMotivo] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [enviando, setEnviando] = useState(false);

  useEffect(() => {
    setActual(movimiento);
    setArchivo(null);
    setQuitando(false);
    setMotivo("");
    setError(null);
  }, [movimiento]);

  if (!movimiento || !actual) return null;
  const tiene = Boolean(actual.documento_nombre);

  async function ejecutar(accion: () => Promise<Movimiento>, mensaje: string) {
    setEnviando(true);
    setError(null);
    try {
      setActual(await accion());
      invalidar();
      avisar(mensaje);
      setArchivo(null);
      setQuitando(false);
      setMotivo("");
    } catch (err) {
      setError(err);
    } finally {
      setEnviando(false);
    }
  }

  async function ver() {
    setError(null);
    try {
      await verFactura(actual!.id);
    } catch (err) {
      setError(err);
    }
  }

  return (
    <Modal abierto titulo="Factura de la entrada" onCerrar={onCerrar}
      descripcion={<>Entrada del {fecha(actual.fecha_movimiento)} por <Monto valor={actual.monto_bruto} /></>}>
      <div className="space-y-4">
        {tiene ? (
          <div className="flex items-center gap-3 rounded-lg p-3 ring-1 ring-slate-200">
            <Icono nombre="documento" className="size-8 shrink-0 text-rose-600" />
            <div className="min-w-0 flex-1">
              <p className="truncate font-medium text-slate-900" title={actual.documento_nombre!}>{actual.documento_nombre}</p>
              <p className="text-xs text-slate-500">
                {tamano(actual.documento_tamano_bytes ?? 0)} · subida el {fechaHoraLocal(actual.documento_subido_en)}
              </p>
            </div>
            <Boton variante="secundario" tamano="sm" onClick={ver}>Ver</Boton>
          </div>
        ) : (
          <Aviso tono="info">Esta entrada aún no tiene factura.</Aviso>
        )}

        {!quitando && (
          <div className="space-y-2">
            <p className="text-sm font-medium text-slate-700">{tiene ? "Reemplazar por otro PDF" : "Subir factura (PDF)"}</p>
            <SelectorPdf archivo={archivo} onCambiar={setArchivo} />
            <p className="text-xs text-slate-500">Máximo {MAX_FACTURA_MB} MB. {tiene && "El archivo anterior se borra."}</p>
          </div>
        )}

        {quitando && (
          <div className="space-y-2 rounded-lg bg-rose-50 p-3 ring-1 ring-rose-200">
            <p className="text-sm text-rose-800">Se quitará la factura de esta entrada. Queda registrado en la bitácora.</p>
            <Input placeholder="Motivo (opcional)" maxLength={500} value={motivo} onChange={(e) => setMotivo(e.target.value)} />
          </div>
        )}

        <ErrorApi error={error} />
        <PieModal>
          {tiene && !quitando && (
            <Boton variante="fantasma" className="mr-auto text-rose-600 hover:text-rose-700" onClick={() => setQuitando(true)}>
              <Icono nombre="basura" className="size-4" />
              Quitar factura
            </Boton>
          )}
          {quitando ? (
            <>
              <Boton variante="secundario" onClick={() => setQuitando(false)}>Cancelar</Boton>
              <Boton variante="peligro" cargando={enviando}
                onClick={() => ejecutar(async () => {
                  await api.delete(`/movimientos/${actual.id}/documento`, { motivo: motivo.trim() || undefined });
                  return { ...actual, documento_nombre: null, documento_tamano_bytes: null, documento_subido_en: null };
                }, "Factura quitada")}>
                Quitar
              </Boton>
            </>
          ) : (
            <>
              <Boton variante="secundario" onClick={onCerrar}>Cerrar</Boton>
              <Boton disabled={!archivo} cargando={enviando}
                onClick={() => archivo && ejecutar(() => subirFactura(actual.id, archivo), tiene ? "Factura reemplazada" : "Factura subida")}>
                <Icono nombre="subir" className="size-4" />
                {tiene ? "Reemplazar" : "Subir"}
              </Boton>
            </>
          )}
        </PieModal>
      </div>
    </Modal>
  );
}
