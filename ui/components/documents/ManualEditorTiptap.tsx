'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { useEditor, EditorContent } from '@tiptap/react'
import StarterKit from '@tiptap/starter-kit'
import Link from '@tiptap/extension-link'
import Image from '@tiptap/extension-image'
import Placeholder from '@tiptap/extension-placeholder'
import Table from '@tiptap/extension-table'
import TableRow from '@tiptap/extension-table-row'
import TableHeader from '@tiptap/extension-table-header'
import TableCell from '@tiptap/extension-table-cell'
import { uploadEditorImage } from '@/lib/api'

export interface ManualEditorTiptapRef {
  getHtml: () => string
}

interface ManualEditorTiptapProps {
  documentId: string
  initialHtml: string
  onSave: (html: string) => void
  onDirtyChange?: (dirty: boolean) => void
  readOnly?: boolean
  saving?: boolean
  className?: string
  editorRef?: React.MutableRefObject<ManualEditorTiptapRef | null>
}

/** Devuelve true si el texto contiene tags HTML de bloque/inline. HTML de Tiptap siempre los tiene. */
const HTML_BLOCK_RE = /<(?:h[1-6]|p|ul|ol|li|strong|em|b|i|table|img|div|span|a|br|hr|blockquote|pre|code)\b/i

function isHtml(text: string): boolean {
  return HTML_BLOCK_RE.test(text)
}

/** True si el texto parece markdown crudo (sin ningún tag HTML). */
function looksLikeMarkdown(text: string): boolean {
  return !isHtml(text)
}

