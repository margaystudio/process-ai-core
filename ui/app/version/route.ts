// Expone la versión deployada de la UI — equivalente del /health del backend.
// NEXT_PUBLIC_APP_VERSION se hornea en build (la inyecta ops/release.py con el tag releaseado).
export const dynamic = "force-static";

export function GET() {
  return Response.json({
    service: "margay-process-ai-ui",
    version: process.env.NEXT_PUBLIC_APP_VERSION ?? "dev",
  });
}
