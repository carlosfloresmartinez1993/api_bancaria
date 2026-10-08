from datetime import timedelta

from sqlalchemy import select

from app.core.tiempo import hoy
from app.db.session import SessionLocal
from app.models import MetodoPago


def dia(n: int) -> str:
    """Fecha relativa a hoy: dia(-3) = hace tres días."""
    return (hoy() + timedelta(days=n)).isoformat()


def metodo(nombre: str = "Transferencia") -> str:
    with SessionLocal() as db:
        return str(db.scalar(select(MetodoPago.id).where(MetodoPago.nombre == nombre)))


def crear_empresa(client, h, nombre="Empresa Uno", **extra):
    r = client.post("/empresas", json={"nombre": nombre, **extra}, headers=h)
    assert r.status_code == 201, r.text
    return r.json()


def crear_cliente(client, h, empresa_id=None, ident="T-001", **extra):
    """Sin empresa_id, el cliente queda sin empresa."""
    datos = {"empresa_id": empresa_id, "identificador_terminal": ident, **extra}
    r = client.post("/terminales", json=datos, headers=h)
    assert r.status_code == 201, r.text
    return r.json()


def crear_proyecto(client, h, terminal_id, nombre="P1", porcentaje="3.00", desde=None):
    datos = {"terminal_id": terminal_id, "nombre": nombre, "porcentaje_inicial": porcentaje,
             "vigente_desde": desde or dia(-30)}
    r = client.post("/proyectos", json=datos, headers=h)
    assert r.status_code == 201, r.text
    return r.json()


def proyecto_nuevo(client, h, porcentaje="3.00", desde=None, empresa="Empresa Uno"):
    """Empresa → cliente → proyecto en un paso."""
    empresa = crear_empresa(client, h, empresa)
    cliente = crear_cliente(client, h, empresa["id"])
    return crear_proyecto(client, h, cliente["id"], porcentaje=porcentaje, desde=desde)


def capturar(client, h, proyecto_id, monto, fecha=None, **extra):
    datos = {"proyecto_id": proyecto_id, "monto_bruto": monto, "fecha_movimiento": fecha or dia(0),
             "metodo_pago_id": metodo(), **extra}
    r = client.post("/movimientos", headers=h, json=datos)
    assert r.status_code == 201, r.text
    return r.json()


def registrar_salida(client, h, proyecto_id, monto, destino="Proveedor", fecha=None, **extra):
    datos = {"proyecto_id": proyecto_id, "monto": monto, "destino": destino, "metodo_pago_id": metodo(),
             **({"fecha": fecha} if fecha else {}), **extra}
    r = client.post("/salidas", headers=h, json=datos)
    assert r.status_code == 201, r.text
    return r.json()
