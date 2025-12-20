export default function Home() {
  return (
    <main className="min-h-screen p-8">
      <div className="max-w-4xl mx-auto">
        <h1 className="text-4xl font-bold mb-4">Process AI Core</h1>
        <p className="text-gray-600 mb-8">
          Generación automática de documentación de procesos y recetas
        </p>
        
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <a
            href="/clients/new"
            className="p-6 border rounded-lg hover:bg-gray-50 transition"
          >
            <h2 className="text-xl font-semibold mb-2">Nuevo Cliente</h2>
            <p className="text-gray-600">
              Registra una nueva organización/cliente en el sistema
            </p>
          </a>
          
          <a
            href="/processes/new"
            className="p-6 border rounded-lg hover:bg-gray-50 transition"
          >
            <h2 className="text-xl font-semibold mb-2">Nuevo Proceso</h2>
            <p className="text-gray-600">
              Crea documentación de procesos desde audio, video e imágenes
            </p>
          </a>
        </div>
      </div>
    </main>
  )
}