export default function ManualEditorTiptap({
  documentId,
  initialHtml,
  onSave,
  onDirtyChange,
  readOnly = false,
  saving = false,
  className = '',
  editorRef,
}: ManualEditorTiptapProps) {
  const [imageError, setImageError] = useState<string | null>(null)
  const [saveWarning, setSaveWarning] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const lastInitialHtmlRef = useRef<string>('')

  const editor = useEditor({
    extensions: [
      StarterKit.configure({ heading: { levels: [1, 2, 3, 4] } }),
      Link.configure({ openOnClick: false, HTMLAttributes: { rel: 'noopener' } }),
      Image.configure({ inline: false, allowBase64: false }),
      Placeholder.configure({ placeholder: 'Escribí o pegá contenido aquí...' }),
      Table.configure({ resizable: true }),
      TableRow,
      TableHeader,
      TableCell,
    ],
    content: initialHtml,
    editable: !readOnly,
    editorProps: {
      handlePaste: (view, event) => {
        const items = event.clipboardData?.items
        if (!items) return false
        for (const item of items) {
          if (item.type.indexOf('image') !== -1) {
            const file = item.getAsFile()
            if (file) {
              event.preventDefault()
              handleImageFile(file)
              return true
            }
          }
        }
        return false
      },
      handleDrop: (view, event) => {
        const files = event.dataTransfer?.files
        if (!files?.length) return false
        const file = files[0]
        if (file.type.startsWith('image/')) {
          event.preventDefault()
          handleImageFile(file)
          return true
        }
        return false
      },
    },
  })

  useEffect(() => {
    if (!editorRef || !editor) return
    editorRef.current = { getHtml: () => editor.getHTML() }
    return () => {
      if (editorRef) editorRef.current = null
    }
  }, [editor, editorRef])

  // Sync initialHtml into the editor when it changes asynchronously (e.g. after API fetch)
  useEffect(() => {
    if (!editor || !initialHtml) return
    if (initialHtml === lastInitialHtmlRef.current) return
    const prev = lastInitialHtmlRef.current
    lastInitialHtmlRef.current = initialHtml
    // If editor still holds the previous initial value (no user edits yet), update it
    const current = editor.getHTML()
    if (current === '' || current === '<p></p>' || current === prev) {
      editor.commands.setContent(initialHtml, false)
    }
  }, [editor, initialHtml])

  const handleImageFile = useCallback(
    async (file: File) => {
      setImageError(null)
      try {
        const { url } = await uploadEditorImage(documentId, file)
        editor?.chain().focus().setImage({ src: url }).run()
      } catch (e) {
        setImageError(e instanceof Error ? e.message : 'Error al subir la imagen')
      }
    },
    [documentId, editor]
  )

  useEffect(() => {
    editor?.setEditable(!readOnly)
  }, [editor, readOnly])

  const handleSave = useCallback(() => {
    setSaveWarning(null)
    const html = editor?.getHTML() ?? ''
    if (looksLikeMarkdown(html)) {
      setSaveWarning('El contenido parece markdown crudo, no HTML. No se puede guardar. Revisá el editor.')
      console.warn('[ManualEditorTiptap] handleSave: contenido parece markdown, no se envía al backend.', html.slice(0, 200))
      return
    }
    onSave(html)
  }, [editor, onSave])

  useEffect(() => {
    if (!editor || !onDirtyChange) return
    const onUpdate = () => {
      const current = editor.getHTML()
      onDirtyChange(current !== initialHtml)
    }
    editor.on('update', onUpdate)
    return () => editor.off('update', onUpdate)
  }, [editor, initialHtml, onDirtyChange])

  const addImage = () => {
    setImageError(null)
    fileInputRef.current?.click()
  }

  const setLink = () => {
    const previousUrl = editor?.getAttributes('link').href
    const url = window.prompt('URL del enlace', previousUrl)
    if (url === null) return
    if (url === '') {
      editor?.chain().focus().extendMarkRange('link').unsetLink().run()
      return
    }
    editor?.chain().focus().extendMarkRange('link').setLink({ href: url }).run()
  }

  if (!editor) {
    return (
      <div className="animate-pulse rounded-lg bg-gray-100 h-64 flex items-center justify-center text-gray-500">
        Cargando editor...
      </div>
    )
  }

  const ToolbarButton = ({
    onClick,
    active,
    disabled,
    children,
    title,
  }: {
    onClick: () => void
    active?: boolean
    disabled?: boolean
    children: React.ReactNode
    title: string
  }) => (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      title={title}
      className={`p-2 rounded hover:bg-gray-200 disabled:opacity-50 ${active ? 'bg-gray-300' : ''}`}
    >
      {children}
    </button>
  )

  return (
    <div className={className}>
      {!readOnly && (
        <div className="flex flex-wrap items-center gap-1 p-2 border border-gray-200 rounded-t-lg bg-gray-50 border-b-0">
          <ToolbarButton
            onClick={() => editor.chain().focus().toggleHeading({ level: 1 }).run()}
            active={editor.isActive('heading', { level: 1 })}
            title="Título 1"
          >
            H1
          </ToolbarButton>
          <ToolbarButton
            onClick={() => editor.chain().focus().toggleHeading({ level: 2 }).run()}
            active={editor.isActive('heading', { level: 2 })}
            title="Título 2"
          >
            H2
          </ToolbarButton>
          <ToolbarButton
            onClick={() => editor.chain().focus().toggleHeading({ level: 3 }).run()}
            active={editor.isActive('heading', { level: 3 })}
            title="Título 3"
          >
            H3
          </ToolbarButton>
          <span className="w-px h-6 bg-gray-300 mx-1" />
          <ToolbarButton
            onClick={() => editor.chain().focus().toggleBold().run()}
            active={editor.isActive('bold')}
            title="Negrita"
          >
            <strong>B</strong>
          </ToolbarButton>
          <ToolbarButton
            onClick={() => editor.chain().focus().toggleItalic().run()}
            active={editor.isActive('italic')}
            title="Cursiva"
          >
            <em>I</em>
          </ToolbarButton>
          <span className="w-px h-6 bg-gray-300 mx-1" />
          <ToolbarButton
            onClick={() => editor.chain().focus().toggleBulletList().run()}
            active={editor.isActive('bulletList')}
            title="Lista con viñetas"
          >
            •
          </ToolbarButton>
          <ToolbarButton
            onClick={() => editor.chain().focus().toggleOrderedList().run()}
            active={editor.isActive('orderedList')}
            title="Lista numerada"
          >
            1.
          </ToolbarButton>
          <ToolbarButton onClick={setLink} active={editor.isActive('link')} title="Enlace">
            🔗
          </ToolbarButton>
          <ToolbarButton onClick={addImage} title="Insertar imagen">
            🖼️
          </ToolbarButton>
          <ToolbarButton
            onClick={() => editor.chain().focus().insertTable({ rows: 3, cols: 3, withHeaderRow: true }).run()}
            title="Insertar tabla"
          >
            ⊞
          </ToolbarButton>
          <span className="w-px h-6 bg-gray-300 mx-1" />
          <ToolbarButton onClick={() => editor.chain().focus().undo().run()} disabled={!editor.can().undo()} title="Deshacer">
            ↩
          </ToolbarButton>
          <ToolbarButton onClick={() => editor.chain().focus().redo().run()} disabled={!editor.can().redo()} title="Rehacer">
            ↪
          </ToolbarButton>
        </div>
      )}

      <input
        ref={fileInputRef}
        type="file"
        accept="image/*"
        className="hidden"
        onChange={(e) => {
          const f = e.target.files?.[0]
          if (f) handleImageFile(f)
          e.target.value = ''
        }}
      />

      <div className="bg-white border border-gray-200 rounded-b-lg shadow-sm overflow-hidden">
        {/* Paper mode: ancho tipo A4, padding */}
        <div className="max-w-[210mm] mx-auto min-h-[297mm] py-10 px-12 text-gray-900">
          <EditorContent editor={editor} />
        </div>
      </div>

      {/* Estilos mínimos para el contenido del editor (prose) */}
      <style jsx global>{`
        .ProseMirror {
          outline: none;
          min-height: 200px;
        }
        .ProseMirror p { margin-bottom: 0.75em; }
        .ProseMirror h1 { font-size: 2rem; font-weight: 800; margin-top: 1.5em; margin-bottom: 0.5em; }
        .ProseMirror h2 { font-size: 1.5rem; font-weight: 700; margin-top: 1.5em; margin-bottom: 0.5em; }
        .ProseMirror h3 { font-size: 1.25rem; font-weight: 600; margin-top: 1.25em; margin-bottom: 0.5em; }
        .ProseMirror h4 { font-size: 1.1rem; font-weight: 600; margin-top: 1em; margin-bottom: 0.4em; }
        .ProseMirror ul { list-style-type: disc; padding-left: 1.5rem; margin-bottom: 0.75em; }
        .ProseMirror ol { list-style-type: decimal; padding-left: 1.5rem; margin-bottom: 0.75em; }
        .ProseMirror a { color: #2563eb; text-decoration: underline; }
        .ProseMirror img { max-width: 100%; height: auto; border-radius: 4px; }
        .ProseMirror table { border-collapse: collapse; width: 100%; margin: 1em 0; }
        .ProseMirror th, .ProseMirror td { border: 1px solid #e5e7eb; padding: 8px 12px; text-align: left; }
        .ProseMirror th { background: #f3f4f6; font-weight: 600; }
        .ProseMirror .is-empty::before { content: attr(data-placeholder); color: #9ca3af; float: left; pointer-events: none; }
      `}</style>

      {imageError && (
        <p className="mt-2 text-sm text-red-600" role="alert">
          {imageError}
        </p>
      )}

      {saveWarning && (
        <p className="mt-2 text-sm text-red-600 font-medium" role="alert">
          ⚠️ {saveWarning}
        </p>
      )}

      {!readOnly && (
        <div className="mt-4 flex items-center gap-3">
          <button
            type="button"
            onClick={handleSave}
            disabled={saving}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed font-medium inline-flex items-center gap-2"
          >
            {saving && (
              <svg className="animate-spin h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" aria-hidden="true">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
              </svg>
            )}
            {saving ? 'Guardando...' : 'Guardar borrador'}
          </button>
        </div>
      )}
    </div>
  )
}
