"""Clientes (terminales) sin empresa: acceso, operación, reportes y cambio de empresa con reversión."""

from tests.helpers import capturar, crear_cliente, crear_empresa, crear_proyecto, dia, registrar_salida


def _cliente_libre(client, h, ident="LIBRE-1", porcentaje="10"):
    cliente = crear_cliente(client, h, None, ident)
    proyecto = crear_proyecto(client, h, cliente["id"], "P1", porcentaje=porcentaje)
    return cliente, proyecto


def test_cliente_sin_empresa_opera_igual(client, juan):
    h = juan[1]
    cliente, proyecto = _cliente_libre(client, h)
    assert cliente["empresa_id"] is None and cliente["usuario_id"] == str(juan[0].id)
    assert proyecto["empresa_id"] is None

    mov = capturar(client, h, proyecto["id"], "1000", fecha=dia(-1), requiere_factura=True)
    assert mov["monto_neto"] == "900.00" and mov["empresa_id"] is None
    r = registrar_salida(client, h, proyecto["id"], "300")
    assert r["saldo_proyecto"] == "600.00" and r["saldo_empresa"] is None
    assert client.get(f"/terminales/{cliente['id']}/saldo", headers=h).json()["saldo"] == "600.00"

    # Filtros de listados
    assert client.get("/terminales", params={"sin_empresa": True}, headers=h).json()["total"] == 1
    assert client.get("/movimientos", params={"sin_empresa": True}, headers=h).json()["total"] == 1
    assert client.get("/salidas", params={"sin_empresa": True}, headers=h).json()["total"] == 1
    assert client.get("/proyectos", params={"sin_empresa": True}, headers=h).json()["total"] == 1


def test_identificador_unico_entre_clientes_sin_empresa_del_mismo_responsable(client, juan, pedro):
    crear_cliente(client, juan[1], None, "1234")
    r = client.post("/terminales", json={"identificador_terminal": "1234"}, headers=juan[1])
    assert r.status_code == 409
    # Otro contador sí puede tener su propio "1234" sin empresa, y una empresa también
    crear_cliente(client, pedro[1], None, "1234")
    crear_cliente(client, juan[1], crear_empresa(client, juan[1])["id"], "1234")


def test_acceso_a_clientes_sin_empresa(client, admin, juan, pedro):
    cliente, proyecto = _cliente_libre(client, juan[1])
    mov = capturar(client, juan[1], proyecto["id"], "100")
    hp = pedro[1]
    assert client.get(f"/terminales/{cliente['id']}", headers=hp).status_code == 404
    assert client.get(f"/proyectos/{proyecto['id']}", headers=hp).status_code == 404
    assert client.get(f"/movimientos/{mov['id']}", headers=hp).status_code == 404
    assert client.get("/terminales", headers=hp).json()["total"] == 0
    assert client.get("/reportes/saldos", headers=hp).json()["filas"] == []
    # El admin lo ve
    assert client.get(f"/terminales/{cliente['id']}", headers=admin[1]).status_code == 200
    # Un contador no registra clientes a nombre de otro; un admin sí
    r = client.post("/terminales", json={"identificador_terminal": "X", "usuario_id": str(pedro[0].id)}, headers=juan[1])
    assert r.status_code == 403
    r = client.post("/terminales", json={"identificador_terminal": "X", "usuario_id": str(pedro[0].id)}, headers=admin[1])
    assert r.status_code == 201 and r.json()["usuario_id"] == str(pedro[0].id)
    assert client.get(f"/terminales/{r.json()['id']}", headers=hp).status_code == 200


def test_reportes_muestran_sin_empresa(client, juan):
    h = juan[1]
    empresa = crear_empresa(client, h, "Apple")
    p_empresa = crear_proyecto(client, h, crear_cliente(client, h, empresa["id"], "1234")["id"], "P1", porcentaje="0")
    _, p_libre = _cliente_libre(client, h, porcentaje="0")
    capturar(client, h, p_empresa["id"], "100", fecha=dia(-1))
    capturar(client, h, p_libre["id"], "50", fecha=dia(-1))

    saldos = client.get("/reportes/saldos", headers=h).json()
    assert {f["empresa"]: f["saldo"] for f in saldos["filas"]} == {"Apple": "100.00", "Sin empresa": "50.00"}
    assert saldos["totales"]["saldo"] == "150.00"

    r = client.get("/reportes/constructor", params={"agrupar": "empresa"}, headers=h).json()
    assert {f["empresa"] for f in r["filas"]} == {"Apple", "Sin empresa"}
    r = client.get("/reportes/constructor", params={"sin_empresa": True, "agrupar": "cliente"}, headers=h).json()
    assert [(f["empresa"], f["cliente"]) for f in r["filas"]] == [("Sin empresa", "LIBRE-1")]
    r = client.get("/reportes/estado-cuenta", params={"sin_empresa": True, "desde": dia(-5), "hasta": dia(0)}, headers=h)
    assert r.status_code == 200 and r.json()["parametros"]["saldo_final"] == "50.00"
    assert r.json()["titulo"] == "Estado de cuenta — Sin empresa"


