const RUSSIAN_MONTHS = [
  'января',
  'февраля',
  'марта',
  'апреля',
  'мая',
  'июня',
  'июля',
  'августа',
  'сентября',
  'октября',
  'ноября',
  'декабря',
] as const

export function formatLocalDate(value: Date): string {
  const year = value.getFullYear()
  const month = String(value.getMonth() + 1).padStart(2, '0')
  const day = String(value.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

export function monthRange(value: Date): { from: string; to: string } {
  const year = value.getFullYear()
  const monthIndex = value.getMonth()
  return {
    from: formatLocalDate(new Date(year, monthIndex, 1)),
    to: formatLocalDate(new Date(year, monthIndex + 1, 0)),
  }
}

export function defaultStatsPeriod(): { from: string; to: string } {
  const today = new Date()
  const from = new Date(today.getFullYear(), today.getMonth() - 11, 1)
  return {
    from: formatLocalDate(from),
    to: formatLocalDate(today),
  }
}

export function formatDisplayDate(iso: string): string {
  const [year, month, day] = iso.split('-').map(Number)
  return new Date(year, month - 1, day).toLocaleDateString('ru-RU', {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  })
}

/** Формат «ДД.ММ.ГГГГ» без сдвига часового пояса. */
export function formatNumericDate(iso: string | null | undefined): string {
  if (!iso) return '—'
  const datePart = iso.slice(0, 10)
  const [year, month, day] = datePart.split('-').map(Number)
  if (!year || !month || !day) return iso
  return `${String(day).padStart(2, '0')}.${String(month).padStart(2, '0')}.${year}`
}

/** Формат «ДД месяц ГГГГ г.» без сдвига часового пояса. */
export function formatShortDate(iso: string | null | undefined): string {
  if (!iso) return '—'
  const [year, month, day] = iso.split('-').map(Number)
  if (!year || !month || !day) return iso
  const monthName = RUSSIAN_MONTHS[month - 1]
  if (!monthName) return iso
  return `${day} ${monthName} ${year} г.`
}

export function isSameLocalDate(left: Date, right: Date): boolean {
  return formatLocalDate(left) === formatLocalDate(right)
}

export function parseIsoDate(iso: string | null | undefined): number | null {
  if (!iso) return null
  const [year, month, day] = iso.split('-').map(Number)
  if (!year || !month || !day) return null
  return year * 10000 + month * 100 + day
}
