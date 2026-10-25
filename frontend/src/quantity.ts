// Retain the stored marker for compatibility with existing month reports.
// It is not a physical unit and must never be presented as one.
export const UNKNOWN_QUANTITY_UNIT = '原始商品单位'

export function quantityUnit(value?: string | null): string {
  const unit = value?.trim() ?? ''
  return unit === UNKNOWN_QUANTITY_UNIT ? '' : unit
}

// Clean only legacy generated numeric phrases, not product names or user notes.
export function quantityText(value: string): string {
  return value.replace(/(\d)[ \t]*原始商品单位/g, '$1')
}
