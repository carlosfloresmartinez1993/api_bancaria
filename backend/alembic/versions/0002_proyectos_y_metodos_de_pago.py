"""proyectos y metodos de pago

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-06 15:16:45.785099
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '0002'
down_revision: Union[str, None] = '0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Se empieza de cero con los datos del negocio (decisión del usuario): se conservan los usuarios
    # y la bitácora; se borran empresas, terminales, porcentajes, movimientos y salidas.
    op.execute("TRUNCATE movimientos_terminal, salidas_empresa, historial_porcentajes_terminal, "
               "terminales_bancarias, empresas")

    # 1. Estructura anterior (primero, porque algunos índices nuevos reutilizan nombres)
    op.drop_index(op.f('ix_salidas_empresa_fecha'), table_name='salidas_empresa')
    op.drop_index(op.f('ix_salidas_empresa_usuario_id'), table_name='salidas_empresa')
    op.drop_table('salidas_empresa')
    op.drop_index(op.f('ix_movimientos_fecha'), table_name='movimientos_terminal')
    op.drop_index(op.f('ix_movimientos_terminal_fecha'), table_name='movimientos_terminal')
    op.drop_index(op.f('ix_movimientos_terminal_usuario_id'), table_name='movimientos_terminal')
    op.drop_table('movimientos_terminal')
    op.drop_index(op.f('ix_historial_terminal_inicio'), table_name='historial_porcentajes_terminal')
    op.drop_index(op.f('uq_historial_abierto_por_terminal'), table_name='historial_porcentajes_terminal', postgresql_where='(fecha_fin_vigencia IS NULL)')
    op.drop_table('historial_porcentajes_terminal')
    op.alter_column('empresas', 'csf',
               existing_type=sa.VARCHAR(length=100),
               nullable=True)
    op.alter_column('empresas', 'banco',
               existing_type=sa.VARCHAR(length=100),
               nullable=True)
    op.alter_column('empresas', 'numero_cuenta',
               existing_type=sa.VARCHAR(length=30),
               nullable=True)
    op.drop_column('empresas', 'documento_pdf_1_url')
    op.drop_column('empresas', 'logo_url')
    op.drop_column('empresas', 'documento_pdf_2_url')
    op.drop_column('terminales_bancarias', 'datos_extra')

    # 2. Estructura nueva: Empresa → Cliente (terminal) → Proyecto (% de comisión)
    op.create_table('metodos_pago',
    sa.Column('nombre', sa.String(length=50), nullable=False),
    sa.Column('activo', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.Column('fecha_registro', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_metodos_pago')),
    sa.UniqueConstraint('nombre', name=op.f('uq_metodos_pago_nombre'))
    )
    op.create_table('proyectos',
    sa.Column('terminal_id', sa.Uuid(), nullable=False),
    sa.Column('nombre', sa.String(length=100), nullable=False),
    sa.Column('activo', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.Column('fecha_registro', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.ForeignKeyConstraint(['terminal_id'], ['terminales_bancarias.id'], name=op.f('fk_proyectos_terminal_id_terminales_bancarias'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_proyectos')),
    sa.UniqueConstraint('terminal_id', 'nombre', name='uq_proyecto_por_terminal')
    )
    op.create_index(op.f('ix_proyectos_terminal_id'), 'proyectos', ['terminal_id'], unique=False)
    op.create_table('historial_porcentajes_proyecto',
    sa.Column('proyecto_id', sa.Uuid(), nullable=False),
    sa.Column('porcentaje', sa.Numeric(precision=5, scale=2), nullable=False),
    sa.Column('fecha_inicio_vigencia', sa.Date(), nullable=False),
    sa.Column('fecha_fin_vigencia', sa.Date(), nullable=True),
    sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.CheckConstraint('fecha_fin_vigencia IS NULL OR fecha_fin_vigencia > fecha_inicio_vigencia', name=op.f('ck_historial_porcentajes_proyecto_vigencia_valida')),
    sa.CheckConstraint('porcentaje >= 0 AND porcentaje < 100', name=op.f('ck_historial_porcentajes_proyecto_porcentaje_rango')),
    sa.ForeignKeyConstraint(['proyecto_id'], ['proyectos.id'], name=op.f('fk_historial_porcentajes_proyecto_proyecto_id_proyectos'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_historial_porcentajes_proyecto'))
    )
    op.create_index('ix_historial_proyecto_inicio', 'historial_porcentajes_proyecto', ['proyecto_id', 'fecha_inicio_vigencia'], unique=False)
    op.create_index('uq_historial_abierto_por_proyecto', 'historial_porcentajes_proyecto', ['proyecto_id'], unique=True, postgresql_where=sa.text('fecha_fin_vigencia IS NULL'))
    op.create_table('movimientos',
    sa.Column('proyecto_id', sa.Uuid(), nullable=False),
    sa.Column('usuario_id', sa.Uuid(), nullable=False),
    sa.Column('metodo_pago_id', sa.Uuid(), nullable=False),
    sa.Column('fecha_movimiento', sa.Date(), nullable=False),
    sa.Column('monto_bruto', sa.Numeric(precision=14, scale=2), nullable=False),
    sa.Column('porcentaje_aplicado', sa.Numeric(precision=5, scale=2), nullable=False),
    sa.Column('monto_neto', sa.Numeric(precision=14, scale=2), sa.Computed('round(monto_bruto * (1 - porcentaje_aplicado / 100), 2)', persisted=True), nullable=False),
    sa.Column('requiere_factura', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.Column('fecha_captura', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('observaciones', sa.Text(), nullable=True),
    sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.CheckConstraint('monto_bruto > 0', name=op.f('ck_movimientos_monto_bruto_positivo')),
    sa.CheckConstraint('porcentaje_aplicado >= 0 AND porcentaje_aplicado < 100', name=op.f('ck_movimientos_porcentaje_rango')),
    sa.ForeignKeyConstraint(['metodo_pago_id'], ['metodos_pago.id'], name=op.f('fk_movimientos_metodo_pago_id_metodos_pago'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['proyecto_id'], ['proyectos.id'], name=op.f('fk_movimientos_proyecto_id_proyectos'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['usuario_id'], ['usuarios.id'], name=op.f('fk_movimientos_usuario_id_usuarios'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_movimientos'))
    )
    op.create_index('ix_movimientos_fecha', 'movimientos', ['fecha_movimiento'], unique=False)
    op.create_index(op.f('ix_movimientos_metodo_pago_id'), 'movimientos', ['metodo_pago_id'], unique=False)
    op.create_index('ix_movimientos_proyecto_fecha', 'movimientos', ['proyecto_id', 'fecha_movimiento'], unique=False)
    op.create_index(op.f('ix_movimientos_usuario_id'), 'movimientos', ['usuario_id'], unique=False)
    op.create_table('salidas',
    sa.Column('proyecto_id', sa.Uuid(), nullable=False),
    sa.Column('usuario_id', sa.Uuid(), nullable=False),
    sa.Column('metodo_pago_id', sa.Uuid(), nullable=False),
    sa.Column('monto', sa.Numeric(precision=14, scale=2), nullable=False),
    sa.Column('destino', sa.String(length=255), nullable=False),
    sa.Column('fecha', sa.Date(), nullable=False),
    sa.Column('observaciones', sa.Text(), nullable=True),
    sa.Column('fecha_registro', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.CheckConstraint('monto > 0', name=op.f('ck_salidas_monto_positivo')),
    sa.ForeignKeyConstraint(['metodo_pago_id'], ['metodos_pago.id'], name=op.f('fk_salidas_metodo_pago_id_metodos_pago'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['proyecto_id'], ['proyectos.id'], name=op.f('fk_salidas_proyecto_id_proyectos'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['usuario_id'], ['usuarios.id'], name=op.f('fk_salidas_usuario_id_usuarios'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_salidas'))
    )
    op.create_index(op.f('ix_salidas_metodo_pago_id'), 'salidas', ['metodo_pago_id'], unique=False)
    op.create_index('ix_salidas_proyecto_fecha', 'salidas', ['proyecto_id', 'fecha'], unique=False)
    op.create_index(op.f('ix_salidas_usuario_id'), 'salidas', ['usuario_id'], unique=False)

    # 3. Catálogo inicial de métodos de pago (el admin puede agregar más)
    op.execute("INSERT INTO metodos_pago (nombre) VALUES ('Transferencia'), ('Depósito'), ('Efectivo')")


def downgrade() -> None:
    # Los datos de la estructura nueva no se pueden convertir a la anterior: se pierden.
    op.drop_index(op.f('ix_salidas_usuario_id'), table_name='salidas')
    op.drop_index('ix_salidas_proyecto_fecha', table_name='salidas')
    op.drop_index(op.f('ix_salidas_metodo_pago_id'), table_name='salidas')
    op.drop_table('salidas')
    op.drop_index(op.f('ix_movimientos_usuario_id'), table_name='movimientos')
    op.drop_index('ix_movimientos_proyecto_fecha', table_name='movimientos')
    op.drop_index(op.f('ix_movimientos_metodo_pago_id'), table_name='movimientos')
    op.drop_index('ix_movimientos_fecha', table_name='movimientos')
    op.drop_table('movimientos')
    op.drop_index('uq_historial_abierto_por_proyecto', table_name='historial_porcentajes_proyecto', postgresql_where=sa.text('fecha_fin_vigencia IS NULL'))
    op.drop_index('ix_historial_proyecto_inicio', table_name='historial_porcentajes_proyecto')
    op.drop_table('historial_porcentajes_proyecto')
    op.drop_index(op.f('ix_proyectos_terminal_id'), table_name='proyectos')
    op.drop_table('proyectos')
    op.drop_table('metodos_pago')
    op.execute("TRUNCATE terminales_bancarias, empresas")
    op.add_column('terminales_bancarias', sa.Column('datos_extra', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), autoincrement=False, nullable=False))
    op.add_column('empresas', sa.Column('documento_pdf_2_url', sa.VARCHAR(length=500), autoincrement=False, nullable=True))
    op.add_column('empresas', sa.Column('logo_url', sa.VARCHAR(length=500), autoincrement=False, nullable=True))
    op.add_column('empresas', sa.Column('documento_pdf_1_url', sa.VARCHAR(length=500), autoincrement=False, nullable=True))
    op.alter_column('empresas', 'numero_cuenta',
               existing_type=sa.VARCHAR(length=30),
               nullable=False)
    op.alter_column('empresas', 'banco',
               existing_type=sa.VARCHAR(length=100),
               nullable=False)
    op.alter_column('empresas', 'csf',
               existing_type=sa.VARCHAR(length=100),
               nullable=False)
    op.create_table('historial_porcentajes_terminal',
    sa.Column('terminal_id', sa.UUID(), autoincrement=False, nullable=False),
    sa.Column('porcentaje', sa.NUMERIC(precision=5, scale=2), autoincrement=False, nullable=False),
    sa.Column('fecha_inicio_vigencia', sa.DATE(), autoincrement=False, nullable=False),
    sa.Column('fecha_fin_vigencia', sa.DATE(), autoincrement=False, nullable=True),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), autoincrement=False, nullable=False),
    sa.CheckConstraint('fecha_fin_vigencia IS NULL OR fecha_fin_vigencia > fecha_inicio_vigencia', name=op.f('ck_historial_porcentajes_terminal_vigencia_valida')),
    sa.CheckConstraint('porcentaje >= 0::numeric AND porcentaje < 100::numeric', name=op.f('ck_historial_porcentajes_terminal_porcentaje_rango')),
    sa.ForeignKeyConstraint(['terminal_id'], ['terminales_bancarias.id'], name=op.f('fk_historial_porcentajes_terminal_terminal_id_terminale_5f30'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_historial_porcentajes_terminal'))
    )
    op.create_index(op.f('uq_historial_abierto_por_terminal'), 'historial_porcentajes_terminal', ['terminal_id'], unique=True, postgresql_where='(fecha_fin_vigencia IS NULL)')
    op.create_index(op.f('ix_historial_terminal_inicio'), 'historial_porcentajes_terminal', ['terminal_id', 'fecha_inicio_vigencia'], unique=False)
    op.create_table('movimientos_terminal',
    sa.Column('terminal_id', sa.UUID(), autoincrement=False, nullable=False),
    sa.Column('usuario_id', sa.UUID(), autoincrement=False, nullable=False),
    sa.Column('fecha_movimiento', sa.DATE(), autoincrement=False, nullable=False),
    sa.Column('monto_bruto', sa.NUMERIC(precision=14, scale=2), autoincrement=False, nullable=False),
    sa.Column('porcentaje_aplicado', sa.NUMERIC(precision=5, scale=2), autoincrement=False, nullable=False),
    sa.Column('monto_neto', sa.NUMERIC(precision=14, scale=2), sa.Computed('round((monto_bruto * ((1)::numeric - (porcentaje_aplicado / (100)::numeric))), 2)', persisted=True), autoincrement=False, nullable=False),
    sa.Column('fecha_captura', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=False),
    sa.Column('observaciones', sa.TEXT(), autoincrement=False, nullable=True),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), autoincrement=False, nullable=False),
    sa.CheckConstraint('monto_bruto > 0::numeric', name=op.f('ck_movimientos_terminal_monto_bruto_positivo')),
    sa.CheckConstraint('porcentaje_aplicado >= 0::numeric AND porcentaje_aplicado < 100::numeric', name=op.f('ck_movimientos_terminal_porcentaje_rango')),
    sa.ForeignKeyConstraint(['terminal_id'], ['terminales_bancarias.id'], name=op.f('fk_movimientos_terminal_terminal_id_terminales_bancarias'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['usuario_id'], ['usuarios.id'], name=op.f('fk_movimientos_terminal_usuario_id_usuarios'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_movimientos_terminal'))
    )
    op.create_index(op.f('ix_movimientos_terminal_usuario_id'), 'movimientos_terminal', ['usuario_id'], unique=False)
    op.create_index(op.f('ix_movimientos_terminal_fecha'), 'movimientos_terminal', ['terminal_id', 'fecha_movimiento'], unique=False)
    op.create_index(op.f('ix_movimientos_fecha'), 'movimientos_terminal', ['fecha_movimiento'], unique=False)
    op.create_table('salidas_empresa',
    sa.Column('empresa_id', sa.UUID(), autoincrement=False, nullable=False),
    sa.Column('usuario_id', sa.UUID(), autoincrement=False, nullable=False),
    sa.Column('monto', sa.NUMERIC(precision=14, scale=2), autoincrement=False, nullable=False),
    sa.Column('destino', sa.VARCHAR(length=255), autoincrement=False, nullable=False),
    sa.Column('fecha', sa.DATE(), autoincrement=False, nullable=False),
    sa.Column('observaciones', sa.TEXT(), autoincrement=False, nullable=True),
    sa.Column('fecha_registro', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=False),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), autoincrement=False, nullable=False),
    sa.CheckConstraint('monto > 0::numeric', name=op.f('ck_salidas_empresa_monto_positivo')),
    sa.ForeignKeyConstraint(['empresa_id'], ['empresas.id'], name=op.f('fk_salidas_empresa_empresa_id_empresas'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['usuario_id'], ['usuarios.id'], name=op.f('fk_salidas_empresa_usuario_id_usuarios'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_salidas_empresa'))
    )
    op.create_index(op.f('ix_salidas_empresa_usuario_id'), 'salidas_empresa', ['usuario_id'], unique=False)
    op.create_index(op.f('ix_salidas_empresa_fecha'), 'salidas_empresa', ['empresa_id', 'fecha'], unique=False)
