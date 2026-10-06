"""Pobla la base de datos con datos de prueba.

    python -m app.seed            # solo si la base está vacía
    python -m app.seed --reset    # BORRA todo y vuelve a poblar

Crea 1 admin y 4 contadores (contraseña para todos: carlos12345678), 8 empresas,
terminales con cambios de porcentaje, ~45 días de movimientos, salidas,
algunas correcciones y sus registros en la bitácora. Los datos son siempre los
mismos (semilla fija), así que se pueden comparar resultados entre corridas.
"""

import argparse
import random
import sys
from datetime import datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import func, select, text

from app.core.config import settings
from app.core.security import hash_password
from app.core.tiempo import hoy
from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.models import (
    AccionBitacora,
    Empresa,
    HistorialPorcentajeTerminal,
    MovimientoTerminal,
    Rol,
    SalidaEmpresa,
    TerminalBancaria,
    Usuario,
)
from app.services.bitacora import instantanea, registrar
from app.services.porcentajes import porcentaje_vigente
from app.services.saldos import saldo_empresa

PASSWORD = "carlos12345678"
DIAS = 45
rnd = random.Random(42)
zona = ZoneInfo(settings.TIMEZONE)

ADMIN = ("Carlos", "Administrador", "admin@controlbancario.mx")
CONTADORES = [
    ("Juan", "Pérez López", "juan@controlbancario.mx"),
    ("Pedro", "Gómez Ruiz", "pedro@controlbancario.mx"),
    ("María", "Rodríguez Soto", "maria@controlbancario.mx"),
    ("Laura", "Sánchez Vega", "laura@controlbancario.mx"),
]
# (nombre, banco, terminales, venta diaria típica) — dos empresas por contador, en orden
EMPRESAS = [
    ("Mariscos El Güero", "BBVA", 3, 9000),
    ("Farmacia San Miguel", "Banorte", 2, 12000),
    ("Taller Mecánico Rivera", "Santander", 1, 6000),
    ("Papelería La Estrella", "BBVA", 2, 3500),
    ("Café del Puerto", "HSBC", 2, 5000),
    ("Ferretería Baja", "Banamex", 3, 15000),
    ("Panadería La Espiga", "Banorte", 1, 4000),
    ("Boutique Coral", "Santander", 2, 7000),
]
DESTINOS = [
    "Pago a proveedor",
    "Nómina quincenal",
    "Renta del local",
    "Pago de luz CFE",
    "Retiro del dueño",
    "Pago de impuestos SAT",
    "Compra de mercancía",
]


def dinero(valor: float) -> Decimal:
    return Decimal(str(round(valor, 2)))


def momento(fecha, hora: int, minuto: int = 0) -> datetime:
    return datetime.combine(fecha, time(hora, minuto), tzinfo=zona)


def base_vacia() -> bool:
    with SessionLocal() as db:
        return db.scalar(select(func.count()).select_from(Usuario)) == 0


def borrar_todo() -> None:
    tablas = ", ".join(t.name for t in reversed(Base.metadata.sorted_tables))
    with engine.begin() as conn:
        # TRUNCATE no dispara el trigger que protege la bitácora (ese es por fila).
        conn.execute(text(f"TRUNCATE {tablas} CASCADE"))


