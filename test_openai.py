from dotenv import load_dotenv
from openai import OpenAI
import os

print("🔍 Cargando .env…")
load_dotenv()

api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise RuntimeError("❌ OPENAI_API_KEY no encontrada en .env")

print("✅ API key encontrada (no la muestro por seguridad)")

print("🔌 Probando conexión con OpenAI…")
client = OpenAI(api_key=api_key)

try:
    models = client.models.list()
    print("✅ Conexión exitosa!")
    print("📦 Modelos disponibles (primeros 5):")
    for m in models.data[:5]:
        print(" -", m.id)
except Exception as e:
    print("❌ Error al conectarse a OpenAI:")
    print(e)