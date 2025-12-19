# process-ai-core – Reglas del proyecto

Este es un proyecto Python de calidad productiva.
El sistema genera documentación de procesos (JSON → Markdown → PDF)
a partir de inputs multimedia (audio, video, imágenes y texto).

Principios fundamentales:
- Estabilidad > elegancia
- Cambios mínimos y controlados
- Nada de refactors especulativos
- Ningún cambio silencioso de comportamiento

Reglas estrictas:
- NUNCA refactorizar código que ya funciona, salvo pedido explícito
- NUNCA renombrar funciones, parámetros o archivos sin permiso
- NUNCA cambiar tipos de retorno sin discutirlo antes
- Si hay dudas, PREGUNTAR antes de modificar

Arquitectura (visión general):
- media.py: ingesta y enriquecimiento de assets
- doc_engine.py: armado de prompt, parseo de JSON y render de Markdown
- llm_client.py: todas las llamadas al LLM viven acá
- run_demo.py: orquestación y CLI
- domain_models.py: solo dataclasses (sin lógica)

Importante:
Este proyecto evoluciona de forma incremental.
Se corrige solo el problema actual, sin efectos colaterales.