def test_mover_a_empresa_y_revertir(client, juan):
    h = juan[1]
    empresa = crear_empresa(client, h, "Apple")
    cliente, proyecto = _cliente_libre(client, h, porcentaje="0")
    capturar(client, h, proyecto["id"], "500", fecha=dia(-1))

    r = client.post(f"/terminales/{cliente['id']}/empresa", json={"empresa_id": empresa["id"], "motivo": "Era de Apple"},
                    headers=h)
    assert r.status_code == 200 and r.json()["empresa_id"] == empresa["id"]
    # El saldo se mueve con el cliente
    assert client.get(f"/empresas/{empresa['id']}/saldo", headers=h).json()["saldo"] == "500.00"
    nombres = {f["empresa"] for f in client.get("/reportes/saldos", headers=h).json()["filas"]}
    assert nombres == {"Apple"}

    historial = client.get(f"/terminales/{cliente['id']}/historial-empresa", headers=h).json()
    assert len(historial) == 1
    assert historial[0] == {**historial[0], "empresa_antes": "Sin empresa", "empresa_despues": "Apple",
                            "saldo_movido": "500.00", "motivo": "Era de Apple", "se_puede_revertir": True}

    # Revertir: vuelve exactamente a como estaba
    r = client.post(f"/terminales/{cliente['id']}/revertir-movimiento", json={}, headers=h)
    assert r.status_code == 200 and r.json()["empresa_id"] is None
    assert client.get(f"/empresas/{empresa['id']}/saldo", headers=h).json()["saldo"] == "0.00"
    historial = client.get(f"/terminales/{cliente['id']}/historial-empresa", headers=h).json()
    assert [x["es_reversion"] for x in historial] == [True, False]
    assert [x["se_puede_revertir"] for x in historial] == [True, False]


def test_quitar_empresa_y_conflicto_de_identificador(client, juan):
    h = juan[1]
    empresa = crear_empresa(client, h)
    con_empresa = crear_cliente(client, h, empresa["id"], "1234")
    crear_cliente(client, h, None, "1234")
    # Ya hay un "1234" sin empresa del mismo responsable
    r = client.post(f"/terminales/{con_empresa['id']}/empresa", json={"empresa_id": None}, headers=h)
    assert r.status_code == 409
    otro = crear_cliente(client, h, empresa["id"], "5678")
    r = client.post(f"/terminales/{otro['id']}/empresa", json={"empresa_id": None}, headers=h)
    assert r.status_code == 200 and r.json()["empresa_id"] is None and r.json()["usuario_id"] == str(juan[0].id)
    # Moverlo a donde ya está no se permite
    assert client.post(f"/terminales/{otro['id']}/empresa", json={"empresa_id": None}, headers=h).status_code == 422


def test_contador_no_mueve_a_empresas_ajenas_y_admin_si(client, admin, juan, pedro):
    cliente, _ = _cliente_libre(client, juan[1])
    empresa_pedro = crear_empresa(client, pedro[1], "De Pedro")
    r = client.post(f"/terminales/{cliente['id']}/empresa", json={"empresa_id": empresa_pedro["id"]}, headers=juan[1])
    assert r.status_code == 404

    # El admin sí; el cliente pasa al responsable de la empresa destino
    r = client.post(f"/terminales/{cliente['id']}/empresa", json={"empresa_id": empresa_pedro["id"]}, headers=admin[1])
    assert r.status_code == 200 and r.json()["usuario_id"] == str(pedro[0].id)
    assert client.get(f"/terminales/{cliente['id']}", headers=juan[1]).status_code == 404
    # Pedro no puede revertirlo (volvería a ser de Juan); el admin sí
    assert client.post(f"/terminales/{cliente['id']}/revertir-movimiento", json={}, headers=pedro[1]).status_code == 403
    r = client.post(f"/terminales/{cliente['id']}/revertir-movimiento", json={}, headers=admin[1])
    assert r.status_code == 200 and r.json()["usuario_id"] == str(juan[0].id) and r.json()["empresa_id"] is None


def test_reasignar_empresa_arrastra_a_sus_clientes(client, admin, juan, pedro):
    empresa = crear_empresa(client, juan[1])
    cliente = crear_cliente(client, juan[1], empresa["id"], "1234")
    client.post(f"/empresas/{empresa['id']}/reasignar", json={"usuario_id": str(pedro[0].id)}, headers=admin[1])
    assert client.get(f"/terminales/{cliente['id']}", headers=pedro[1]).json()["usuario_id"] == str(pedro[0].id)
    assert client.get(f"/terminales/{cliente['id']}", headers=juan[1]).status_code == 404


def test_reasignar_cliente_sin_empresa(client, admin, juan, pedro):
    cliente, _ = _cliente_libre(client, juan[1])
    assert client.post(f"/terminales/{cliente['id']}/reasignar", json={"usuario_id": str(pedro[0].id)},
                       headers=juan[1]).status_code == 403
    r = client.post(f"/terminales/{cliente['id']}/reasignar", json={"usuario_id": str(pedro[0].id)}, headers=admin[1])
    assert r.status_code == 200 and r.json()["usuario_id"] == str(pedro[0].id)
    con_empresa = crear_cliente(client, pedro[1], crear_empresa(client, pedro[1])["id"], "9")
    r = client.post(f"/terminales/{con_empresa['id']}/reasignar", json={"usuario_id": str(juan[0].id)}, headers=admin[1])
    assert r.status_code == 422
    acciones = [f["accion"] for f in client.get("/reportes/bitacora", headers=admin[1]).json()["filas"]]
    assert "REASIGNAR_CLIENTE" in acciones


def test_mover_registros_solo_dentro_del_mismo_cliente_si_no_tiene_empresa(client, juan):
    h = juan[1]
    cliente, p1 = _cliente_libre(client, h)
    p2 = crear_proyecto(client, h, cliente["id"], "P2", porcentaje="5")
    _, otro = _cliente_libre(client, h, ident="LIBRE-2")
    mov = capturar(client, h, p1["id"], "100")
    assert client.patch(f"/movimientos/{mov['id']}", json={"proyecto_id": p2["id"]}, headers=h).status_code == 200
    assert client.patch(f"/movimientos/{mov['id']}", json={"proyecto_id": otro["id"]}, headers=h).status_code == 422
