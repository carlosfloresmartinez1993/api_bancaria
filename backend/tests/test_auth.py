from tests.conftest import PASSWORD


def test_login_correcto_y_me(client, juan):
    r = client.post("/auth/login", data={"username": "JUAN@test.com", "password": PASSWORD})
    assert r.status_code == 200
    token = r.json()["access_token"]
    r = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.json()["correo"] == "juan@test.com"


def test_login_incorrecto_no_revela_si_existe_el_correo(client, juan):
    r1 = client.post("/auth/login", data={"username": "juan@test.com", "password": "mala123456"})
    r2 = client.post("/auth/login", data={"username": "nadie@test.com", "password": "mala123456"})
    assert r1.status_code == r2.status_code == 401
    assert r1.json() == r2.json()


def test_token_invalido(client):
    r = client.get("/auth/me", headers={"Authorization": "Bearer basura"})
    assert r.status_code == 401


def test_usuario_desactivado_pierde_acceso_inmediato(client, admin, juan):
    usuario, h = juan
    assert client.get("/auth/me", headers=h).status_code == 200
    r = client.post(f"/usuarios/{usuario.id}/desactivar", headers=admin[1])
    assert r.status_code == 200
    assert client.get("/auth/me", headers=h).status_code == 401


def test_contador_no_accede_a_endpoints_de_admin(client, juan):
    assert client.get("/usuarios", headers=juan[1]).status_code == 403
    assert client.get("/reportes/bitacora", headers=juan[1]).status_code == 403


def test_politica_de_password(client, admin):
    datos = {"nombre": "X", "apellidos": "Y", "correo": "x@test.com", "password": "corta", "rol": "contador"}
    assert client.post("/usuarios", json=datos, headers=admin[1]).status_code == 422
    datos["password"] = "SoloLetrasLargas"
    assert client.post("/usuarios", json=datos, headers=admin[1]).status_code == 422
    datos["password"] = "LetrasY12345"
    r = client.post("/usuarios", json=datos, headers=admin[1])
    assert r.status_code == 201
    assert "password" not in r.json() and "password_hash" not in r.json()


def test_no_se_puede_dejar_sin_admins(client, admin):
    usuario, h = admin
    r = client.patch(f"/usuarios/{usuario.id}", json={"rol": "contador"}, headers=h)
    assert r.status_code == 422


def test_cambiar_password(client, juan):
    r = client.post("/auth/cambiar-password", json={"actual": PASSWORD, "nueva": "NuevaClave123"}, headers=juan[1])
    assert r.status_code == 204
    r = client.post("/auth/login", data={"username": "juan@test.com", "password": "NuevaClave123"})
    assert r.status_code == 200
