import { useState, type FormEvent } from "react";
import { Navigate, useLocation, useNavigate } from "react-router";
import { useAuth } from "../auth/AuthContext";
import { Aviso, Boton, Campo, Input } from "../components/ui";

export default function Login() {
  const { usuario, entrar, aviso } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const destino = (location.state as { desde?: string } | null)?.desde ?? "/";

  const [correo, setCorreo] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);

  if (usuario) return <Navigate to={destino} replace />;

  async function enviar(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setEnviando(true);
    try {
      await entrar(correo.trim(), password);
      navigate(destino, { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo iniciar sesión");
    } finally {
      setEnviando(false);
    }
  }

  return (
    <div className="flex min-h-dvh">
      <div className="relative hidden flex-1 flex-col justify-between overflow-hidden bg-teal-900 p-12 text-white lg:flex">
        <div className="flex items-center gap-3">
          <img src="/favicon.svg" alt="" className="size-10" />
          <span className="text-lg font-semibold">Control de Clientes</span>
        </div>
        <div className="relative z-10 max-w-md">
          <h2 className="text-3xl font-semibold leading-tight">
            Ingresos por terminal y salidas de dinero, en un solo lugar.
          </h2>
          <p className="mt-4 text-teal-100/80">
            Captura los cortes de cada terminal, controla el saldo de cada empresa y genera reportes en Excel,
            PDF o CSV.
          </p>
        </div>
        <p className="text-sm text-teal-200/70">Control paralelo · los montos se calculan, no se almacenan</p>
        <div className="pointer-events-none absolute -right-32 -bottom-32 size-[28rem] rounded-full bg-teal-700/40" />
        <div className="pointer-events-none absolute -right-10 top-24 size-56 rounded-full bg-teal-600/20" />
      </div>

      <div className="flex flex-1 items-center justify-center px-4 py-12 sm:px-6">
        <div className="w-full max-w-sm">
          <div className="mb-8 flex items-center gap-3 lg:hidden">
            <img src="/favicon.svg" alt="" className="size-10" />
            <span className="text-lg font-semibold text-slate-900">Control de Clientes</span>
          </div>
          <h1 className="text-2xl font-semibold tracking-tight text-slate-900">Iniciar sesión</h1>
          <p className="mt-1 text-sm text-slate-500">Usa el correo y la contraseña que te dio el administrador.</p>

          <form onSubmit={enviar} className="mt-8 space-y-5">
            {aviso && !error && <Aviso tono="aviso">{aviso}</Aviso>}
            {error && <Aviso tono="peligro">{error}</Aviso>}
            <Campo etiqueta="Correo electrónico">
              {(id) => (
                <Input
                  id={id}
                  type="email"
                  autoComplete="email"
                  required
                  autoFocus
                  value={correo}
                  onChange={(e) => setCorreo(e.target.value)}
                />
              )}
            </Campo>
            <Campo etiqueta="Contraseña">
              {(id) => (
                <Input
                  id={id}
                  type="password"
                  autoComplete="current-password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
              )}
            </Campo>
            <Boton type="submit" cargando={enviando} className="w-full">
              Entrar
            </Boton>
          </form>
        </div>
      </div>
    </div>
  );
}
