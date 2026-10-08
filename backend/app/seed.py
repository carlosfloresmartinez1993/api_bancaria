"""Pobla la base de datos con datos de prueba.

    python -m app.seed            # solo si la base está vacía
    python -m app.seed --reset    # BORRA todo y vuelve a poblar

Crea 1 admin y 4 contadores (contraseña para todos: carlos12345678), 8 empresas,
cada una con sus clientes (terminales) y cada cliente con 1 a 3 proyectos con su
propio % de comisión. Genera ~45 días de entradas y salidas con distintos métodos
de pago, algunas correcciones y sus registros en la bitácora. Los datos son
siempre los mismos (semilla fija), así que se pueden comparar resultados entre
corridas.
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
    HistorialPorcentajeProyecto,
    MetodoPago,
    Movimiento,
    Proyecto,
    Rol,
    Salida,
    TerminalBancaria,
    Usuario,
)
from app.services.bitacora import instantanea, registrar
from app.services.porcentajes import porcentaje_vigente
from app.services.saldos import totales

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
METODOS = ["Transferencia", "Depósito", "Efectivo"]
# (nombre, banco o None, clientes, venta diaria típica por proyecto) — dos empresas por contador, en orden
EMPRESAS = [
    ("Mariscos El Güero", "BBVA", 2, 4500),
    ("Farmacia San Miguel", "Banorte", 2, 6000),
    ("Taller Mecánico Rivera", None, 1, 5000),
    ("Papelería La Estrella", "BBVA", 1, 2500),
    ("Café del Puerto", "HSBC", 2, 2800),
    ("Ferretería Baja", "Banamex", 3, 5500),
    ("Panadería La Espiga", None, 1, 3000),
    ("Boutique Coral", "Santander", 2, 3500),
]
PROYECTOS = ["Proyecto Norte", "Proyecto Centro", "Proyecto Sur", "Mostrador", "Eventos", "Mayoreo"]
# Clientes sin empresa: (índice del contador responsable, identificador, nombres de proyectos, venta típica)
INDEPENDIENTES = [
    (0, "Cliente libre 7001", ["Servicios", "Eventos"], 2500),
    (3, "Cliente libre 7002", ["Mostrador"], 1800),
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
        # ------------------------------------------------- métodos de pago
        metodos = []
        for nombre in METODOS:
            metodo = db.scalar(select(MetodoPago).where(MetodoPago.nombre == nombre))
            if metodo is None:
                metodo = MetodoPago(nombre=nombre)
                db.add(metodo)
            metodos.append(metodo)
        db.flush()

        def metodo_al_azar() -> MetodoPago:
            return rnd.choices(metodos, weights=[6, 3, 1])[0]

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

        # --------------------------------------- empresas, clientes y proyectos
        empresas = []  # (empresa, dueño, venta, [proyectos])
        for i, (nombre, banco, n_clientes, venta) in enumerate(EMPRESAS):
            dueno = contadores[i // 2]
            empresa = Empresa(
                usuario_id=dueno.id,
                nombre=nombre,
                csf=f"{nombre[:3].upper()}{rnd.randint(100000, 999999)}XX{rnd.randint(0, 9)}" if banco else None,
                banco=banco,
                numero_cuenta=str(rnd.randint(10**9, 10**10 - 1)) if banco else None,
                clabe="".join(str(rnd.randint(0, 9)) for _ in range(18)) if banco else None,
            )
            db.add(empresa)
            db.flush()
            proyectos_empresa = []
            for c in range(n_clientes):
                terminal = TerminalBancaria(empresa_id=empresa.id, usuario_id=dueno.id,
                                            identificador_terminal=str(rnd.randint(1000, 9999)))
                db.add(terminal)
                db.flush()
                for nombre_proyecto in rnd.sample(PROYECTOS, rnd.randint(1, 3)):
                    proyecto = Proyecto(terminal_id=terminal.id, nombre=nombre_proyecto)
                    db.add(proyecto)
                    db.flush()
                    pct = dinero(rnd.choice([2, 2.5, 3, 3.5, 4, 5, 6, 9]))
                    db.add(HistorialPorcentajeProyecto(proyecto_id=proyecto.id, porcentaje=pct,
                                                      fecha_inicio_vigencia=inicio))
                    proyectos_empresa.append((proyecto, terminal, pct))
            # El primer proyecto de cada empresa cambió de % hace 15 días
            proyecto, _, pct = proyectos_empresa[0]
            cambio = hoy_ - timedelta(days=15)
            db.flush()
            db.execute(
                HistorialPorcentajeProyecto.__table__.update()
                .where(HistorialPorcentajeProyecto.proyecto_id == proyecto.id)
                .values(fecha_fin_vigencia=cambio)
            )
            nuevo = pct + Decimal("0.50")
            db.add(HistorialPorcentajeProyecto(proyecto_id=proyecto.id, porcentaje=nuevo, fecha_inicio_vigencia=cambio))
            registrar(db, usuario_id=dueno.id, entidad="Proyecto", entidad_id=proyecto.id,
                      accion=AccionBitacora.CAMBIO_PORCENTAJE,
                      detalle={"anterior": pct, "nuevo": nuevo, "vigente_desde": cambio,
                               "movimientos_recalculados": 0, "motivo": "Ajuste de tarifa del banco"})
            empresas.append((empresa, dueno, venta, [p for p, _, _ in proyectos_empresa]))

        # Clientes sin empresa (empresa = None en la lista, para reutilizar los mismos ciclos)
        for i, identificador, nombres_proyectos, venta in INDEPENDIENTES:
            dueno = contadores[i]
            terminal = TerminalBancaria(empresa_id=None, usuario_id=dueno.id, identificador_terminal=identificador)
            db.add(terminal)
            db.flush()
            proyectos_libres = []
            for nombre_proyecto in nombres_proyectos:
                proyecto = Proyecto(terminal_id=terminal.id, nombre=nombre_proyecto)
                db.add(proyecto)
                db.flush()
                db.add(HistorialPorcentajeProyecto(proyecto_id=proyecto.id, porcentaje=dinero(rnd.choice([3, 4, 5])),
                                                  fecha_inicio_vigencia=inicio))
                proyectos_libres.append(proyecto)
            empresas.append((None, dueno, venta, proyectos_libres))
        db.flush()

        # ---------------------------------------------------------- entradas
        movimientos = []
        for empresa, dueno, venta, proyectos in empresas:
            for d in range(DIAS + 1):
                fecha = inicio + timedelta(days=d)
                for proyecto in proyectos:
                    if rnd.random() < 0.25:  # días sin venta o sin captura
                        continue
                    mov = Movimiento(
                        proyecto_id=proyecto.id,
                        usuario_id=dueno.id,
                        metodo_pago_id=metodo_al_azar().id,
                        fecha_movimiento=fecha,
                        monto_bruto=dinero(venta * rnd.uniform(0.5, 1.6)),
                        porcentaje_aplicado=porcentaje_vigente(db, proyecto.id, fecha),
                        requiere_factura=rnd.random() < 0.3,
                        fecha_captura=momento(fecha, rnd.randint(9, 19), rnd.randint(0, 59)),
                        observaciones=rnd.choice([None, None, None, "Incluye ventas con tarjeta de crédito"]),
                    )
                    db.add(mov)
                    movimientos.append((mov, dueno))

        # Un proyecto inactivo en la empresa con más clientes (conserva su historial)
        for empresa, dueno, _, proyectos in empresas:
            if len(proyectos) > 4:
                proyectos[-1].activo = False
                registrar(db, usuario_id=dueno.id, entidad="Proyecto", entidad_id=proyectos[-1].id,
                          accion=AccionBitacora.DESACTIVAR)
        db.flush()

        # ------------------------------------------------ correcciones (bitácora)
        campos = ("monto_bruto", "monto_neto", "fecha_movimiento")
        for mov, dueno in rnd.sample(movimientos, 6):
            db.refresh(mov)
            antes = instantanea(mov, campos)
            mov.monto_bruto = dinero(float(mov.monto_bruto) / 10)
            db.flush()
            db.refresh(mov)
            registrar(db, usuario_id=dueno.id, entidad="Movimiento", entidad_id=mov.id,
                      accion=AccionBitacora.EDITAR_MOVIMIENTO,
                      detalle={"antes": antes, "despues": instantanea(mov, campos), "motivo": "Capturé un cero de más"})

        # ------------------------------------------------------------ salidas
        for empresa, dueno, venta, proyectos in empresas:
            for proyecto in proyectos:
                for d in range(4, DIAS + 1, rnd.randint(6, 9)):
                    fecha = inicio + timedelta(days=d)
                    db.add(Salida(
                        proyecto_id=proyecto.id,
                        usuario_id=dueno.id,
                        metodo_pago_id=metodo_al_azar().id,
                        monto=dinero(venta * rnd.uniform(3.0, 5.5)),
                        destino=rnd.choice(DESTINOS),
                        fecha=fecha,
                        observaciones=rnd.choice([None, "Transferencia realizada por contabilidad"]),
                        fecha_registro=momento(fecha, 12),
                    ))
            # Un proyecto de Boutique Coral queda en negativo a propósito, para probar la advertencia
            if empresa and empresa.nombre == "Boutique Coral":
                db.flush()
                proyecto = proyectos[0]
                faltante = totales(db, proyecto_id=proyecto.id).saldo + Decimal("8500.00")
                db.add(Salida(proyecto_id=proyecto.id, usuario_id=dueno.id, metodo_pago_id=metodos[0].id,
                              monto=faltante, destino="Liquidación a proveedor de temporada", fecha=hoy_,
                              observaciones="Faltan entradas por capturar"))

        db.commit()

        # ------------------------------------------------------------ resumen
        print(f"\nBase poblada ({DIAS} días, del {inicio} al {hoy_}). Contraseña de todos: {PASSWORD}\n")
        print(f"  admin      {ADMIN[2]}")
        for c in contadores:
            print(f"  contador   {c.correo}")
        print(f"\n  {'Empresa':<26}{'Contador':<28}{'Clientes':>9}{'Proyectos':>10}{'Saldo':>16}")
        for empresa, dueno, _, proyectos in empresas:
            clientes = len({p.terminal_id for p in proyectos})
            if empresa:
                saldo, nombre = totales(db, empresa_id=empresa.id).saldo, empresa.nombre
            else:
                saldo = sum((totales(db, terminal_id=t).saldo for t in {p.terminal_id for p in proyectos}), Decimal(0))
                nombre = "(sin empresa)"
            print(f"  {nombre:<26}{dueno.correo:<28}{clientes:>9}{len(proyectos):>10}{saldo:>16,.2f}")
        total_mov = db.scalar(select(func.count()).select_from(Movimiento))
        total_sal = db.scalar(select(func.count()).select_from(Salida))
        print(f"\n  {total_mov} entradas y {total_sal} salidas.\n")


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
