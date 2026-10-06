from decimal import Decimal

from sqlalchemy import text

from app.db.session import engine
from tests.helpers import (
    capturar,
    crear_cliente,
    crear_empresa,
    crear_proyecto,
    dia,
    metodo,
    proyecto_nuevo,
    registrar_salida,
)


def test_empresa_solo_requiere_nombre(client, juan):
    r = client.post("/empresas", json={"nombre": "  Apple  "}, headers=juan[1])
    assert r.status_code == 201
    e = r.json()
    assert e["nombre"] == "Apple" and e["csf"] is None and e["banco"] is None and e["num_clientes"] == 0
    # Un texto opcional vacío se guarda como nulo
    r = client.patch(f"/empresas/{e['id']}", json={"banco": "BBVA", "csf": "  "}, headers=juan[1])
    assert r.json()["banco"] == "BBVA" and r.json()["csf"] is None
    assert client.patch(f"/empresas/{e['id']}", json={"nombre": None}, headers=juan[1]).status_code == 422


def test_neto_calculado_con_el_porcentaje_del_proyecto(client, juan):
    h = juan[1]
    empresa = crear_empresa(client, h)
    cliente = crear_cliente(client, h, empresa["id"])
    p1 = crear_proyecto(client, h, cliente["id"], "P1", porcentaje="2.00")
    p2 = crear_proyecto(client, h, cliente["id"], "P2", porcentaje="9.00")
    assert capturar(client, h, p1["id"], "1000.00")["monto_neto"] == "980.00"
    mov = capturar(client, h, p2["id"], "1000.00", requiere_factura=True)
    assert mov["porcentaje_aplicado"] == "9.00" and mov["comision"] == "90.00" and mov["monto_neto"] == "910.00"
    assert mov["requiere_factura"] is True
    assert mov["terminal_id"] == cliente["id"] and mov["empresa_id"] == empresa["id"]
    assert client.get(f"/terminales/{cliente['id']}", headers=h).json()["num_proyectos"] == 2
    assert client.get(f"/empresas/{empresa['id']}", headers=h).json()["num_clientes"] == 1


def test_porcentaje_segun_fecha_del_movimiento_y_recalculo_retroactivo(client, juan):
    h = juan[1]
    proyecto = proyecto_nuevo(client, h, porcentaje="3.00", desde=dia(-20))
    viejo = capturar(client, h, proyecto["id"], "100.00", fecha=dia(-15))
    reciente = capturar(client, h, proyecto["id"], "100.00", fecha=dia(-5))

    # El % cambió hace 10 días y se registra tarde: se recalcula lo capturado desde entonces
    r = client.post(f"/proyectos/{proyecto['id']}/porcentajes", headers=h,
                    json={"porcentaje": "5.00", "vigente_desde": dia(-10), "motivo": "aviso tardío del banco"})
    assert r.status_code == 201, r.text
    assert r.json()["movimientos_recalculados"] == 1

    assert client.get(f"/movimientos/{viejo['id']}", headers=h).json()["porcentaje_aplicado"] == "3.00"
    assert client.get(f"/movimientos/{reciente['id']}", headers=h).json()["monto_neto"] == "95.00"
    assert client.get(f"/proyectos/{proyecto['id']}", headers=h).json()["porcentaje_vigente"] == "5.00"

    # Captura tardía de un día anterior al cambio: usa el % de ese día, no el de hoy
    assert capturar(client, h, proyecto["id"], "100.00", fecha=dia(-12))["porcentaje_aplicado"] == "3.00"

    historial = client.get(f"/proyectos/{proyecto['id']}/porcentajes", headers=h).json()
    assert [x["porcentaje"] for x in historial] == ["3.00", "5.00"]
    assert historial[0]["fecha_fin_vigencia"] == dia(-10)

    # No se pueden reescribir periodos anteriores al abierto
    r = client.post(f"/proyectos/{proyecto['id']}/porcentajes", headers=h,
                    json={"porcentaje": "4.00", "vigente_desde": dia(-15)})
    assert r.status_code == 422


def test_movimiento_sin_porcentaje_vigente_o_fecha_futura(client, juan):
    h = juan[1]
    proyecto = proyecto_nuevo(client, h, desde=dia(-5))
    for fecha in (dia(-6), dia(1)):
        r = client.post("/movimientos", headers=h, json={"proyecto_id": proyecto["id"], "monto_bruto": "10",
                                                        "fecha_movimiento": fecha, "metodo_pago_id": metodo()})
        assert r.status_code == 422


