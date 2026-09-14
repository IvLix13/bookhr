export interface ManualStatisticsItem {
  label: string
  value: string
}

export type ManualStatisticsColumn = 'left' | 'right'

export interface ManualStatisticsBlock {
  column: ManualStatisticsColumn
  title: string
  items: ManualStatisticsItem[]
}

export interface ManualStatisticsData {
  items: ManualStatisticsBlock[]
  source_filename: string | null
  updated_at: string | null
}
