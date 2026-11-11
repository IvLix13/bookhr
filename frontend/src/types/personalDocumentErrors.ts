export type PersonalDocumentErrorCode =
  | 'grade'
  | 'post'
  | 'contract'
  | 'photo'
  | 'biography'
  | 'attestation'
  | 'passport'

export interface PersonalDocumentErrorsCard {
  external_id: number
  ldnumber: string
  cardnumber: string | null
  full_name: string
  grade: string | null
  errors: PersonalDocumentErrorCode[]
  personal_file_url: string
}

export interface PersonalDocumentErrorsResult {
  state: 'ready' | 'not_configured' | 'refreshing' | 'source_error'
  last_success_at: string | null
  timezone: string
  items: PersonalDocumentErrorsCard[]
}
