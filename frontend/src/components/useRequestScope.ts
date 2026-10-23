import { useCallback, useLayoutEffect, useRef } from 'react'

/** A response may update its view only while the originating context is current. */
export function useRequestScope(key: string) {
  const generation = useRef(0)
  useLayoutEffect(() => {
    ++generation.current
    return () => { ++generation.current }
  }, [key])
  return useCallback(() => {
    const captured = generation.current
    return () => captured === generation.current
  }, [])
}
