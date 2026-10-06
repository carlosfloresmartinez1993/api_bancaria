from datetime import date, timedelta

from app.core.tiempo import hoy


def dia(n: int) -> str:
    """Fecha relativa a hoy: dia(-3) = hace tres días."""
    return (hoy() + timedelta(days=n)).isoformat()


def crear_empresa(client, h, nombre="Empresa Uno", **extra):
    datos = {"nombre": nombre, "csf": "CSF123", "banco": "BBVA", "numero_cuenta": "0123456789", **extra}
    r = client.post("/empresas", json=datos, headers=h)
    assert r.status_code == 201, r.text
    return r.json()


def crear_terminal(client, h, empresa_id, porcentaje="3.00", desde=None, ident="T-001"):
    datos = {"empresa_id": empresa_id, "identificador_terminal": ident, "porcentaje_inicial": porcentaje,
             "vigente_desde": desde or dia(-30)}
    r = client.post("/terminales", json=datos, headers=h)
    assert r.status_code == 201, r.text
    return r.json()


def capturar(client, h, terminal_id, monto, fecha=None):
    r = client.post("/movimientos", headers=h,
                    json={"terminal_id": terminal_id, "monto_bruto": monto, "fecha_movimiento": fecha or dia(0)})
    assert r.status_code == 201, r.text
    return r.json()
