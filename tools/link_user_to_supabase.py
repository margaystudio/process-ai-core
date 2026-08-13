#!/usr/bin/env python3
"""
Script para vincular un usuario local con Supabase Auth.

Actualiza el external_id del usuario local con el ID de Supabase (sub del JWT).

Ejecutar:
    python tools/link_user_to_supabase.py
"""

import sys
from pathlib import Path

# Agregar el directorio raíz al path
sys.path.insert(0, str(Path(__file__).parent.parent))

from process_ai_core.db.database import get_db_session
from process_ai_core.db.models import User
from datetime import datetime, UTC


def link_user_to_supabase():
    """Vincula un usuario local con Supabase Auth."""
    with get_db_session() as session:
        print("=" * 70)
        print("  VINCULAR USUARIO CON SUPABASE")
        print("=" * 70)
        print()
        
        # Solicitar email
        email = input("Email del usuario a vincular: ").strip()
        if not email:
            print("❌ Email requerido.")
            return
        
        # Buscar usuario
        user = session.query(User).filter_by(email=email).first()
        if not user:
            print(f"❌ Usuario {email} no encontrado en la base de datos.")
            print("   El usuario se crea solo al ingresar por primera vez (sync desde margay-workspace).")
            return
        
        print(f"✅ Usuario encontrado: {user.name} ({user.email})")
        if user.external_id:
            print(f"⚠️  Ya tiene external_id: {user.external_id}")
            response = input("¿Deseas actualizarlo? (s/n): ").strip().lower()
            if response != "s":
                print("❌ Cancelado.")
                return
        
        # Solicitar Supabase User ID
        print()
        print("Para obtener el Supabase User ID:")
        print("  1. Dashboard de Supabase: Users > [usuario] > UUID")
        print("  2. O desde el JWT después de login: data.user.id")
        print("  3. O desde la consola del navegador después de login:")
        print("     supabase.auth.getUser().then(u => console.log(u.data.user.id))")
        print()
        
        supabase_user_id = input("Supabase User ID (sub del JWT): ").strip()
        if not supabase_user_id:
            print("❌ Supabase User ID requerido.")
            return
        
        # Validar formato (debe ser un UUID)
        if len(supabase_user_id) != 36 or supabase_user_id.count('-') != 4:
            print("⚠️  Advertencia: El Supabase User ID no parece un UUID válido.")
            response = input("¿Continuar de todas formas? (s/n): ").strip().lower()
            if response != "s":
                print("❌ Cancelado.")
                return
        
        # Actualizar usuario
        user.external_id = supabase_user_id
        user.auth_provider = "supabase"
        user.updated_at = datetime.now(UTC)
        
        session.commit()
        
        print()
        print("=" * 70)
        print("  ✅ USUARIO VINCULADO CON SUPABASE")
        print("=" * 70)
        print()
        print(f"📧 Email: {user.email}")
        print(f"👤 Nombre: {user.name}")
        print(f"🆔 ID Local: {user.id}")
        print(f"🔗 External ID (Supabase): {user.external_id}")
        print(f"🔐 Auth Provider: {user.auth_provider}")
        print()
        print("✅ El usuario ahora puede autenticarse con Supabase y el sistema")
        print("   lo reconocerá automáticamente.")


if __name__ == "__main__":
    link_user_to_supabase()