def poblar() -> None:
    hoy_ = hoy()
    inicio = hoy_ - timedelta(days=DIAS)
    password_hash = hash_password(PASSWORD)  # un solo hash: bcrypt es lento a propósito

    with SessionLocal() as db:
        # ---------------------------------------------------------- usuarios
        admin = Usuario(nombre=ADMIN[0], apellidos=ADMIN[1], correo=ADMIN[2],
                        password_hash=password_hash, rol=Rol.ADMIN)
        db.add(admin)
        db.flush()
        registrar(db, usuario_id=None, entidad="Usuario", entidad_id=admin.id,
                  accion=AccionBitacora.CREAR_USUARIO, detalle={"correo": admin.correo, "origen": "seed"})

        contadores = []
        for nombre, apellidos, correo in CONTADORES:
            c = Usuario(nombre=nombre, apellidos=apellidos, correo=correo,
                        password_hash=password_hash, rol=Rol.CONTADOR)
            db.add(c)
            db.flush()
            registrar(db, usuario_id=admin.id, entidad="Usuario", entidad_id=c.id,
                      accion=AccionBitacora.CREAR_USUARIO, detalle={"correo": correo, "rol": "contador"})
            contadores.append(c)

        # ------------------------------------------------ empresas y terminales
        terminales_por_empresa: dict = {}
        empresas = []
        for i, (nombre, banco, n_terminales, venta) in enumerate(EMPRESAS):
            dueno = contadores[i // 2]
            empresa = Empresa(
                usuario_id=dueno.id,
                nombre=nombre,
                csf=f"{nombre[:3].upper()}{rnd.randint(100000, 999999)}XX{rnd.randint(0, 9)}",
                banco=banco,
                numero_cuenta=str(rnd.randint(10**9, 10**10 - 1)),
                clabe="".join(str(rnd.randint(0, 9)) for _ in range(18)),
            )
            db.add(empresa)
            db.flush()
            empresas.append((empresa, dueno, venta))
            terminales_por_empresa[empresa.id] = []

            for t in range(n_terminales):
                terminal = TerminalBancaria(
                    empresa_id=empresa.id,
                    identificador_terminal=f"TPV-{rnd.randint(1000, 9999)}",
                    datos_extra={"modelo": rnd.choice(["Verifone V200c", "Ingenico Move/5000", "Clip Total"])},
                )
                db.add(terminal)
                db.flush()
                pct_inicial = dinero(rnd.uniform(2.5, 3.9))
                db.add(HistorialPorcentajeTerminal(terminal_id=terminal.id, porcentaje=pct_inicial,
                                                   fecha_inicio_vigencia=inicio))
                # La primera terminal de cada empresa cambió de % hace 15 días
                if t == 0:
                    cambio = hoy_ - timedelta(days=15)
                    db.flush()
                    db.execute(
                        HistorialPorcentajeTerminal.__table__.update()
                        .where(HistorialPorcentajeTerminal.terminal_id == terminal.id)
                        .values(fecha_fin_vigencia=cambio)
                    )
                    nuevo = pct_inicial + Decimal("0.50")
                    db.add(HistorialPorcentajeTerminal(terminal_id=terminal.id, porcentaje=nuevo,
                                                       fecha_inicio_vigencia=cambio))
                    registrar(db, usuario_id=dueno.id, entidad="TerminalBancaria", entidad_id=terminal.id,
                              accion=AccionBitacora.CAMBIO_PORCENTAJE,
                              detalle={"anterior": pct_inicial, "nuevo": nuevo, "vigente_desde": cambio,
                                       "movimientos_recalculados": 0, "motivo": "Ajuste de tarifa del banco"})
                terminales_por_empresa[empresa.id].append(terminal)
        db.flush()

        # -------------------------------------------------------- movimientos
        movimientos = []
        for empresa, dueno, venta in empresas:
            terminales = terminales_por_empresa[empresa.id]
            for d in range(DIAS + 1):
                fecha = inicio + timedelta(days=d)
                for terminal in terminales:
                    if rnd.random() < 0.15:  # días sin venta o sin captura
                        continue
                    monto = dinero(venta / len(terminales) * rnd.uniform(0.5, 1.6))
                    mov = MovimientoTerminal(
                        terminal_id=terminal.id,
                        usuario_id=dueno.id,
                        fecha_movimiento=fecha,
                        monto_bruto=monto,
                        porcentaje_aplicado=porcentaje_vigente(db, terminal.id, fecha),
                        fecha_captura=momento(fecha, 21, rnd.randint(0, 59)),
                        observaciones=rnd.choice([None, None, None, "Incluye ventas con tarjeta de crédito"]),
                    )
                    db.add(mov)
                    movimientos.append((mov, dueno))

        # Una terminal inactiva por empresa con más de una terminal (conserva su historial)
        for empresa, dueno, _ in empresas:
            terminales = terminales_por_empresa[empresa.id]
            if len(terminales) > 2:
                terminales[-1].activa = False
                registrar(db, usuario_id=dueno.id, entidad="TerminalBancaria", entidad_id=terminales[-1].id,
                          accion=AccionBitacora.DESACTIVAR)
        db.flush()

        # ------------------------------------------------ correcciones (bitácora)
        for mov, dueno in rnd.sample(movimientos, 6):
            db.refresh(mov)
            antes = instantanea(mov, ("monto_bruto", "monto_neto", "fecha_movimiento"))
            mov.monto_bruto = dinero(float(mov.monto_bruto) / 10)
            db.flush()
            db.refresh(mov)
            registrar(db, usuario_id=dueno.id, entidad="MovimientoTerminal", entidad_id=mov.id,
                      accion=AccionBitacora.EDITAR_MOVIMIENTO,
                      detalle={"antes": antes,
                               "despues": instantanea(mov, ("monto_bruto", "monto_neto", "fecha_movimiento")),
                               "motivo": "Capturé un cero de más"})

        # ------------------------------------------------------------ salidas
        for i, (empresa, dueno, venta) in enumerate(empresas):
            for d in range(4, DIAS + 1, rnd.randint(4, 7)):
                fecha = inicio + timedelta(days=d)
                db.add(SalidaEmpresa(
                    empresa_id=empresa.id,
                    usuario_id=dueno.id,
                    monto=dinero(venta * rnd.uniform(2.0, 4.5)),
                    destino=rnd.choice(DESTINOS),
                    fecha=fecha,
                    observaciones=rnd.choice([None, "Transferencia realizada por contabilidad"]),
                    fecha_registro=momento(fecha, 12),
                ))
            # Boutique Coral queda en negativo a propósito, para probar la advertencia
            if empresa.nombre == "Boutique Coral":
                db.flush()
                faltante = saldo_empresa(db, empresa.id) + Decimal("8500.00")
                db.add(SalidaEmpresa(empresa_id=empresa.id, usuario_id=dueno.id, monto=faltante,
                                     destino="Liquidación a proveedor de temporada", fecha=hoy_,
                                     observaciones="Faltan ingresos por capturar"))

        db.commit()

        # ------------------------------------------------------------ resumen
        print(f"\nBase poblada ({DIAS} días, del {inicio} al {hoy_}). Contraseña de todos: {PASSWORD}\n")
        print(f"  admin      {ADMIN[2]}")
        for c in contadores:
            print(f"  contador   {c.correo}")
        print(f"\n  {'Empresa':<26}{'Contador':<28}{'Terminales':>11}{'Saldo':>16}")
        for empresa, dueno, _ in empresas:
            saldo = saldo_empresa(db, empresa.id)
            print(f"  {empresa.nombre:<26}{dueno.correo:<28}{len(terminales_por_empresa[empresa.id]):>11}"
                  f"{saldo:>16,.2f}")
        total_mov = db.scalar(select(func.count()).select_from(MovimientoTerminal))
        total_sal = db.scalar(select(func.count()).select_from(SalidaEmpresa))
        print(f"\n  {total_mov} movimientos y {total_sal} salidas.\n")


def main() -> int:
    parser = argparse.ArgumentParser(prog="python -m app.seed")
    parser.add_argument("--reset", action="store_true", help="Borra TODOS los datos antes de poblar")
    args = parser.parse_args()

    if args.reset:
        if settings.ENVIRONMENT == "production":
            print("No se permite --reset con ENVIRONMENT=production", file=sys.stderr)
            return 1
        borrar_todo()
    elif not base_vacia():
        print("La base ya tiene datos. Usa --reset para borrarlos y volver a poblar.", file=sys.stderr)
        return 1
    poblar()
    return 0


if __name__ == "__main__":
    sys.exit(main())