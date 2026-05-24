import { useEffect, useId, useRef, useState } from 'react'
import { HelpCircle } from 'lucide-react'
import type { SchemaPayload } from './types'

interface FieldTooltipProps {
  recordType: string
  fieldName: string
  schema: SchemaPayload
  children: React.ReactNode
}

export default function FieldTooltip({
  recordType,
  fieldName,
  schema,
  children,
}: FieldTooltipProps) {
  const [open, setOpen] = useState(false)
  const tooltipId = useId()
  const containerRef = useRef<HTMLSpanElement>(null)
  const doc = schema.records[recordType]?.[fieldName]

  useEffect(() => {
    if (!open) return
    const handleKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setOpen(false)
    }
    const handleClick = (event: MouseEvent) => {
      if (
        containerRef.current &&
        !containerRef.current.contains(event.target as Node)
      ) {
        setOpen(false)
      }
    }
    document.addEventListener('keydown', handleKey)
    document.addEventListener('mousedown', handleClick)
    return () => {
      document.removeEventListener('keydown', handleKey)
      document.removeEventListener('mousedown', handleClick)
    }
  }, [open])

  if (!doc) {
    return <span className="field-label">{children}</span>
  }

  return (
    <span className="field-tooltip-wrap" ref={containerRef}>
      <span className="field-label">{children}</span>
      <button
        type="button"
        className="field-tooltip-trigger"
        aria-describedby={open ? tooltipId : undefined}
        aria-expanded={open}
        aria-label={`Explain field ${fieldName}`}
        onClick={() => setOpen((prev) => !prev)}
        onBlur={(event) => {
          if (!containerRef.current?.contains(event.relatedTarget as Node)) {
            setOpen(false)
          }
        }}
      >
        <HelpCircle size={14} aria-hidden="true" />
      </button>
      {open && (
        <span
          id={tooltipId}
          role="tooltip"
          className="field-tooltip-popover"
        >
          <span className="field-tooltip-type">{doc.type}</span>
          <span className="field-tooltip-desc">{doc.description}</span>
          {doc.vocab && doc.vocab.length > 0 && (
            <span className="field-tooltip-vocab">
              <strong>Vocabulary:</strong> {doc.vocab.join(', ')}
            </span>
          )}
        </span>
      )}
    </span>
  )
}
