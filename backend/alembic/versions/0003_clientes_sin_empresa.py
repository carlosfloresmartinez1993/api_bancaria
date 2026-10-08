"""clientes sin empresa

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-07

Un cliente (terminal) puede no tener empresa. Cada cliente guarda su responsable
(usuario_id): si tiene empresa, una llave compuesta obliga a que sea el responsable de
la empresa y lo actualiza en cascada al reasignarla. Los datos existentes se conservan.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '0003'
down_revision: Union[str, None] = '0002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ACCIONES_ANTES = [
    'CREAR_USUARIO', 'EDITAR_USUARIO', 'CAMBIO_PASSWORD', 'ACTIVAR', 'DESACTIVAR', 'REASIGNAR_EMPRESA',
    'CAMBIO_PORCENTAJE', 'EDITAR_MOVIMIENTO', 'ELIMINAR_MOVIMIENTO', 'EDITAR_SALIDA', 'ELIMINAR_SALIDA',
    'CIERRE_ENVIADO', 'CIERRE_ERROR',
]
ACCIONES_DESPUES = ACCIONES_ANTES + ['MOVER_CLIENTE', 'REASIGNAR_CLIENTE']


def _check_acciones(acciones: list[str], valido: bool = True) -> None:
    op.drop_constraint(op.f('ck_bitacora_auditoria_accion_bitacora'), 'bitacora_auditoria', type_='check')
    lista = ", ".join(f"'{a}'" for a in acciones)
    # NOT VALID al revertir: la bitácora no se puede modificar, así que puede conservar acciones nuevas.
    op.execute(f"ALTER TABLE bitacora_auditoria ADD CONSTRAINT ck_bitacora_auditoria_accion_bitacora "
               f"CHECK (accion IN ({lista})){'' if valido else ' NOT VALID'}")


def upgrade() -> None:
    op.create_unique_constraint('uq_empresas_id_usuario', 'empresas', ['id', 'usuario_id'])

    # Responsable del cliente: se toma de su empresa para los clientes existentes.
    op.add_column('terminales_bancarias', sa.Column('usuario_id', sa.Uuid(), nullable=True))
    op.execute("UPDATE terminales_bancarias t SET usuario_id = e.usuario_id FROM empresas e WHERE e.id = t.empresa_id")
    op.alter_column('terminales_bancarias', 'usuario_id', existing_type=sa.Uuid(), nullable=False)
    op.alter_column('terminales_bancarias', 'empresa_id', existing_type=sa.UUID(), nullable=True)

    op.create_index(op.f('ix_terminales_bancarias_usuario_id'), 'terminales_bancarias', ['usuario_id'], unique=False)
    op.create_index('uq_terminal_sin_empresa_por_responsable', 'terminales_bancarias',
                    ['usuario_id', 'identificador_terminal'], unique=True,
                    postgresql_where=sa.text('empresa_id IS NULL'))
    op.create_foreign_key('fk_terminal_responsable_de_la_empresa', 'terminales_bancarias', 'empresas',
                          ['empresa_id', 'usuario_id'], ['id', 'usuario_id'], onupdate='CASCADE', ondelete='RESTRICT')
    op.create_foreign_key(op.f('fk_terminales_bancarias_usuario_id_usuarios'), 'terminales_bancarias', 'usuarios',
                          ['usuario_id'], ['id'], ondelete='RESTRICT')

    _check_acciones(ACCIONES_DESPUES)


def downgrade() -> None:
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM terminales_bancarias WHERE empresa_id IS NULL) THEN
                RAISE EXCEPTION 'Hay clientes sin empresa: asígnales una empresa antes de revertir esta migración';
            END IF;
        END $$;
    """)
    _check_acciones(ACCIONES_ANTES, valido=False)
    op.drop_constraint(op.f('fk_terminales_bancarias_usuario_id_usuarios'), 'terminales_bancarias', type_='foreignkey')
    op.drop_constraint('fk_terminal_responsable_de_la_empresa', 'terminales_bancarias', type_='foreignkey')
    op.drop_index('uq_terminal_sin_empresa_por_responsable', table_name='terminales_bancarias',
                  postgresql_where=sa.text('empresa_id IS NULL'))
    op.drop_index(op.f('ix_terminales_bancarias_usuario_id'), table_name='terminales_bancarias')
    op.alter_column('terminales_bancarias', 'empresa_id', existing_type=sa.UUID(), nullable=False)
    op.drop_column('terminales_bancarias', 'usuario_id')
    op.drop_constraint('uq_empresas_id_usuario', 'empresas', type_='unique')
