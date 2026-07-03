'use client'

import { useState, useEffect, useRef, useMemo } from 'react'
import { useRouter } from 'next/navigation'
import { Check, X, ChevronDown, Globe } from 'lucide-react'
import { Card, CardBody, Input, Field, Button } from '@/shared/ui/components'
import { cn } from '@/shared/ui/cn'
import { getUser, updateMyProfile, type UserProfile } from '@/lib/api'
import { useUserId } from '@/hooks/useUserId'
import { useLoading } from '@/contexts/LoadingContext'
import { formatDateTime } from '@/utils/dateFormat'
import { redirectToHubLogin } from '@/lib/hub-login'

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
      <div className="flex min-h-[70vh] items-center justify-center p-6">
        <div className="text-center">
          <p className="text-ink-600">Iniciá sesión para ver tu perfil.</p>
          <Button className="mt-4" onClick={() => redirectToHubLogin()}>
            Ir a inicio de sesión
          </Button>
        </div>
      </div>
    )
  }

  if (loading) {
    return (
      <div className="p-8">
        <div className="mx-auto max-w-3xl">
          <div className="animate-pulse text-ink-500">Cargando perfil...</div>
        </div>
      </div>
    )
  }

  return (
    <div className="p-8">
      <div className="mx-auto max-w-3xl">
        <div className="mb-8">
          <h1 className="text-h1 text-ink-900">Mi perfil</h1>
          <p className="mt-2 text-sm text-ink-500">
            Datos de tu cuenta y teléfono de contacto
          </p>
        </div>

        {error && (
          <div className="mb-4 rounded-md border border-danger-bd bg-danger-bg px-4 py-3 text-sm text-danger" role="alert">
            {error}
          </div>
        )}

        {successMessage && (
          <div className="mb-4 rounded-md border border-success-bd bg-success-bg px-4 py-3 text-sm text-success-fg" role="status">
            {successMessage}
          </div>
        )}

        <Card>
          <CardBody>
            <form onSubmit={handleSubmit} className="space-y-6">
              <Field label="Nombre">
                <Input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Tu nombre"
                />
              </Field>

              <div>
                <Field label="Email">
                  <Input type="text" value={profile?.email ?? ''} disabled className="bg-ink-50 text-ink-500" />
                </Field>
                <p className="mt-1 text-xs text-ink-500">El email no se puede cambiar desde aquí.</p>
              </div>

              <div>
                <label className="mb-1 block text-sm font-semibold text-ink-700">Teléfono</label>
                <div className="flex items-center gap-2">
                  <div className="relative w-52 flex-shrink-0" ref={countryPickerRef}>
                    <button
                      type="button"
                      onClick={() => setCountryPickerOpen((o) => !o)}
                      className="flex w-full items-center gap-2 rounded-md border border-ink-300 bg-white px-3 py-2 text-left focus:border-action focus:outline-none focus:ring-[3px] focus:ring-action-ring"
                      aria-haspopup="listbox"
                      aria-expanded={countryPickerOpen}
                      aria-label="Código de país"
                    >
                      <span className="flex h-[15px] w-5 flex-shrink-0 items-center justify-center overflow-hidden rounded-sm bg-ink-100" aria-hidden>
                        {currentCountryOption?.isExtra ? (
                          <Globe className="h-3.5 w-3.5 text-ink-500" />
                        ) : currentCountryOption?.iso ? (
                          <FlagImage iso={currentCountryOption.iso} className="h-[15px] w-5 object-cover" />
                        ) : (
                          <Globe className="h-3.5 w-3.5 text-ink-500" />
                        )}
                      </span>
                      <span className="min-w-0 flex-1 truncate text-sm text-ink-800">
                        {currentCountryOption?.label ?? phonePrefix}
                      </span>
                      <ChevronDown className="h-4 w-4 flex-shrink-0 text-ink-500" />
                    </button>
                    {countryPickerOpen && (
                      <ul
                        className="absolute z-10 mt-1 max-h-60 w-full overflow-auto rounded-md border border-ink-200 bg-white py-1 shadow-md"
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
                            className="flex cursor-pointer items-center gap-2 px-3 py-2 text-sm text-ink-700 hover:bg-ink-100 aria-selected:bg-accent-tint aria-selected:text-accent-ink"
                          >
                            <span className="flex h-[15px] w-5 flex-shrink-0 items-center justify-center overflow-hidden rounded-sm bg-ink-100" aria-hidden>
                              <FlagImage iso={opt.iso} className="h-[15px] w-5 object-cover" />
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
                            className="flex cursor-pointer items-center gap-2 px-3 py-2 text-sm text-ink-700 hover:bg-ink-100 aria-selected:bg-accent-tint aria-selected:text-accent-ink"
                          >
                            <span className="flex h-[15px] w-5 flex-shrink-0 items-center justify-center text-ink-500" aria-hidden>
                              <Globe className="h-3.5 w-3.5" />
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
                    className="min-w-0 flex-1 rounded-md border border-ink-300 bg-white px-3 py-2 text-body text-ink-800 placeholder:text-ink-500 focus:border-action focus:outline-none focus:ring-[3px] focus:ring-action-ring"
                    placeholder="91234567"
                    aria-label="Número de teléfono"
                  />
                  {fullPhoneE164 || profile?.phone_e164 ? (
                    profile?.phone_verified ? (
                      <span className="flex-shrink-0 text-success" title="Verificado" aria-label="Verificado">
                        <Check className="h-6 w-6" />
                      </span>
                    ) : (
                      <span className="flex-shrink-0 text-danger" title="No verificado" aria-label="No verificado">
                        <X className="h-6 w-6" />
                      </span>
                    )
                  ) : null}
                </div>
                <p className="mt-1 text-xs text-ink-500">
                  Primero elegí el país, luego el número sin el 0 ni la característica.
                </p>
                {(phoneNumber.length >= 6 || profile?.phone_e164) && (
                  <div className="mt-3">
                    <Button
                      type="button"
                      variant="secondary"
                      size="sm"
                      disabled={phoneNumber.length < 6}
                      onClick={() => {
                        const num = fullPhoneE164 || profile?.phone_e164 || ''
                        setVerificationMessage(`Se envió un código de verificación al número: ${num}`)
                      }}
                    >
                      Verificar
                    </Button>
                  </div>
                )}
                {profile?.phone_e164 && profile?.phone_verified_at && (
                  <p className="mt-1 text-xs text-ink-500">
                    Verificado el {formatDateTime(profile.phone_verified_at)}
                  </p>
                )}
              </div>

              <div className="flex justify-end">
                <Button type="submit" disabled={saving}>
                  {saving ? 'Guardando...' : 'Guardar'}
                </Button>
              </div>
            </form>
          </CardBody>
        </Card>
      </div>

      {/* Pop-up de verificación enviada */}
      {verificationMessage && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-4"
          role="dialog"
          aria-modal="true"
          aria-labelledby="verification-toast-title"
        >
          <div className="flex w-full max-w-sm items-start gap-4 rounded-xl bg-white p-6 shadow-lg">
            <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-full bg-success-bg">
              <Check className="h-5 w-5 text-success" />
            </div>
            <div className="min-w-0 flex-1">
              <h3 id="verification-toast-title" className="mb-1 text-sm font-semibold text-ink-900">
                Código enviado
              </h3>
              <p className="text-sm text-ink-600">{verificationMessage}</p>
            </div>
            <button
              type="button"
              onClick={() => setVerificationMessage(null)}
              className="flex-shrink-0 rounded-md p-1 text-ink-400 hover:bg-ink-100 hover:text-ink-600"
              aria-label="Cerrar"
            >
              <X className="h-5 w-5" />
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