def test_proyecto_o_cliente_inactivo_no_acepta_capturas(client, juan):
    h = juan[1]
    proyecto = proyecto_nuevo(client, h)
    datos = {"proyecto_id": proyecto["id"], "monto_bruto": "10", "fecha_movimiento": dia(0), "metodo_pago_id": metodo()}

    client.post(f"/proyectos/{proyecto['id']}/desactivar", headers=h)
    assert client.post("/movimientos", headers=h, json=datos).status_code == 422
    r = client.post("/salidas", headers=h, json={"proyecto_id": proyecto["id"], "monto": "5", "destino": "x",
                                                 "metodo_pago_id": metodo()})
    assert r.status_code == 422

    client.post(f"/proyectos/{proyecto['id']}/activar", headers=h)
    client.post(f"/terminales/{proyecto['terminal_id']}/desactivar", headers=h)
    assert client.post("/movimientos", headers=h, json=datos).status_code == 422


def test_saldos_por_proyecto_cliente_y_empresa_con_advertencia(client, juan):
    h = juan[1]
    empresa = crear_empresa(client, h)
    cliente = crear_cliente(client, h, empresa["id"])
    p1 = crear_proyecto(client, h, cliente["id"], "P1", porcentaje="0")
    p2 = crear_proyecto(client, h, cliente["id"], "P2", porcentaje="10")
    capturar(client, h, p1["id"], "1000.00", fecha=dia(-2))
    capturar(client, h, p2["id"], "500.00", fecha=dia(-2))

    r = registrar_salida(client, h, p1["id"], "300")
    assert r["saldo_proyecto"] == "700.00" and r["saldo_empresa"] == "1150.00" and r["advertencia"] is None

    # Control paralelo: no se bloquea, se advierte cuando el proyecto queda negativo
    r = registrar_salida(client, h, p1["id"], "900", "Nómina")
    assert r["saldo_proyecto"] == "-200.00" and "negativo" in r["advertencia"]

    saldo = client.get(f"/empresas/{empresa['id']}/saldo", headers=h).json()
    assert saldo == {**saldo, "ingresos_brutos": "1500.00", "comisiones": "50.00", "ingresos_netos": "1450.00",
                     "salidas": "1200.00", "saldo": "250.00"}
    assert client.get(f"/terminales/{cliente['id']}/saldo", headers=h).json()["saldo"] == "250.00"
    assert client.get(f"/proyectos/{p2['id']}/saldo", headers=h).json()["saldo"] == "450.00"


def test_editar_movimiento_recalcula_y_queda_en_bitacora(client, admin, juan):
    h = juan[1]
    proyecto = proyecto_nuevo(client, h, porcentaje="10")
    mov = capturar(client, h, proyecto["id"], "15000.00")

    r = client.patch(f"/movimientos/{mov['id']}", headers=h,
                     json={"monto_bruto": "1500.00", "metodo_pago_id": metodo("Efectivo"), "requiere_factura": True,
                           "motivo": "capturé un cero de más"})
    assert r.status_code == 200
    assert r.json()["monto_neto"] == "1350.00" and r.json()["requiere_factura"] is True
    assert client.get(f"/proyectos/{proyecto['id']}/saldo", headers=h).json()["saldo"] == "1350.00"

    fila = client.get("/reportes/bitacora", params={"accion": "EDITAR_MOVIMIENTO"}, headers=admin[1]).json()["filas"][0]
    assert fila["usuario"] == "juan@test.com"
    assert fila["detalle"]["antes"]["monto_bruto"] == "15000.00"
    assert fila["detalle"]["despues"]["monto_bruto"] == "1500.00"
    assert fila["detalle"]["motivo"] == "capturé un cero de más"


def test_mover_movimiento_entre_proyectos(client, juan):
    h = juan[1]
    empresa = crear_empresa(client, h, "A")
    cliente = crear_cliente(client, h, empresa["id"])
    p1 = crear_proyecto(client, h, cliente["id"], "P1", porcentaje="2")
    p2 = crear_proyecto(client, h, crear_cliente(client, h, empresa["id"], "T-002")["id"], "P2", porcentaje="9")
    ajeno = proyecto_nuevo(client, h, empresa="B")
    mov = capturar(client, h, p1["id"], "100")

    # Dentro de la misma empresa sí (aunque sea otro cliente), y se recalcula el %
    r = client.patch(f"/movimientos/{mov['id']}", json={"proyecto_id": p2["id"]}, headers=h)
    assert r.status_code == 200 and r.json()["porcentaje_aplicado"] == "9.00" and r.json()["monto_neto"] == "91.00"
    # A otra empresa no
    assert client.patch(f"/movimientos/{mov['id']}", json={"proyecto_id": ajeno["id"]}, headers=h).status_code == 422


