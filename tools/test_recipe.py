#!/usr/bin/env python3
"""
Script rápido para probar una receta desde un archivo de audio.

Uso:
    python tools/test_recipe.py <archivo_audio> [nombre_receta] [modo]

Ejemplos:
    python tools/test_recipe.py audio.mp3
    python tools/test_recipe.py audio.m4a "Pasta Carbonara" simple
    python tools/test_recipe.py audio.wav "Torta de Chocolate" detallado
"""

import sys
import requests
from pathlib import Path

def test_recipe(audio_path: str, recipe_name: str = "Receta de Prueba", mode: str = "simple"):
    """
    Prueba crear una receta desde un archivo de audio.
    
    Args:
        audio_path: Ruta al archivo de audio
        recipe_name: Nombre de la receta
        mode: Modo ('simple' o 'detallado')
    """
    audio_file = Path(audio_path)
    
    if not audio_file.exists():
        print(f"❌ Error: El archivo {audio_path} no existe")
        sys.exit(1)
    
    if not audio_file.suffix.lower() in ['.mp3', '.m4a', '.wav', '.aac', '.ogg', '.opus']:
        print(f"⚠️  Advertencia: El archivo {audio_file.suffix} podría no ser un audio válido")
    
    print(f"🍳 Creando receta: {recipe_name}")
    print(f"📁 Archivo: {audio_file.name}")
    print(f"🎯 Modo: {mode}")
    print()
    
    # Preparar el request
    url = "http://localhost:8000/api/v1/recipe-runs"
    
    with open(audio_file, 'rb') as f:
        files = {
            'audio_files': (audio_file.name, f, 'audio/mpeg')
        }
        data = {
            'recipe_name': recipe_name,
            'mode': mode
        }
        
        print("📤 Enviando request...")
        try:
            response = requests.post(url, files=files, data=data, timeout=300)
            
            if response.status_code == 200:
                result = response.json()
                print("✅ Receta creada exitosamente!")
                print()
                print(f"🆔 Run ID: {result.get('run_id')}")
                print(f"📊 Status: {result.get('status')}")
                print()
                
                artifacts = result.get('artifacts', {})
                if artifacts:
                    print("📄 Artefactos generados:")
                    if artifacts.get('json'):
                        print(f"   JSON: {artifacts['json']}")
                    if artifacts.get('markdown'):
                        print(f"   Markdown: {artifacts['markdown']}")
                    if artifacts.get('pdf'):
                        print(f"   PDF: {artifacts['pdf']}")
                    
                    # Mostrar URLs para acceder
                    base_url = "http://localhost:8000"
                    print()
                    print("🔗 URLs para ver los artefactos:")
                    if artifacts.get('json'):
                        print(f"   {base_url}{artifacts['json']}")
                    if artifacts.get('markdown'):
                        print(f"   {base_url}{artifacts['markdown']}")
                    if artifacts.get('pdf'):
                        print(f"   {base_url}{artifacts['pdf']}")
                else:
                    print("⚠️  No se generaron artefactos aún (puede estar procesando)")
                
                if result.get('error'):
                    print(f"⚠️  Error: {result['error']}")
                    
            else:
                print(f"❌ Error: HTTP {response.status_code}")
                try:
                    error_detail = response.json()
                    print(f"   Detalle: {error_detail.get('detail', 'Error desconocido')}")
                except:
                    print(f"   Respuesta: {response.text}")
                sys.exit(1)
                
        except requests.exceptions.ConnectionError:
            print("❌ Error: No se pudo conectar al servidor")
            print("   Asegúrate de que el backend esté corriendo en http://localhost:8000")
            sys.exit(1)
        except requests.exceptions.Timeout:
            print("⏱️  Timeout: El procesamiento está tomando más tiempo del esperado")
            print("   Esto es normal para archivos de audio largos")
        except Exception as e:
            print(f"❌ Error inesperado: {e}")
            sys.exit(1)


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Uso: python tools/test_recipe.py <archivo_audio> [nombre_receta] [modo]")
        print()
        print("Ejemplos:")
        print("  python tools/test_recipe.py audio.mp3")
        print("  python tools/test_recipe.py audio.m4a \"Pasta Carbonara\" simple")
        print("  python tools/test_recipe.py audio.wav \"Torta de Chocolate\" detallado")
        sys.exit(1)
    
    audio_path = sys.argv[1]
    recipe_name = sys.argv[2] if len(sys.argv) > 2 else "Receta de Prueba"
    mode = sys.argv[3] if len(sys.argv) > 3 else "simple"
    
    if mode not in ['simple', 'detallado']:
        print(f"❌ Error: El modo debe ser 'simple' o 'detallado', no '{mode}'")
        sys.exit(1)
    
    test_recipe(audio_path, recipe_name, mode)
