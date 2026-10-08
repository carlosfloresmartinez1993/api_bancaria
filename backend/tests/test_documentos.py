"""Factura (PDF) de una entrada: la BD guarda solo la clave; el archivo va al almacenamiento."""
import boto3
import pytest
from moto import mock_aws

from app.core.config import settings
from app.services.almacenamiento import almacenamiento
from tests.helpers import capturar, proyecto_nuevo

PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"


@pytest.fixture(autouse=True)
def carpeta_temporal(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "ALMACENAMIENTO", "local")
    monkeypatch.setattr(settings, "ARCHIVOS_DIR", tmp_path)
    almacenamiento.cache_clear()
    yield tmp_path
    almacenamiento.cache_clear()


def subir(client, h, mov_id, contenido=PDF, nombre="Factura A-15.pdf"):
    return client.put(f"/movimientos/{mov_id}/documento", headers=h,
                      files={"archivo": (nombre, contenido, "application/pdf")})


def archivos(carpeta):
    return sorted(p.relative_to(carpeta).as_posix() for p in carpeta.rglob("*.pdf"))


def acciones(client, admin):
    return [f["accion"] for f in client.get("/reportes/bitacora", headers=admin[1]).json()["filas"]]


def test_subir_ver_reemplazar_y_quitar_la_factura(client, admin, juan, carpeta_temporal):
    h = juan[1]
    mov = capturar(client, h, proyecto_nuevo(client, h)["id"], "1000")
    assert mov["documento_nombre"] is None

    r = subir(client, h, mov["id"])
    assert r.status_code == 200, r.text
    assert r.json()["documento_nombre"] == "Factura A-15.pdf"
    assert r.json()["documento_tamano_bytes"] == len(PDF)
    assert "documento_clave" not in r.json()  # la ruta interna no se expone
    primero = archivos(carpeta_temporal)
    assert len(primero) == 1 and primero[0].startswith(f"entradas/{mov['id']}/")

    r = client.get(f"/movimientos/{mov['id']}/documento", headers=h)
    assert r.status_code == 200 and r.content == PDF
    assert r.headers["content-type"] == "application/pdf"
    assert "Factura A-15.pdf" in r.headers["content-disposition"]

    # Reemplazar: queda solo el archivo nuevo
    r = subir(client, h, mov["id"], PDF + b"v2", "Factura corregida.pdf")
    assert r.json()["documento_nombre"] == "Factura corregida.pdf"
    segundo = archivos(carpeta_temporal)
    assert len(segundo) == 1 and segundo != primero
    assert client.get(f"/movimientos/{mov['id']}/documento", headers=h).content == PDF + b"v2"

    r = client.delete(f"/movimientos/{mov['id']}/documento", headers=h, params={"motivo": "No era de esta entrada"})
    assert r.status_code == 200 and r.json()["documento_nombre"] is None
    assert archivos(carpeta_temporal) == []
    assert client.get(f"/movimientos/{mov['id']}/documento", headers=h).status_code == 404
    assert acciones(client, admin).count("SUBIR_DOCUMENTO") == 2
    assert "ELIMINAR_DOCUMENTO" in acciones(client, admin)


def test_solo_acepta_pdf_y_respeta_el_tamano(client, juan, monkeypatch, carpeta_temporal):
    h = juan[1]
    mov = capturar(client, h, proyecto_nuevo(client, h)["id"], "1000")
    r = subir(client, h, mov["id"], b"MZ\x90\x00 no soy un pdf", "virus.pdf")
    assert r.status_code == 422 and "PDF" in r.json()["detail"]

    monkeypatch.setattr(settings, "MAX_DOCUMENTO_MB", 1)
    r = subir(client, h, mov["id"], PDF + b"0" * (1024 * 1024))
    assert r.status_code == 422 and "1 MB" in r.json()["detail"]
    assert archivos(carpeta_temporal) == []


def test_nombre_sin_ruta_y_con_extension(client, juan):
    h = juan[1]
    mov = capturar(client, h, proyecto_nuevo(client, h)["id"], "1000")
    r = subir(client, h, mov["id"], nombre=r"C:\Users\juan\Escritorio\factura")
    assert r.json()["documento_nombre"] == "factura.pdf"


def test_otro_contador_no_ve_ni_toca_la_factura(client, juan, pedro):
    mov = capturar(client, juan[1], proyecto_nuevo(client, juan[1])["id"], "1000")
    subir(client, juan[1], mov["id"])
    assert client.get(f"/movimientos/{mov['id']}/documento", headers=pedro[1]).status_code == 404
    assert subir(client, pedro[1], mov["id"]).status_code == 404
    assert client.delete(f"/movimientos/{mov['id']}/documento", headers=pedro[1]).status_code == 404


def test_eliminar_la_entrada_borra_su_factura(client, juan, carpeta_temporal):
    h = juan[1]
    mov = capturar(client, h, proyecto_nuevo(client, h)["id"], "1000")
    subir(client, h, mov["id"])
    assert client.delete(f"/movimientos/{mov['id']}", headers=h).status_code == 204
    assert archivos(carpeta_temporal) == []


def test_en_s3_guarda_lee_y_borra_del_bucket(client, juan, monkeypatch):
    with mock_aws():
        boto3.client("s3", region_name="us-east-1").create_bucket(Bucket="facturas")
        for nombre, valor in {"ALMACENAMIENTO": "s3", "S3_BUCKET": "facturas", "S3_ENDPOINT_URL": None,
                              "S3_REGION": "us-east-1", "S3_ACCESS_KEY_ID": "x", "S3_SECRET_ACCESS_KEY": "x",
                              "S3_PREFIJO": "pruebas/"}.items():
            monkeypatch.setattr(settings, nombre, valor)
        almacenamiento.cache_clear()
        s3 = boto3.client("s3", region_name="us-east-1")
        claves = lambda: [o["Key"] for o in s3.list_objects_v2(Bucket="facturas").get("Contents", [])]  # noqa: E731

        h = juan[1]
        mov = capturar(client, h, proyecto_nuevo(client, h)["id"], "1000")
        assert subir(client, h, mov["id"]).status_code == 200
        assert len(claves()) == 1 and claves()[0].startswith(f"pruebas/entradas/{mov['id']}/")
        assert client.get(f"/movimientos/{mov['id']}/documento", headers=h).content == PDF
        client.delete(f"/movimientos/{mov['id']}/documento", headers=h)
        assert claves() == []
