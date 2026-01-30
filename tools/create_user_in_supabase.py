#!/usr/bin/env python3
"""
Script para crear un usuario en Supabase Auth.

Este script crea el usuario en Supabase Auth para que pueda iniciar sesión.
Después de crear el usuario en Supabase, se vinculará automáticamente con la BD local
cuando el usuario inicie sesión (mediante sync-user).

Ejecutar:
    python tools/create_user_in_supabase.py
"""

import sys
import os
from pathlib import Path

# Agregar el directorio raíz al path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

try:
    from supabase import create_client, Client
except ImportError:
    print("❌ Error: supabase-py no está instalado.")
    print("   Instala con: pip install supabase")
    sys.exit(1)


def create_user_in_supabase():
    """Crea el usuario en Supabase Auth."""
    print("=" * 70)
    print("  CREAR USUARIO EN SUPABASE AUTH")
    print("=" * 70)
    print()
    
    # Verificar variables de entorno
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    
    if not supabase_url or not supabase_service_key:
        print("❌ Error: Variables de entorno no configuradas.")
        print("   Necesitas configurar en .env:")
        print("   - SUPABASE_URL")
        print("   - SUPABASE_SERVICE_ROLE_KEY")
        print()
        print("   Obtén estos valores desde:")
        print("   - Supabase Dashboard > Settings > API")
        sys.exit(1)
    
    # Crear cliente de Supabase
    supabase: Client = create_client(supabase_url, supabase_service_key)
    
    # Solicitar datos del usuario
    email = input("Email del usuario: ").strip()
    if not email:
        print("❌ Email requerido.")
        return
    
    # Verificar si el usuario ya existe
    try:
        existing_users = supabase.auth.admin.list_users()
        for user in existing_users.users:
            if user.email == email:
                print(f"⚠️  Usuario {email} ya existe en Supabase Auth.")
                print(f"   User ID: {user.id}")
                print()
                response = input("¿Deseas resetear la contraseña? (s/n): ").strip().lower()
                if response == "s":
                    # Generar nueva contraseña temporal
                    import secrets
                    import string
                    temp_password = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(12))
                    
                    # Actualizar contraseña
                    supabase.auth.admin.update_user_by_id(
                        user.id,
                        {"password": temp_password}
                    )
                    print(f"✅ Contraseña actualizada.")
                    print(f"   Contraseña temporal: {temp_password}")
                    print(f"   IMPORTANTE: Cambia la contraseña después del primer login.")
                return
    except Exception as e:
        print(f"⚠️  Error verificando usuario existente: {e}")
        print("   Continuando con la creación...")
    
    # Solicitar contraseña
    print()
    print("Opciones para la contraseña:")
    print("  1. Generar contraseña temporal automáticamente")
    print("  2. Ingresar contraseña manualmente")
    choice = input("Opción (1/2): ").strip()
    
    if choice == "1":
        import secrets
        import string
        password = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(12))
        print(f"✅ Contraseña generada: {password}")
    else:
        password = input("Contraseña: ").strip()
        if not password:
            print("❌ Contraseña requerida.")
            return
        confirm_password = input("Confirmar contraseña: ").strip()
        if password != confirm_password:
            print("❌ Las contraseñas no coinciden.")
            return
    
    # Solicitar nombre
    name = input("Nombre del usuario (opcional): ").strip() or email.split("@")[0]
    
    print()
    print("📧 Creando usuario en Supabase Auth...")
    
    try:
        # Crear usuario usando Admin API
        response = supabase.auth.admin.create_user({
            "email": email,
            "password": password,
            "email_confirm": True,  # Confirmar email automáticamente
            "user_metadata": {
                "name": name,
            }
        })
        
        if response.user:
            print("✅ Usuario creado exitosamente en Supabase Auth!")
            print()
            print("=" * 70)
            print("  ✅ USUARIO CREADO")
            print("=" * 70)
            print()
            print(f"📧 Email: {email}")
            print(f"👤 Nombre: {name}")
            print(f"🆔 Supabase User ID: {response.user.id}")
            print()
            if choice == "1":
                print(f"🔑 Contraseña temporal: {password}")
                print("   IMPORTANTE: Cambia la contraseña después del primer login.")
            print()
            print("📋 PRÓXIMOS PASOS:")
            print()
            print("1. El usuario puede iniciar sesión ahora con:")
            print(f"   Email: {email}")
            print(f"   Contraseña: {'(la que ingresaste)' if choice == '2' else password}")
            print()
            print("2. Cuando el usuario inicie sesión, el sistema:")
            print("   - Validará las credenciales en Supabase")
            print("   - Llamará a /api/v1/auth/sync-user automáticamente")
            print("   - Vinculará el usuario de Supabase con el usuario local")
            print("   - Usará el email para hacer el match")
            print()
            print("3. Si el usuario local no existe, se creará automáticamente.")
            print("   Si ya existe (como en tu caso), se vinculará por email.")
            print()
            print("💡 NOTA: El usuario local debe tener el mismo email que el de Supabase")
            print("   para que se vincule automáticamente.")
        else:
            print("❌ Error: No se pudo crear el usuario.")
            
    except Exception as e:
        print(f"❌ Error creando usuario: {e}")
        print()
        print("Posibles causas:")
        print("  - Email ya existe en Supabase")
        print("  - Contraseña no cumple requisitos de seguridad")
        print("  - Credenciales de Supabase incorrectas")
        sys.exit(1)


if __name__ == "__main__":
    create_user_in_supabase()
