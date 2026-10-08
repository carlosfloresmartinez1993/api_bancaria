"""factura (PDF) de las entradas

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-08

Cada entrada puede tener una factura en PDF. La BD guarda solo la clave (ruta) del archivo,
su nombre, tamaño y fecha; el archivo vive en el almacenamiento configurado (carpeta local o
bucket S3). Los datos existentes se conservan.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '0004'
down_revision: Union[str, None] = '0003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ACCIONES_ANTES = [
    'CREAR_USUARIO', 'EDITAR_USUARIO', 'CAMBIO_PASSWORD', 'ACTIVAR', 'DESACTIVAR', 'REASIGNAR_EMPRESA',
    'CAMBIO_PORCENTAJE', 'EDITAR_MOVIMIENTO', 'ELIMINAR_MOVIMIENTO', 'EDITAR_SALIDA', 'ELIMINAR_SALIDA',
    'CIERRE_ENVIADO', 'CIERRE_ERROR', 'MOVER_CLIENTE', 'REASIGNAR_CLIENTE',
]
ACCIONES_DESPUES = ACCIONES_ANTES + ['SUBIR_DOCUMENTO', 'ELIMINAR_DOCUMENTO']


def _check_acciones(acciones: list[str], valido: bool = True) -> None:
    op.drop_constraint(op.f('ck_bitacora_auditoria_accion_bitacora'), 'bitacora_auditoria', type_='check')
    lista = ", ".join(f"'{a}'" for a in acciones)
    # NOT VALID al revertir: la bitácora no se puede modificar, así que puede conservar acciones nuevas.
    op.execute(f"ALTER TABLE bitacora_auditoria ADD CONSTRAINT ck_bitacora_auditoria_accion_bitacora "
               f"CHECK (accion IN ({lista})){'' if valido else ' NOT VALID'}")


def upgrade() -> None:
    op.add_column('movimientos', sa.Column('documento_clave', sa.String(length=500), nullable=True))
    op.add_column('movimientos', sa.Column('documento_nombre', sa.String(length=255), nullable=True))
    op.add_column('movimientos', sa.Column('documento_tamano_bytes', sa.Integer(), nullable=True))
    op.add_column('movimientos', sa.Column('documento_subido_en', sa.DateTime(timezone=True), nullable=True))
    op.create_check_constraint(
        op.f('ck_movimientos_documento_completo'), 'movimientos',
        "documento_clave IS NULL OR (documento_nombre IS NOT NULL AND documento_tamano_bytes > 0 "
        "AND documento_subido_en IS NOT NULL)",
    )
    _check_acciones(ACCIONES_DESPUES)


def downgrade() -> None:
    # Ojo: al revertir se pierde qué archivo pertenece a cada entrada (los archivos no se borran).
    _check_acciones(ACCIONES_ANTES, valido=False)
    op.drop_constraint(op.f('ck_movimientos_documento_completo'), 'movimientos', type_='check')
    op.drop_column('movimientos', 'documento_subido_en')
    op.drop_column('movimientos', 'documento_tamano_bytes')
    op.drop_column('movimientos', 'documento_nombre')
    op.drop_column('movimientos', 'documento_clave')
