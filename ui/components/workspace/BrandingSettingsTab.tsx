'use client'

import { ChangeEvent } from 'react'
import Image from 'next/image'

type BrandingSettingsTabProps = {
  brandingIconUrl: string | null
  brandingPrimaryColor: string
  brandingSecondaryColor: string
  brandingSaving: boolean
  brandingMessage: string | null
  onFileChange: (e: ChangeEvent<HTMLInputElement>) => Promise<void>
  onDeleteIcon: () => Promise<void>
  onPrimaryColorChange: (value: string) => void
  onSecondaryColorChange: (value: string) => void
  onSaveColors: () => Promise<void>
}

export default function BrandingSettingsTab({
  brandingIconUrl,
  brandingPrimaryColor,
  brandingSecondaryColor,
  brandingSaving,
  brandingMessage,
  onFileChange,
  onDeleteIcon,
  onPrimaryColorChange,
  onSecondaryColorChange,
  onSaveColors,
}: BrandingSettingsTabProps) {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold mb-2">Personalización</h2>
        <p className="text-ink-600">
          Cargá un icono para este cliente. El sistema tomará automaticamente 2 colores principales desde la imagen y podrás ajustarlos manualmente si hace falta.
        </p>
      </div>

      <div className="rounded-lg border border-ink-200 p-6 bg-ink-50">
        <div className="flex flex-col md:flex-row md:items-center gap-6">
          <div className="flex items-center gap-3">
            <div className="flex h-16 w-16 items-center justify-center rounded-lg border border-ink-200 bg-white overflow-hidden">
              {brandingIconUrl ? (
                // eslint-disable-next-line @next/next/no-img-element -- URL dinámica (firmada, dominio de storage no allowlisteado en next.config.js)
                <img src={brandingIconUrl} alt="Icono del cliente" className="h-14 w-14 object-contain" />
              ) : (
                <span className="text-xs text-ink-400 text-center px-2">Sin icono</span>
              )}
            </div>
            <div className="flex items-center gap-3">
              <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-white border border-ink-200">
                <Image src="/margay-logo.png" alt="Logo de Process AI" width={40} height={40} className="h-10 w-10 object-contain" />
              </div>
              <span
                className="text-xl font-bold"
                style={
                  brandingPrimaryColor === brandingSecondaryColor
                    ? { color: brandingPrimaryColor }
                    : {
                        backgroundImage: `linear-gradient(90deg, ${brandingPrimaryColor}, ${brandingSecondaryColor})`,
                        WebkitBackgroundClip: 'text',
                        backgroundClip: 'text',
                        color: 'transparent',
                      }
                }
              >
                Process AI
              </span>
            </div>
          </div>

          <div className="space-y-4">
            <label className="inline-flex items-center px-4 py-2 bg-action hover:bg-action-hover text-white font-medium rounded-md cursor-pointer disabled:opacity-50">
              <input
                type="file"
                accept=".png,.jpg,.jpeg,.webp,.svg,image/png,image/jpeg,image/webp,image/svg+xml"
                className="sr-only"
                onChange={onFileChange}
                disabled={brandingSaving}
              />
              {brandingSaving ? 'Guardando...' : 'Cargar icono'}
            </label>
            {brandingIconUrl && (
              <button
                type="button"
                onClick={onDeleteIcon}
                className="block px-4 py-2 border border-ink-300 rounded-md text-sm font-medium text-ink-700 hover:bg-ink-100 disabled:opacity-50"
                disabled={brandingSaving}
              >
                Quitar icono
              </button>
            )}
            <p className="text-xs text-ink-500">
              Formatos permitidos: PNG, JPG, WEBP o SVG. Tamaño máximo: 2 MB.
            </p>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2">
              <label className="block">
                <span className="block text-sm font-medium text-ink-700 mb-2">Color principal</span>
                <div className="flex items-center gap-3">
                  <input
                    type="color"
                    value={brandingPrimaryColor}
                    onChange={(e) => onPrimaryColorChange(e.target.value.toUpperCase())}
                    className="h-11 w-14 rounded border border-ink-300 bg-white p-1"
                    disabled={brandingSaving}
                  />
                  <span className="text-sm font-mono text-ink-600">{brandingPrimaryColor}</span>
                </div>
              </label>

              <label className="block">
                <span className="block text-sm font-medium text-ink-700 mb-2">Color secundario</span>
                <div className="flex items-center gap-3">
                  <input
                    type="color"
                    value={brandingSecondaryColor}
                    onChange={(e) => onSecondaryColorChange(e.target.value.toUpperCase())}
                    className="h-11 w-14 rounded border border-ink-300 bg-white p-1"
                    disabled={brandingSaving}
                  />
                  <span className="text-sm font-mono text-ink-600">{brandingSecondaryColor}</span>
                </div>
              </label>
            </div>

            <button
              type="button"
              onClick={onSaveColors}
              className="inline-flex items-center px-4 py-2 rounded-md text-white font-medium disabled:opacity-50"
              style={{ backgroundColor: brandingPrimaryColor }}
              disabled={brandingSaving}
            >
              {brandingSaving ? 'Guardando...' : 'Guardar colores'}
            </button>
          </div>
        </div>

        {brandingMessage && (
          <p
            className={`mt-4 text-sm ${
              brandingMessage.includes('correctamente') ? 'text-success-fg' : 'text-danger'
            }`}
          >
            {brandingMessage}
          </p>
        )}
      </div>
    </div>
  )
}
