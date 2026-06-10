const numberFormatter = new Intl.NumberFormat('en-GB', {
  maximumFractionDigits: 1,
})

const dateFormatter = new Intl.DateTimeFormat('en-GB', {
  day: 'numeric',
  month: 'short',
  year: 'numeric',
})

export function formatPoints(points) {
  return numberFormatter.format(Number(points ?? 0))
}

export function formatDate(value) {
  if (!value) {
    return 'TBD'
  }

  return dateFormatter.format(new Date(value))
}

export function fullName(entity) {
  if (!entity) return ''
  return [entity.first_name, entity.last_name].filter(Boolean).join(' ')
}
