import { useEffect, useRef, useState, type CSSProperties, type ElementType, type ReactNode } from 'react'

/**
 * Fades its content up the first time it scrolls into view. Without IntersectionObserver (tests,
 * old browsers) it shows at once. Reduced motion turns the fade off in index.css.
 */
export default function Reveal({
  as: Tag = 'div',
  index = 0,
  className = '',
  children,
}: {
  as?: ElementType
  index?: number
  className?: string
  children: ReactNode
}) {
  const ref = useRef<HTMLElement>(null)
  const [shown, setShown] = useState(() => typeof IntersectionObserver === 'undefined')

  useEffect(() => {
    if (shown || !ref.current) return
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setShown(true)
          observer.disconnect()
        }
      },
      { rootMargin: '0px 0px -8% 0px' },
    )
    observer.observe(ref.current)
    return () => observer.disconnect()
  }, [shown])

  return (
    <Tag ref={ref} className={`reveal ${shown ? 'is-in' : ''} ${className}`} style={{ '--i': index } as CSSProperties}>
      {children}
    </Tag>
  )
}
