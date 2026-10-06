import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";
import { cn } from "../lib/cn";
import type { Empresa } from "../lib/types";

/** El logo es un recurso protegido: se descarga con el token y se muestra como object URL. */
export function LogoEmpresa({ empresa, className }: { empresa: Empresa; className?: string }) {
  const ruta = empresa.archivos.logo;
  const { data: blob } = useQuery({
    queryKey: ["empresas", empresa.id, "logo", ruta],
    queryFn: () => api.blob(ruta!),
    enabled: Boolean(ruta),
    staleTime: Infinity,
  });
  const [url, setUrl] = useState<string | null>(null);

  useEffect(() => {
    if (!blob) {
      setUrl(null);
      return;
    }
    const u = URL.createObjectURL(blob);
    setUrl(u);
    return () => URL.revokeObjectURL(u);
  }, [blob]);

  const iniciales = empresa.nombre
    .split(/\s+/)
    .filter((p) => p.length > 2)
    .slice(0, 2)
    .map((p) => p[0])
    .join("")
    .toUpperCase() || empresa.nombre.slice(0, 2).toUpperCase();

  return (
    <div className={cn("flex shrink-0 items-center justify-center overflow-hidden rounded-lg bg-teal-50 ring-1 ring-teal-100", className ?? "size-10")}>
      {url ? (
        <img src={url} alt={`Logo de ${empresa.nombre}`} className="size-full object-contain" />
      ) : (
        <span className="text-sm font-semibold text-teal-700">{iniciales}</span>
      )}
    </div>
  );
}
