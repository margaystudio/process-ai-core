#!/usr/bin/env python3
"""
Script para crear planes de suscripción iniciales.

Ejecutar:
    python tools/seed_subscription_plans.py
"""

import json
from process_ai_core.db.database import get_db_session
from process_ai_core.db.models import SubscriptionPlan
from process_ai_core.db.helpers import get_subscription_plan_by_name


def seed_plans():
    """Crea los planes de suscripción iniciales."""
    with get_db_session() as session:
        # Planes B2B (Organizaciones)
        b2b_plans = [
            {
                "name": "b2b_trial",
                "display_name": "Trial B2B",
                "description": "Plan de prueba para organizaciones (14 días)",
                "plan_type": "b2b",
                "price_monthly": 0.0,
                "price_yearly": 0.0,
                "max_users": 3,
                "max_documents": 10,
                "max_documents_per_month": 10,
                "max_storage_gb": 1.0,
                "features_json": json.dumps({
                    "ai_generation": True,
                    "pdf_export": True,
                    "team_collaboration": True,
                    "api_access": False,
                    "custom_branding": False,
                }),
                "sort_order": 1,
            },
            {
                "name": "b2b_starter",
                "display_name": "Starter B2B",
                "description": "Plan inicial para pequeñas organizaciones",
                "plan_type": "b2b",
                "price_monthly": 49.0,
                "price_yearly": 490.0,
                "max_users": 10,
                "max_documents": 100,
                "max_documents_per_month": 50,
                "max_storage_gb": 10.0,
                "features_json": json.dumps({
                    "ai_generation": True,
                    "pdf_export": True,
                    "team_collaboration": True,
                    "api_access": False,
                    "custom_branding": False,
                }),
                "sort_order": 2,
            },
            {
                "name": "b2b_professional",
                "display_name": "Professional B2B",
                "description": "Plan para organizaciones medianas",
                "plan_type": "b2b",
                "price_monthly": 149.0,
                "price_yearly": 1490.0,
                "max_users": 50,
                "max_documents": 1000,
                "max_documents_per_month": 200,
                "max_storage_gb": 100.0,
                "features_json": json.dumps({
                    "ai_generation": True,
                    "pdf_export": True,
                    "team_collaboration": True,
                    "api_access": True,
                    "custom_branding": True,
                }),
                "sort_order": 3,
            },
            {
                "name": "b2b_enterprise",
                "display_name": "Enterprise B2B",
                "description": "Plan para grandes organizaciones",
                "plan_type": "b2b",
                "price_monthly": 499.0,
                "price_yearly": 4990.0,
                "max_users": None,  # Ilimitado
                "max_documents": None,  # Ilimitado
                "max_documents_per_month": None,  # Ilimitado
                "max_storage_gb": None,  # Ilimitado
                "features_json": json.dumps({
                    "ai_generation": True,
                    "pdf_export": True,
                    "team_collaboration": True,
                    "api_access": True,
                    "custom_branding": True,
                    "priority_support": True,
                    "sla": True,
                }),
                "sort_order": 4,
            },
        ]
        
        # Planes B2C (Usuarios individuales)
        b2c_plans = [
            {
                "name": "b2c_free",
                "display_name": "Free",
                "description": "Plan gratuito para usuarios individuales",
                "plan_type": "b2c",
                "price_monthly": 0.0,
                "price_yearly": 0.0,
                "max_users": None,  # No aplica para B2C
                "max_documents": 10,
                "max_documents_per_month": 5,
                "max_storage_gb": 0.5,
                "features_json": json.dumps({
                    "ai_generation": True,
                    "pdf_export": True,
                    "mobile_app": True,
                    "ads": True,
                }),
                "sort_order": 1,
            },
            {
                "name": "b2c_premium",
                "display_name": "Premium",
                "description": "Plan premium para usuarios individuales",
                "plan_type": "b2c",
                "price_monthly": 9.99,
                "price_yearly": 99.99,
                "max_users": None,  # No aplica para B2C
                "max_documents": 1000,
                "max_documents_per_month": 100,
                "max_storage_gb": 10.0,
                "features_json": json.dumps({
                    "ai_generation": True,
                    "pdf_export": True,
                    "mobile_app": True,
                    "ads": False,
                    "priority_support": True,
                }),
                "sort_order": 2,
            },
        ]
        
        all_plans = b2b_plans + b2c_plans
        
        created_count = 0
        updated_count = 0
        
        for plan_data in all_plans:
            existing = get_subscription_plan_by_name(session, plan_data["name"])
            if existing:
                # Actualizar plan existente
                for key, value in plan_data.items():
                    setattr(existing, key, value)
                existing.is_active = True
                updated_count += 1
                print(f"✓ Actualizado: {plan_data['display_name']}")
            else:
                # Crear nuevo plan
                plan = SubscriptionPlan(**plan_data)
                session.add(plan)
                created_count += 1
                print(f"✓ Creado: {plan_data['display_name']}")
        
        session.commit()
        print(f"\n✅ Seed completado: {created_count} planes creados, {updated_count} planes actualizados")


if __name__ == "__main__":
    seed_plans()


