from decimal import Decimal

from sqlalchemy import text

from app.db.session import engine
from tests.helpers import capturar, crear_empresa, crear_terminal, dia


def test_neto_calculado_por_la_base_de_datos(client, juan):
    empresa = crear_empresa(client, juan[1])
    terminal = crear_terminal(client, juan[1], empresa["id"], porcentaje="3.50")
    mov = capturar(client, juan[1], terminal["id"], "1000.00")
    assert Decimal(mov["porcentaje_aplicado"]) == Decimal("3.50")
    assert Decimal(mov["monto_neto"]) == Decimal("965.00")
    assert Decimal(mov["comision"]) == Decimal("35.00")


def test_porcentaje_segun_fecha_del_movimiento_y_recalculo_retroactivo(client, juan):
    h = juan[1]
    empresa = crear_empresa(client, h)
    terminal = crear_terminal(client, h, empresa["id"], porcentaje="3.00", desde=dia(-20))
    viejo = capturar(client, h, terminal["id"], "100.00", fecha=dia(-15))
    reciente = capturar(client, h, terminal["id"], "100.00", fecha=dia(-5))

    # El % cambió hace 10 días y se registra tarde: se recalcula lo capturado desde entonces
    r = client.post(f"/terminales/{terminal['id']}/porcentajes", headers=h,
                    json={"porcentaje": "5.00", "vigente_desde": dia(-10), "motivo": "aviso tardío del banco"})
    assert r.status_code == 201, r.text
    assert r.json()["movimientos_recalculados"] == 1

    assert client.get(f"/movimientos/{viejo['id']}", headers=h).json()["porcentaje_aplicado"] == "3.00"
    assert client.get(f"/movimientos/{reciente['id']}", headers=h).json()["monto_neto"] == "95.00"

    # Captura tardía de un día anterior al cambio: usa el % de ese día, no el de hoy
    tardio = capturar(client, h, terminal["id"], "100.00", fecha=dia(-12))
    assert tardio["porcentaje_aplicado"] == "3.00"

    historial = client.get(f"/terminales/{terminal['id']}/porcentajes", headers=h).json()
    assert [x["porcentaje"] for x in historial] == ["3.00", "5.00"]
    assert historial[0]["fecha_fin_vigencia"] == dia(-10)

    # No se pueden reescribir periodos anteriores al abierto
    r = client.post(f"/terminales/{terminal['id']}/porcentajes", headers=h,
                    json={"porcentaje": "4.00", "vigente_desde": dia(-15)})
    assert r.status_code == 422


def test_movimiento_sin_porcentaje_vigente_o_fecha_futura(client, juan):
    h = juan[1]
    empresa = crear_empresa(client, h)
    terminal = crear_terminal(client, h, empresa["id"], desde=dia(-5))
    for fecha in (dia(-6), dia(1)):
        r = client.post("/movimientos", headers=h,
                        json={"terminal_id": terminal["id"], "monto_bruto": "10", "fecha_movimiento": fecha})
        assert r.status_code == 422


def test_terminal_inactiva_no_acepta_capturas(client, juan):
    h = juan[1]
    empresa = crear_empresa(client, h)
    terminal = crear_terminal(client, h, empresa["id"])
    client.post(f"/terminales/{terminal['id']}/desactivar", headers=h)
    r = client.post("/movimientos", headers=h,
                    json={"terminal_id": terminal["id"], "monto_bruto": "10", "fecha_movimiento": dia(0)})
    assert r.status_code == 422


def test_saldo_salidas_y_advertencia_de_negativo(client, juan):
    h = juan[1]
    empresa = crear_empresa(client, h)
    terminal = crear_terminal(client, h, empresa["id"], porcentaje="0")
    capturar(client, h, terminal["id"], "1000.00", fecha=dia(-2))

    r = client.post("/salidas", headers=h, json={"empresa_id": empresa["id"], "monto": "300", "destino": "Proveedor"})
    assert r.status_code == 201
    assert r.json()["saldo_empresa"] == "700.00" and r.json()["advertencia"] is None

    # Control paralelo: no se bloquea, se advierte
    r = client.post("/salidas", headers=h, json={"empresa_id": empresa["id"], "monto": "900", "destino": "Nómina"})
    assert r.status_code == 201
    assert r.json()["saldo_empresa"] == "-200.00" and "negativo" in r.json()["advertencia"]

    saldo = client.get(f"/empresas/{empresa['id']}/saldo", headers=h).json()
    assert saldo == {**saldo, "ingresos_netos": "1000.00", "salidas": "1200.00", "saldo": "-200.00"}


def test_editar_movimiento_recalcula_y_queda_en_bitacora(client, admin, juan):
    h = juan[1]
    empresa = crear_empresa(client, h)
    terminal = crear_terminal(client, h, empresa["id"], porcentaje="10")
    mov = capturar(client, h, terminal["id"], "15000.00")

    r = client.patch(f"/movimientos/{mov['id']}", headers=h,
                     json={"monto_bruto": "1500.00", "motivo": "capturé un cero de más"})
    assert r.status_code == 200
    assert r.json()["monto_neto"] == "1350.00"
    assert client.get(f"/empresas/{empresa['id']}/saldo", headers=h).json()["saldo"] == "1350.00"

    fila = client.get("/reportes/bitacora", params={"accion": "EDITAR_MOVIMIENTO"}, headers=admin[1]).json()["filas"][0]
    assert fila["usuario"] == "juan@test.com"
    assert fila["detalle"]["antes"]["monto_bruto"] == "15000.00"
    assert fila["detalle"]["despues"]["monto_bruto"] == "1500.00"
    assert fila["detalle"]["motivo"] == "capturé un cero de más"


def test_mover_a_terminal_de_otra_empresa_no_se_permite(client, juan):
    h = juan[1]
    t1 = crear_terminal(client, h, crear_empresa(client, h, "A")["id"])
    t2 = crear_terminal(client, h, crear_empresa(client, h, "B")["id"])
    mov = capturar(client, h, t1["id"], "10")
    r = client.patch(f"/movimientos/{mov['id']}", json={"terminal_id": t2["id"]}, headers=h)
    assert r.status_code == 422


def test_patch_no_puede_anular_campos_obligatorios(client, juan):
    h = juan[1]
    t = crear_terminal(client, h, crear_empresa(client, h)["id"])
    mov = capturar(client, h, t["id"], "10")
    assert client.patch(f"/movimientos/{mov['id']}", json={"monto_bruto": None}, headers=h).status_code == 422


def test_bitacora_es_inmutable_en_la_base_de_datos(client, admin, juan):
    h = juan[1]
    t = crear_terminal(client, h, crear_empresa(client, h)["id"])
    mov = capturar(client, h, t["id"], "10")
    client.delete(f"/movimientos/{mov['id']}", headers=h)
    with engine.connect() as conn:
        try:
            conn.execute(text("DELETE FROM bitacora_auditoria"))
            raise AssertionError("la bitácora debió rechazar el DELETE")
        except Exception as exc:
            assert "no se puede modificar" in str(exc)


def test_identificador_de_terminal_unico_por_empresa(client, juan):
    h = juan[1]
    empresa = crear_empresa(client, h)
    crear_terminal(client, h, empresa["id"], ident="T1")
    r = client.post("/terminales", headers=h, json={"empresa_id": empresa["id"], "identificador_terminal": "T1",
                                                     "porcentaje_inicial": "1"})
    assert r.status_code == 409
