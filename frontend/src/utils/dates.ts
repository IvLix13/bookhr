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

const RUSSIAN_MONTHS_NOMINATIVE = [
  'январь',
  'февраль',
  'март',
  'апрель',
  'май',
  'июнь',
  'июль',
  'август',
  'сентябрь',
  'октябрь',
  'ноябрь',
  'декабрь',
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

const RUSSIAN_WEEKDAYS = [
  'воскресенье',
  'понедельник',
  'вторник',
  'среда',
  'четверг',
  'пятница',
  'суббота',
] as const

/** Формат «ДД.ММ.ГГГГ» без сдвига часового пояса. */
export function formatNumericDate(iso: string | null | undefined): string {
  if (!iso) return '—'
  const datePart = iso.slice(0, 10)
  const [year, month, day] = datePart.split('-').map(Number)
  if (!year || !month || !day) return iso
  return `${String(day).padStart(2, '0')}.${String(month).padStart(2, '0')}.${year}`
}

/** Заголовок календаря: «Месяц ГГГГ г.» без сдвига часового пояса. */
export function formatMonthYearLabel(value: Date): string {
  const monthName = RUSSIAN_MONTHS_NOMINATIVE[value.getMonth()]
  const year = value.getFullYear()
  const capitalizedMonth = monthName.charAt(0).toUpperCase() + monthName.slice(1)
  return `${capitalizedMonth} ${year} г.`
}

/** Формат «ДД месяц ГГГГ г.» без сдвига часового пояса. */
export function formatShortDate(iso: string | null | undefined): string {
  if (!iso) return '—'
  const datePart = iso.slice(0, 10)
  const [year, month, day] = datePart.split('-').map(Number)
  if (!year || !month || !day) return iso
  const monthName = RUSSIAN_MONTHS[month - 1]
  if (!monthName) return iso
  return `${day} ${monthName} ${year} г.`
}

function extractClockTime(iso: string): string | null {
  const match = iso.match(/[T ](\d{2}):(\d{2})/)
  if (!match) return null
  return `${match[1]}:${match[2]}`
}

/** Формат «ДД месяц ГГГГ г., ЧЧ:ММ» без сдвига часового пояса. */
export function formatShortDateTime(iso: string | null | undefined): string {
  if (!iso) return '—'
  const dateLabel = formatShortDate(iso)
  if (dateLabel === '—' || dateLabel === iso) return dateLabel
  const timePart = extractClockTime(iso)
  if (!timePart) return dateLabel
  return `${dateLabel}, ${timePart}`
}

/** Формат «Пятница, 24 июля 2026 г.» без сдвига часового пояса и без заглавной «Г.». */
export function formatDisplayDate(iso: string): string {
  const datePart = iso.slice(0, 10)
  const [year, month, day] = datePart.split('-').map(Number)
  if (!year || !month || !day) return iso
  const weekdayName = RUSSIAN_WEEKDAYS[new Date(year, month - 1, day).getDay()]
  const capitalizedWeekday = weekdayName.charAt(0).toUpperCase() + weekdayName.slice(1)
  return `${capitalizedWeekday}, ${formatShortDate(datePart)}`
}

/** Replace ISO dates inside user-facing text with «11 августа 2025 г.». */
export function humanizeDatesInText(text: string | null | undefined): string {
  if (!text) return text ?? ''
  const pattern =
    /(?<!\d)(\d{4})-(\d{2})-(\d{2})(?:[T ]\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?)?(?!\d)/g
  return text.replace(pattern, (match, year: string, month: string, day: string) => {
    const formatted = formatShortDate(`${year}-${month}-${day}`)
    return formatted === '—' || formatted === `${year}-${month}-${day}` ? match : formatted
  })
}

/** Подпись оси/ключа «ГГГГ-ММ»: «Июль 2026 г.» */
export function formatMonthKey(value: string | null | undefined): string {
  if (!value) return '—'
  const [year, month] = value.split('-').map(Number)
  if (!year || !month) return value
  return formatMonthYearLabel(new Date(year, month - 1, 1))
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

export function addYearsToIsoDate(iso: string, years: number): string {
  const [year, month, day] = iso.split('-').map(Number)
  if (!year || !month || !day) return iso
  const wholeYears = Math.floor(years)
  const remainingMonths = Math.round((years - wholeYears) * 12)
  const target = new Date(year + wholeYears, month - 1 + remainingMonths, day)
  return formatLocalDate(target)
}

/** Дата начала договора: окончание минус срок, без сдвига часового пояса. */
export function subtractYearsFromIsoDate(iso: string, years: number): string {
  const [year, month, day] = iso.split('-').map(Number)
  if (!year || !month || !day) return iso
  const wholeYears = Math.floor(years)
  const remainingMonths = Math.round((years - wholeYears) * 12)
  const target = new Date(year - wholeYears, month - 1 - remainingMonths, day)
  return formatLocalDate(target)
}

/** Дата минус N месяцев с прижимом к последнему дню месяца, как relativedelta. */
export function subtractMonthsFromIsoDate(iso: string, months: number): string {
  const [year, month, day] = iso.split('-').map(Number)
  if (!year || !month || !day) return iso
  const totalMonths = year * 12 + (month - 1) - months
  const targetYear = Math.floor(totalMonths / 12)
  const targetMonth = totalMonths - targetYear * 12
  const lastDay = new Date(targetYear, targetMonth + 1, 0).getDate()
  return formatLocalDate(new Date(targetYear, targetMonth, Math.min(day, lastDay)))
}

export function calculateTermYears(
  startDateIso: string | null | undefined,
  endDateIso: string | null | undefined,
): number | null {
  if (!startDateIso || !endDateIso) return null
  const [startYear, startMonth, startDay] = startDateIso.split('-').map(Number)
  const [endYear, endMonth, endDay] = endDateIso.split('-').map(Number)
  if (!startYear || !startMonth || !startDay || !endYear || !endMonth || !endDay) return null

  const startDate = new Date(startYear, startMonth - 1, startDay)
  const endDate = new Date(endYear, endMonth - 1, endDay)
  if (endDate <= startDate) return null

  let years = endYear - startYear
  let months = endMonth - startMonth
  let days = endDay - startDay
  if (days < 0) {
    months -= 1
    days += 30
  }
  if (months < 0) {
    years -= 1
    months += 12
  }
  const approxMonths = years * 12 + months + days / 30.4375
  const totalYears = approxMonths / 12
  const rounded = Math.round(totalYears * 10) / 10
  if (Math.abs(rounded - Math.round(rounded)) < 0.05) {
    return Math.round(rounded)
  }
  return rounded
}
