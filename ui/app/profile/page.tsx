'use client'

import { useState, useEffect, useRef, useMemo } from 'react'
import { useRouter } from 'next/navigation'
import { getUser, updateMyProfile, type UserProfile } from '@/lib/api'
import { useUserId } from '@/hooks/useUserId'
import { useLoading } from '@/contexts/LoadingContext'
import { formatDateTime } from '@/utils/dateFormat'

const PHONE_COUNTRY_OPTIONS: { code: string; label: string; iso: string }[] = [
  { code: '+598', label: 'Uruguay (+598)', iso: 'UY' },
  { code: '+54', label: 'Argentina (+54)', iso: 'AR' },
  { code: '+55', label: 'Brasil (+55)', iso: 'BR' },
  { code: '+52', label: 'México (+52)', iso: 'MX' },
  { code: '+57', label: 'Colombia (+57)', iso: 'CO' },
  { code: '+56', label: 'Chile (+56)', iso: 'CL' },
  { code: '+51', label: 'Perú (+51)', iso: 'PE' },
  { code: '+34', label: 'España (+34)', iso: 'ES' },
  { code: '+1', label: 'EE.UU. / Canadá (+1)', iso: 'US' },
  { code: '+49', label: 'Alemania (+49)', iso: 'DE' },
  { code: '+33', label: 'Francia (+33)', iso: 'FR' },
  { code: '+39', label: 'Italia (+39)', iso: 'IT' },
]

const FLAG_CDN = 'https://flagcdn.com'

/** Banderas como imagen desde CDN (se ve en todos los navegadores). */
function FlagImage({ iso, className }: { iso: string; className?: string }) {
  if (!iso || iso.length !== 2) return null
  const code = iso.toLowerCase()
  return (
    <img
      src={`${FLAG_CDN}/w40/${code}.png`}
      srcSet={`${FLAG_CDN}/w80/${code}.png 2x`}
      alt=""
      width={20}
      height={15}
      className={className}
      loading="lazy"
    />
  )
}

/** Ícono de globo para "otro" país. */
function GlobeIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden>
      <circle cx="12" cy="12" r="10" />
      <path d="M2 12h20M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
    </svg>
  )
}

function parsePhoneE164(value: string | null | undefined): { prefix: string; number: string } {
  const raw = (value || '').replace(/\s/g, '')
  if (!raw.startsWith('+') || raw.length < 4) return { prefix: '+598', number: '' }
  const digitsAfterPlus = raw.slice(1).replace(/\D/g, '')
  const sortedCodes = [...PHONE_COUNTRY_OPTIONS].sort((a, b) => b.code.length - a.code.length)
  for (const { code } of sortedCodes) {
    const codeDigits = code.slice(1)
    if (digitsAfterPlus.startsWith(codeDigits)) {
      const number = digitsAfterPlus.slice(codeDigits.length)
      return { prefix: code, number }
    }
  }
  if (digitsAfterPlus.startsWith('1') && digitsAfterPlus.length >= 10) {
    return { prefix: '+1', number: digitsAfterPlus.slice(1) }
  }
  const len = digitsAfterPlus.length >= 3 ? 3 : digitsAfterPlus.length >= 2 ? 2 : 1
  const prefix = '+' + digitsAfterPlus.slice(0, len)
  const number = digitsAfterPlus.slice(len)
  return { prefix, number }
}

function buildPhoneE164(prefix: string, number: string): string {
  const digits = (number || '').replace(/\D/g, '')
  if (!prefix || !digits) return ''
  const prefixNorm = prefix.startsWith('+') ? prefix : '+' + prefix
  return prefixNorm + digits
}

