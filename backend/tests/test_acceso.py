"""El requisito original: la empresa que registró Juan no la puede usar Pedro."""

from tests.helpers import capturar, crear_empresa, crear_terminal


def test_la_empresa_guarda_quien_la_registro(client, juan):
    empresa = crear_empresa(client, juan[1])
    assert empresa["usuario_id"] == str(juan[0].id)


def test_pedro_no_ve_ni_usa_la_empresa_de_juan(client, juan, pedro):
    empresa = crear_empresa(client, juan[1])
    terminal = crear_terminal(client, juan[1], empresa["id"])
    mov = capturar(client, juan[1], terminal["id"], "1000.00")
    hp = pedro[1]

    assert client.get("/empresas", headers=hp).json()["total"] == 0
    assert client.get(f"/empresas/{empresa['id']}", headers=hp).status_code == 404
    assert client.get(f"/empresas/{empresa['id']}/saldo", headers=hp).status_code == 404
    assert client.patch(f"/empresas/{empresa['id']}", json={"nombre": "X"}, headers=hp).status_code == 404
    r = client.post("/terminales", headers=hp, json={"empresa_id": empresa["id"], "identificador_terminal": "Z",
                                                      "porcentaje_inicial": "1"})
    assert r.status_code == 404
    assert client.get(f"/terminales/{terminal['id']}", headers=hp).status_code == 404
    r = client.post("/movimientos", headers=hp, json={"terminal_id": terminal["id"], "monto_bruto": "5",
                                                       "fecha_movimiento": mov["fecha_movimiento"]})
    assert r.status_code == 404
    assert client.get(f"/movimientos/{mov['id']}", headers=hp).status_code == 404
    assert client.patch(f"/movimientos/{mov['id']}", json={"monto_bruto": "1"}, headers=hp).status_code == 404
    assert client.delete(f"/movimientos/{mov['id']}", headers=hp).status_code == 404
    assert client.get("/movimientos", headers=hp).json()["total"] == 0
    r = client.post("/salidas", json={"empresa_id": empresa["id"], "monto": "10", "destino": "x"}, headers=hp)
    assert r.status_code == 404
    r = client.get("/reportes/estado-cuenta", headers=hp,
                   params={"empresa_id": empresa["id"], "desde": "2026-01-01", "hasta": "2026-12-31"})
    assert r.status_code == 404
    assert client.get("/reportes/saldos", headers=hp).json()["filas"] == []


def test_contador_no_registra_empresas_a_nombre_de_otro(client, juan, pedro):
    r = client.post("/empresas", headers=juan[1], json={
        "nombre": "X", "csf": "C", "banco": "B", "numero_cuenta": "1", "usuario_id": str(pedro[0].id)})
    assert r.status_code == 403


def test_admin_ve_todo_y_puede_reasignar(client, admin, juan, pedro):
    empresa = crear_empresa(client, juan[1])
    terminal = crear_terminal(client, juan[1], empresa["id"])
    mov = capturar(client, juan[1], terminal["id"], "500.00")

    assert client.get("/empresas", headers=admin[1]).json()["total"] == 1
    r = client.post(f"/empresas/{empresa['id']}/reasignar", json={"usuario_id": str(pedro[0].id)}, headers=admin[1])
    assert r.status_code == 200

    # Pedro hereda la empresa con todo su historial (aunque lo capturó Juan); Juan la pierde
    assert client.get(f"/movimientos/{mov['id']}", headers=pedro[1]).status_code == 200
    assert client.get(f"/empresas/{empresa['id']}", headers=juan[1]).status_code == 404
    bit = client.get("/reportes/bitacora", params={"accion": "REASIGNAR_EMPRESA"}, headers=admin[1]).json()
    assert len(bit["filas"]) == 1