def test_patch_no_puede_anular_campos_obligatorios(client, juan):
    h = juan[1]
    mov = capturar(client, h, proyecto_nuevo(client, h)["id"], "10")
    for campo in ("monto_bruto", "proyecto_id", "metodo_pago_id"):
        assert client.patch(f"/movimientos/{mov['id']}", json={campo: None}, headers=h).status_code == 422


def test_bitacora_es_inmutable_en_la_base_de_datos(client, admin, juan):
    h = juan[1]
    mov = capturar(client, h, proyecto_nuevo(client, h)["id"], "10")
    client.delete(f"/movimientos/{mov['id']}", headers=h)
    with engine.connect() as conn:
        try:
            conn.execute(text("DELETE FROM bitacora_auditoria"))
            raise AssertionError("la bitácora debió rechazar el DELETE")
        except Exception as exc:
            assert "no se puede modificar" in str(exc)


def test_nombres_unicos_de_cliente_y_proyecto(client, juan):
    h = juan[1]
    empresa = crear_empresa(client, h)
    c1 = crear_cliente(client, h, empresa["id"], ident="1234")
    r = client.post("/terminales", headers=h, json={"empresa_id": empresa["id"], "identificador_terminal": "1234"})
    assert r.status_code == 409
    crear_proyecto(client, h, c1["id"], "P1")
    r = client.post("/proyectos", headers=h, json={"terminal_id": c1["id"], "nombre": "P1", "porcentaje_inicial": "1"})
    assert r.status_code == 409
    # El mismo nombre de proyecto en otro cliente sí se permite
    crear_proyecto(client, h, crear_cliente(client, h, empresa["id"], ident="5678")["id"], "P1")


def test_metodos_de_pago(client, admin, juan):
    nombres = [m["nombre"] for m in client.get("/metodos-pago", headers=juan[1]).json()]
    assert nombres == ["Depósito", "Efectivo", "Transferencia"]

    # Solo el admin administra el catálogo
    assert client.post("/metodos-pago", json={"nombre": "Cheque"}, headers=juan[1]).status_code == 403
    r = client.post("/metodos-pago", json={"nombre": "Cheque"}, headers=admin[1])
    assert r.status_code == 201
    cheque = r.json()
    assert client.post("/metodos-pago", json={"nombre": "cheque"}, headers=admin[1]).status_code == 409

    proyecto = proyecto_nuevo(client, juan[1])
    assert capturar(client, juan[1], proyecto["id"], "10", metodo_pago_id=cheque["id"])["metodo_pago_id"] == cheque["id"]

    # Un método inactivo ya no se ofrece ni se puede usar
    client.patch(f"/metodos-pago/{cheque['id']}", json={"activo": False}, headers=admin[1])
    assert "Cheque" not in [m["nombre"] for m in client.get("/metodos-pago", headers=juan[1]).json()]
    todos = client.get("/metodos-pago", params={"incluir_inactivos": True}, headers=admin[1]).json()
    assert "Cheque" in [m["nombre"] for m in todos]
    r = client.post("/movimientos", headers=juan[1], json={"proyecto_id": proyecto["id"], "monto_bruto": "10",
                                                          "fecha_movimiento": dia(0), "metodo_pago_id": cheque["id"]})
    assert r.status_code == 422


def test_filtros_de_movimientos(client, juan):
    h = juan[1]
    proyecto = proyecto_nuevo(client, h)
    capturar(client, h, proyecto["id"], "10", requiere_factura=True)
    capturar(client, h, proyecto["id"], "20", metodo_pago_id=metodo("Efectivo"))
    assert client.get("/movimientos", params={"requiere_factura": True}, headers=h).json()["total"] == 1
    assert client.get("/movimientos", params={"metodo_pago_id": metodo("Efectivo")}, headers=h).json()["total"] == 1
    assert client.get("/movimientos", params={"proyecto_id": proyecto["id"]}, headers=h).json()["total"] == 2
    assert Decimal(client.get("/movimientos", headers=h).json()["items"][0]["monto_bruto"]) in (Decimal(10), Decimal(20))
