# Process AI Core - UI

Frontend Next.js para Process AI Core.

## Instalación

```bash
# Instalar dependencias
npm install
# o
yarn install
```

## Configuración

1. Copiar `.env.local.example` a `.env.local`:
```bash
cp .env.local.example .env.local
```

2. Ajustar la URL de la API si es necesario (por defecto: `http://localhost:8000`)

## Desarrollo

```bash
npm run dev
# o
yarn dev
```

La aplicación estará disponible en `http://localhost:3000`

## Estructura

```
ui/
├── app/              # Next.js App Router
├── components/       # Componentes React reutilizables
├── lib/              # Utilidades y cliente API
└── public/           # Archivos estáticos
```

## Migración a proyecto separado

Para mover esta UI a otro proyecto:

1. Copiar toda la carpeta `ui/`
2. Copiar `package.json` y `package-lock.json`
3. Ajustar `NEXT_PUBLIC_API_URL` en `.env.local` para apuntar al backend separado
4. Ejecutar `npm install` y `npm run dev`