export default function ProfilePage() {
  const router = useRouter()
  const userId = useUserId()
  const { withLoading } = useLoading()
  const [profile, setProfile] = useState<UserProfile | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [successMessage, setSuccessMessage] = useState<string | null>(null)

  const [name, setName] = useState('')
  const [phonePrefix, setPhonePrefix] = useState('+598')
  const [phoneNumber, setPhoneNumber] = useState('')
  const [extraCountryOption, setExtraCountryOption] = useState<{ code: string; label: string } | null>(null)
  const [countryPickerOpen, setCountryPickerOpen] = useState(false)
  const countryPickerRef = useRef<HTMLDivElement>(null)
  const [verificationMessage, setVerificationMessage] = useState<string | null>(null)
  const verificationTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const fullPhoneE164 = useMemo(
    () => buildPhoneE164(phonePrefix, phoneNumber),
    [phonePrefix, phoneNumber]
  )

  const currentCountryOption = useMemo(() => {
    const found = PHONE_COUNTRY_OPTIONS.find((o) => o.code === phonePrefix)
    if (found) return { ...found, isExtra: false }
    if (extraCountryOption && extraCountryOption.code === phonePrefix) {
      return { code: extraCountryOption.code, label: extraCountryOption.label, iso: '', isExtra: true }
    }
    return null
  }, [phonePrefix, extraCountryOption])

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (countryPickerRef.current && !countryPickerRef.current.contains(e.target as Node)) {
        setCountryPickerOpen(false)
      }
    }
    if (countryPickerOpen) document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [countryPickerOpen])

  useEffect(() => {
    if (!verificationMessage) return
    verificationTimeoutRef.current = setTimeout(() => {
      setVerificationMessage(null)
    }, 3000)
    return () => {
      if (verificationTimeoutRef.current) {
        clearTimeout(verificationTimeoutRef.current)
        verificationTimeoutRef.current = null
      }
    }
  }, [verificationMessage])

  useEffect(() => {
    if (!userId) {
      setLoading(false)
      return
    }
    let cancelled = false
    getUser(userId)
      .then((data) => {
        if (!cancelled) {
          setProfile(data)
          setName(data.name ?? '')
          const parsed = parsePhoneE164(data.phone_e164 ?? '')
          setPhonePrefix(parsed.prefix)
          setPhoneNumber(parsed.number)
          const inList = PHONE_COUNTRY_OPTIONS.some((o) => o.code === parsed.prefix)
          if (parsed.prefix && !inList) {
            setExtraCountryOption({ code: parsed.prefix, label: `${parsed.prefix} (otro)` })
          } else {
            setExtraCountryOption(null)
          }
        }
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : 'Error al cargar perfil')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => { cancelled = true }
  }, [userId])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!userId) return

    const trimmedName = name.trim()
    const newPhone = fullPhoneE164 || null
    const savedName = profile?.name ?? ''
    const savedPhone = profile?.phone_e164 ?? null

    const nameChanged = trimmedName !== savedName
    const phoneChanged = newPhone !== savedPhone

    if (!nameChanged && !phoneChanged) {
      setError('No hay cambios para guardar')
      return
    }

    if (nameChanged && !trimmedName) {
      setError('El nombre es obligatorio')
      return
    }

    if (phoneChanged && phoneNumber && phoneNumber.length < 6) {
      setError('El número de teléfono es demasiado corto (mínimo 6 dígitos)')
      return
    }

    const payload: { name?: string; phone_e164?: string | null } = {}
    if (nameChanged) payload.name = trimmedName
    if (phoneChanged) payload.phone_e164 = newPhone

    await withLoading(async () => {
      try {
        setSaving(true)
        setError(null)
        setSuccessMessage(null)
        const updated = await updateMyProfile(userId, payload)
        setProfile(updated)
        setSuccessMessage('Datos guardados correctamente')
        setTimeout(() => setSuccessMessage(null), 3000)
        if (typeof window !== 'undefined') {
          window.dispatchEvent(new CustomEvent('profileUpdated'))
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Error al guardar')
      } finally {
        setSaving(false)
      }
    })
  }

  if (!userId) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <p className="text-gray-600">Iniciá sesión para ver tu perfil.</p>
          <button
            onClick={() => router.push('/login')}
            className="mt-4 px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
          >
            Ir a inicio de sesión
          </button>
        </div>
      </div>
    )
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 py-8 px-4 sm:px-6 lg:px-8">
        <div className="max-w-7xl mx-auto">
          <div className="animate-pulse text-gray-500">Cargando perfil...</div>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-50 py-8 px-4 sm:px-6 lg:px-8">
      <div className="max-w-7xl mx-auto">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900">Mi perfil</h1>
          <p className="mt-2 text-sm text-gray-600">
            Datos de tu cuenta y teléfono de contacto
          </p>
        </div>

        {error && (
          <div className="mb-4 bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded relative" role="alert">
            <span className="block sm:inline">{error}</span>
          </div>
        )}

        {successMessage && (
          <div className="mb-4 bg-green-100 border border-green-400 text-green-700 px-4 py-3 rounded relative" role="status">
            <span className="block sm:inline">{successMessage}</span>
          </div>
        )}

        <div className="bg-white shadow rounded-lg">
          <div className="p-6">
            <form onSubmit={handleSubmit} className="space-y-6">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Nombre
                </label>
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-blue-500 focus:border-blue-500"
                  placeholder="Tu nombre"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Email
                </label>
                <input
                  type="text"
                  value={profile?.email ?? ''}
                  disabled
                  className="w-full px-3 py-2 border border-gray-200 rounded-md bg-gray-50 text-gray-500 cursor-not-allowed"
                />
                <p className="mt-1 text-xs text-gray-500">
                  El email no se puede cambiar desde aquí.
                </p>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Teléfono
                </label>
                <div className="flex items-center gap-2">
                  <div className="relative w-52 flex-shrink-0" ref={countryPickerRef}>
                    <button
                      type="button"
                      onClick={() => setCountryPickerOpen((o) => !o)}
                      className="w-full flex items-center gap-2 px-3 py-2 border border-gray-300 rounded-md bg-white text-left focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                      aria-haspopup="listbox"
                      aria-expanded={countryPickerOpen}
                      aria-label="Código de país"
                    >
                      <span className="flex-shrink-0 w-5 h-[15px] flex items-center justify-center overflow-hidden rounded-sm bg-gray-100" aria-hidden>
                        {currentCountryOption?.isExtra ? (
                          <GlobeIcon className="w-3.5 h-3.5 text-gray-500" />
                        ) : currentCountryOption?.iso ? (
                          <FlagImage iso={currentCountryOption.iso} className="w-5 h-[15px] object-cover" />
                        ) : (
                          <GlobeIcon className="w-3.5 h-3.5 text-gray-500" />
                        )}
                      </span>
                      <span className="flex-1 min-w-0 truncate text-sm">
                        {currentCountryOption?.label ?? phonePrefix}
                      </span>
                      <svg className="w-4 h-4 flex-shrink-0 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 9l-7 7-7-7" />
                      </svg>
                    </button>
                    {countryPickerOpen && (
                      <ul
                        className="absolute z-10 mt-1 w-full max-h-60 overflow-auto rounded-md border border-gray-200 bg-white py-1 shadow-lg"
                        role="listbox"
                      >
                        {PHONE_COUNTRY_OPTIONS.map((opt) => (
                          <li
                            key={opt.code}
                            role="option"
                            aria-selected={phonePrefix === opt.code}
                            onClick={() => {
                              setPhonePrefix(opt.code)
                              setVerificationMessage(null)
                              setCountryPickerOpen(false)
                            }}
                            className="flex items-center gap-2 px-3 py-2 text-sm cursor-pointer hover:bg-gray-100 aria-selected:bg-blue-50 aria-selected:text-blue-700"
                          >
                            <span className="flex-shrink-0 w-5 h-[15px] flex items-center justify-center overflow-hidden rounded-sm bg-gray-100" aria-hidden>
                              <FlagImage iso={opt.iso} className="w-5 h-[15px] object-cover" />
                            </span>
                            <span>{opt.label}</span>
                          </li>
                        ))}
                        {extraCountryOption && (
                          <li
                            role="option"
                            aria-selected={phonePrefix === extraCountryOption.code}
                            onClick={() => {
                              setPhonePrefix(extraCountryOption.code)
                              setVerificationMessage(null)
                              setCountryPickerOpen(false)
                            }}
                            className="flex items-center gap-2 px-3 py-2 text-sm cursor-pointer hover:bg-gray-100 aria-selected:bg-blue-50 aria-selected:text-blue-700"
                          >
                            <span className="flex-shrink-0 w-5 h-[15px] flex items-center justify-center text-gray-500" aria-hidden>
                              <GlobeIcon className="w-3.5 h-3.5" />
                            </span>
                            <span>{extraCountryOption.label}</span>
                          </li>
                        )}
                      </ul>
                    )}
                  </div>
                  <input
                    type="tel"
                    value={phoneNumber}
                    onChange={(e) => {
                      setPhoneNumber(e.target.value.replace(/\D/g, '').slice(0, 15))
                      setVerificationMessage(null)
                    }}
                    className="flex-1 min-w-0 px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-blue-500 focus:border-blue-500"
                    placeholder="91234567"
                    aria-label="Número de teléfono"
                  />
                  {fullPhoneE164 || profile?.phone_e164 ? (
                    profile?.phone_verified ? (
                      <span className="flex-shrink-0 text-green-600" title="Verificado" aria-label="Verificado">
                        <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2">
                          <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                        </svg>
                      </span>
                    ) : (
                      <span className="flex-shrink-0 text-red-500" title="No verificado" aria-label="No verificado">
                        <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2">
                          <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                        </svg>
                      </span>
                    )
                  ) : null}
                </div>
                <p className="mt-1 text-xs text-gray-500">
                  Primero elegí el país, luego el número sin el 0 ni la característica.
                </p>
                {(phoneNumber.length >= 6 || profile?.phone_e164) && (
                  <div className="mt-3">
                    <button
                      type="button"
                      disabled={phoneNumber.length < 6}
                      onClick={() => {
                        const num = fullPhoneE164 || profile?.phone_e164 || ''
                        setVerificationMessage(`Se envió un código de verificación al número: ${num}`)
                      }}
                      className={`px-4 py-2 border rounded-md text-sm font-medium ${phoneNumber.length < 6 ? 'border-gray-200 text-gray-400 cursor-not-allowed' : 'border-gray-300 text-gray-700 hover:bg-gray-50'}`}
                    >
                      Verificar
                    </button>
                  </div>
                )}
                {profile?.phone_e164 && profile?.phone_verified_at && (
                  <p className="mt-1 text-xs text-gray-500">
                    Verificado el {formatDateTime(profile.phone_verified_at)}
                  </p>
                )}
              </div>

              <div className="flex justify-end">
                <button
                  type="submit"
                  disabled={saving}
                  className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed font-medium"
                >
                  {saving ? 'Guardando...' : 'Guardar'}
                </button>
              </div>
            </form>
          </div>
        </div>
      </div>

      {/* Pop-up de verificación enviada */}
      {verificationMessage && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/30"
          role="dialog"
          aria-modal="true"
          aria-labelledby="verification-toast-title"
        >
          <div className="bg-white rounded-xl shadow-xl max-w-sm w-full p-6 flex items-start gap-4">
            <div className="flex-shrink-0 w-10 h-10 rounded-full bg-green-100 flex items-center justify-center">
              <svg className="w-5 h-5 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2">
                <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
              </svg>
            </div>
            <div className="flex-1 min-w-0">
              <h3 id="verification-toast-title" className="text-sm font-semibold text-gray-900 mb-1">
                Código enviado
              </h3>
              <p className="text-sm text-gray-600">
                {verificationMessage}
              </p>
            </div>
            <button
              type="button"
              onClick={() => setVerificationMessage(null)}
              className="flex-shrink-0 p-1 rounded-md text-gray-400 hover:text-gray-600 hover:bg-gray-100"
              aria-label="Cerrar"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
