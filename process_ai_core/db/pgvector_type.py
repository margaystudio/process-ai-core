"""Tipo SQLAlchemy pgvector-aware, portable SQLite/PostgreSQL.

Las columnas de embedding se guardan como el literal pgvector ("[0.1,0.2,...]").
En PostgreSQL la columna real es ``vector(dim)``; en SQLite (tests) es ``TEXT``.

Mapearlas como ``Text`` a secas rompe los INSERT del ORM en PostgreSQL: el dialecto
psycopg renderiza el bind como ``$n::VARCHAR`` (render_bind_cast de String) y Postgres
rechaza ``vector = varchar`` (DatatypeMismatch), incluso al insertar NULL. Un
``UserDefinedType`` no dispara ese cast, así que el literal viaja como texto y la
función de entrada de pgvector lo parsea. En SQLite cae a ``TEXT`` sin cambios.

El valor de ida y vuelta sigue siendo el literal string (lo consumen
``embedding_to_literal`` / ``literal_to_embedding`` en semantic.chunking).
"""

from __future__ import annotations

from sqlalchemy import types


class _PgVector(types.UserDefinedType):
    """Tipo nativo ``vector(dim)`` de pgvector (solo PostgreSQL)."""

    cache_ok = True

    def __init__(self, dim: int | None = None):
        self.dim = dim

    def get_col_spec(self, **kw) -> str:
        return f"vector({self.dim})" if self.dim else "vector"


class VectorLiteral(types.TypeDecorator):
    """Columna de embedding: ``vector(dim)`` en PostgreSQL, ``TEXT`` en el resto.

    El valor Python es siempre el literal pgvector ("[...]"); no se procesa."""

    impl = types.Text
    cache_ok = True

    def __init__(self, dim: int = 1536, **kw):
        self.dim = dim
        super().__init__(**kw)

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(_PgVector(self.dim))
        return dialect.type_descriptor(types.Text())
