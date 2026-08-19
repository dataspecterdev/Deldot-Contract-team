import { useCallback, useRef, useState } from 'react'

interface UseResizableOptions {
  direction: 'horizontal' | 'vertical'
  initialSize: number // percentage (0-100)
  minSize?: number // percentage
  maxSize?: number // percentage
}

export function useResizable({ direction, initialSize, minSize = 15, maxSize = 85 }: UseResizableOptions) {
  const [size, setSize] = useState(initialSize)
  const containerRef = useRef<HTMLDivElement | null>(null)
  const dragging = useRef(false)

  const onMouseDown = useCallback(
    (e: React.MouseEvent) => {
      e.preventDefault()
      dragging.current = true

      const startPos = direction === 'horizontal' ? e.clientX : e.clientY

      const onMouseMove = (moveEvent: MouseEvent) => {
        if (!dragging.current || !containerRef.current) return
        const rect = containerRef.current.getBoundingClientRect()
        const totalSize = direction === 'horizontal' ? rect.width : rect.height
        const offset = direction === 'horizontal'
          ? moveEvent.clientX - rect.left
          : moveEvent.clientY - rect.top
        const percent = (offset / totalSize) * 100
        setSize(Math.min(maxSize, Math.max(minSize, percent)))
      }

      const onMouseUp = () => {
        dragging.current = false
        document.removeEventListener('mousemove', onMouseMove)
        document.removeEventListener('mouseup', onMouseUp)
        document.body.style.cursor = ''
        document.body.style.userSelect = ''
      }

      document.addEventListener('mousemove', onMouseMove)
      document.addEventListener('mouseup', onMouseUp)
      document.body.style.cursor = direction === 'horizontal' ? 'col-resize' : 'row-resize'
      document.body.style.userSelect = 'none'
    },
    [direction, minSize, maxSize]
  )

  return { size, containerRef, onMouseDown }
}
