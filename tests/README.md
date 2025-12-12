# process-ai-core

Core de IA para generar documentación de procesos (SOPs, manuales operativos)
a partir de insumos crudos:

- Audio (reuniones, explicaciones de procesos)
- Video (demos de sistemas, walkthroughs)
- Imágenes (pizarrones, capturas de pantalla)
- Texto (notas sueltas, mails, especificaciones)

Pensado como núcleo reutilizable para:

- Productos SaaS de documentación de procesos
- Herramientas internas de consultoría
- Integraciones con Notion / Confluence / Trello / etc.

## Estado

- ✅ PoC inicial en Python
- ✅ Estructura de proyecto (paquete + tests)
- ✅ Ingesta de `RawAsset`
- ✅ Enriquecimiento de audio (transcripción con OpenAI)
- ✅ Motor que genera documento de proceso en Markdown (con JSON mock)
- ⏳ Próximo: usar modelo de texto real para generar el JSON de `ProcessDocument`
- ⏳ Próximo: manejo real de video (extraer audio + transcribir)
- ⏳ Próximo: manejo real de imágenes (visión)

## Requisitos

- Python 3.10+
- Cuenta de OpenAI y API key

## Instalación

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e ".[dev]"