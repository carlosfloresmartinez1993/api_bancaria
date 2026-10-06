"""El requisito original: la empresa que registró Juan no la puede usar Pedro (ni sus clientes ni proyectos)."""

from tests.helpers import capturar, crear_empresa, metodo, proyecto_nuevo, registrar_salida


def test_la_empresa_guarda_quien_la_registro(client, juan):
    empresa = crear_empresa(client, juan[1])
    assert empresa["usuario_id"] == str(juan[0].id)


def test_pedro_no_ve_ni_usa_la_empresa_de_juan(client, juan, pedro):
    proyecto = proyecto_nuevo(client, juan[1])
    empresa_id, cliente_id = proyecto["empresa_id"], proyecto["terminal_id"]
    mov = capturar(client, juan[1], proyecto["id"], "1000.00")
    salida = registrar_salida(client, juan[1], proyecto["id"], "10")["salida"]
    hp = pedro[1]

    assert client.get("/empresas", headers=hp).json()["total"] == 0
    assert client.get(f"/empresas/{empresa_id}", headers=hp).status_code == 404
    assert client.get(f"/empresas/{empresa_id}/saldo", headers=hp).status_code == 404
    assert client.patch(f"/empresas/{empresa_id}", json={"nombre": "X"}, headers=hp).status_code == 404
    r = client.post("/terminales", headers=hp, json={"empresa_id": empresa_id, "identificador_terminal": "Z"})
    assert r.status_code == 404
    assert client.get(f"/terminales/{cliente_id}", headers=hp).status_code == 404
    r = client.post("/proyectos", headers=hp, json={"terminal_id": cliente_id, "nombre": "X", "porcentaje_inicial": "1"})
    assert r.status_code == 404
    assert client.get(f"/proyectos/{proyecto['id']}", headers=hp).status_code == 404
    assert client.get("/proyectos", headers=hp).json()["total"] == 0
    r = client.post("/movimientos", headers=hp, json={"proyecto_id": proyecto["id"], "monto_bruto": "5",
                                                       "fecha_movimiento": mov["fecha_movimiento"],
                                                       "metodo_pago_id": metodo()})
    assert r.status_code == 404
    assert client.get(f"/movimientos/{mov['id']}", headers=hp).status_code == 404
    assert client.patch(f"/movimientos/{mov['id']}", json={"monto_bruto": "1"}, headers=hp).status_code == 404
    assert client.delete(f"/movimientos/{mov['id']}", headers=hp).status_code == 404
    assert client.get("/movimientos", headers=hp).json()["total"] == 0
    r = client.post("/salidas", headers=hp, json={"proyecto_id": proyecto["id"], "monto": "10", "destino": "x",
                                                  "metodo_pago_id": metodo()})
    assert r.status_code == 404
    assert client.get(f"/salidas/{salida['id']}", headers=hp).status_code == 404
    assert client.get("/salidas", headers=hp).json()["total"] == 0
    r = client.get("/reportes/estado-cuenta", headers=hp,
                   params={"empresa_id": empresa_id, "desde": "2026-01-01", "hasta": "2026-12-31"})
    assert r.status_code == 404
    assert client.get("/reportes/constructor", params={"proyecto_id": proyecto["id"]}, headers=hp).status_code == 404
    assert client.get("/reportes/constructor", headers=hp).json()["filas"] == []
    assert client.get("/reportes/saldos", headers=hp).json()["filas"] == []


def test_contador_no_registra_empresas_a_nombre_de_otro(client, juan, pedro):
    r = client.post("/empresas", headers=juan[1], json={"nombre": "X", "usuario_id": str(pedro[0].id)})
    assert r.status_code == 403


def test_admin_ve_todo_y_puede_reasignar(client, admin, juan, pedro):
    proyecto = proyecto_nuevo(client, juan[1])
    mov = capturar(client, juan[1], proyecto["id"], "500.00")

    assert client.get("/empresas", headers=admin[1]).json()["total"] == 1
    r = client.post(f"/empresas/{proyecto['empresa_id']}/reasignar", json={"usuario_id": str(pedro[0].id)},
                    headers=admin[1])
    assert r.status_code == 200

    # Pedro hereda la empresa con todo su historial (aunque lo capturó Juan); Juan la pierde
    assert client.get(f"/movimientos/{mov['id']}", headers=pedro[1]).status_code == 200
    assert client.get(f"/proyectos/{proyecto['id']}", headers=pedro[1]).status_code == 200
    assert client.get(f"/empresas/{proyecto['empresa_id']}", headers=juan[1]).status_code == 404
    bit = client.get("/reportes/bitacora", params={"accion": "REASIGNAR_EMPRESA"}, headers=admin[1]).json()
    assert len(bit["filas"]) == 1
