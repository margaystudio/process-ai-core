# Contexto del proyecto – process-ai-core

## Qué hace este proyecto

Este sistema transforma conocimiento operativo no estructurado
en documentación de procesos estructurada.

Inputs posibles:
- Audios (explicaciones habladas de procesos)
- Videos (grabaciones de pantalla)
- Imágenes (capturas, evidencia visual)
- Textos (notas o instrucciones)

Pipeline general:
1. Se detectan los assets desde carpetas
2. Los assets se enriquecen:
   - audio → transcripción
   - video → transcripción + inferencia de pasos + capturas
   - imágenes → evidencia visual
3. Se construye un prompt grande con toda la información
4. El LLM devuelve un JSON estructurado del proceso
5. El JSON se convierte a Markdown
6. El Markdown se exporta a PDF usando Pandoc

## Restricciones de diseño clave

- El número de pasos NO se conoce de antemano
- El usuario NUNCA asigna imágenes a pasos manualmente
- La relación paso ↔ imagen se infiere automáticamente
- El sistema debe funcionar aunque falten tipos de media

## Qué se considera “funcionando”

- El pipeline corre de punta a punta sin romperse
- Las imágenes aparecen en el PDF
- La estructura del Markdown es estable
- El documento final es usable por humanos

## Qué NO es objetivo

- Formato perfecto
- Abstracciones innecesarias
- Refactors automáticos
- “Clean code” si rompe estabilidad