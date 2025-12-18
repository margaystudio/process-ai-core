# tools/seed_demo.py
from __future__ import annotations

from process_ai_core.db.database import get_db_session
from process_ai_core.db.models import Client, Process


def main():
    with get_db_session() as db:
        # 1) Client (empresa / tenant)
        slug = "demo"
        client = db.query(Client).filter(Client.slug == slug).first()

        if not client:
            client = Client(
                slug=slug,
                name="Cliente Demo",
                country="UY",
                business_type="estaciones_servicio",     # catalog: business_type (si existe)
                language_style="es_uy_formal",           # catalog: language_style

                # defaults (catálogos)
                default_audience="operativo",            # audience
                default_detail_level="breve",            # detail_level
                default_formality="media",               # formality

                # contexto libre (esto es lo que antes metías en context_json)
                context_text=(
                    "Rubro: estaciones de servicio.\n"
                    "Objetivo de documentos: operativos, entendibles por personal de pista.\n"
                    "Restricción: documentos cortos (ideal 1–2 páginas).\n"
                    "Tono: español uruguayo formal, claro y directo.\n"
                ),
            )
            db.add(client)
            db.commit()
            db.refresh(client)

        # 2) Process (uno dentro del cliente)
        proc_name = "Atender cliente en pista"
        process = (
            db.query(Process)
            .filter(Process.client_id == client.id, Process.name == proc_name)
            .first()
        )

        if not process:
            process = Process(
                client_id=client.id,
                name=proc_name,
                status="draft",
                description="Atención al cliente en pista: saludo, carga, cobro y cierre.",
                process_type="operativo",   # catalog: process_type

                # (opcional) overrides por proceso: si lo dejás vacío usa defaults del cliente
                # audience="operativo",
                # detail_level="breve",
                # formality="media",

                context_text=(
                    "Proceso en pista. Prioridad: seguridad, claridad y secuencia.\n"
                    "Evitar textos largos y tecnicismos.\n"
                ),
            )
            db.add(process)
            db.commit()
            db.refresh(process)

        print("✅ Client:", client.id, client.slug, client.name)
        print("✅ Process:", process.id, process.name)


if __name__ == "__main__":
    main()