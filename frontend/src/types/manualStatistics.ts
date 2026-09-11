export interface ManualStatisticsItem {
  label: string
  value: string
}

export interface ManualStatisticsData {
  items: ManualStatisticsItem[]
  source_filename: string | null
  updated_at: string | null
}
