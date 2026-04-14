// src/types.ts

export interface NameChangeInfo {
  old_full_name: string | null;
  date_changed: string | null; // YYYY-MM-DD
}

export interface PersonalData {
  last_name: string;
  first_name: string;
  middle_name: string | null;
  birth_date: string; // YYYY-MM-DD
  snils: string;
  gender: string; // "Мужской", "Женский"
  citizenship: string;
  name_change_info: NameChangeInfo | null;
  dependents: number;
}

export interface DisabilityInfo {
  group: "1" | "2" | "3" | "child";
  date: string; // YYYY-MM-DD
  cert_number: string | null;
}

export type WorkBookEventType = "ПРИЕМ" | "ПЕРЕВОД" | "УВОЛЬНЕНИЕ" | "НАГРАЖДЕНИЕ" | "ДРУГОЕ";

export interface WorkBookEventRecord {
    event_type: WorkBookEventType | null;
    date: string | null; // YYYY-MM-DD
    organization: string | null;
    position: string | null;
    raw_text: string;
}

export interface WorkBookRecordEntry {
  organization: string | null;
  position: string | null;
  date_in: string | null; // YYYY-MM-DD
  date_out: string | null; // YYYY-MM-DD
  special_conditions?: boolean | null;
}

export interface WorkExperience {
  calculated_total_years?: number | null;
  records?: WorkBookRecordEntry[] | null;
  raw_events?: WorkBookEventRecord[] | null;
}

export interface OtherDocumentData {
  identified_document_type: string | null;
  standardized_document_type: string | null;
  extracted_fields: Record<string, any> | null;
  multimodal_assessment: string | null;
  text_llm_reasoning: string | null;
  birth_place: string | null;
}

export interface CaseDataInput {
  personal_data: PersonalData;
  benefit_type: string; // ID из /api/v1/benefit_types (типы льгот для участников СВО)
  disability: DisabilityInfo | null;
  work_experience: WorkExperience | null;
  pension_points: number | null;
  benefits: string[] | null;
  submitted_documents: string[] | null; // ID из /api/v1/benefit_documents/{benefit_type_id}
  has_incorrect_document: boolean | null;
  other_documents_extracted_data: OtherDocumentData[] | null;
}

export interface ErrorDetail {
  code: string | null;
  message: string | null;
  source: string | null;
  details: Record<string, any> | null;
}

export interface ProcessOutput {
  case_id: number;
  final_status: string; // "PROCESSING", "COMPLETED", "FAILED", "ERROR_PROCESSING", "СООТВЕТСТВУЕТ", "НЕ СООТВЕТСТВУЕТ", "UNKNOWN"
  explanation: string | null;
  confidence_score: number | null;
  department_code: string | null;
  error_info: ErrorDetail | null;
}

export interface CaseHistoryEntry {
  id: number;
  created_at: string; // ISO 8601
  benefit_type: string; // Тип запрашиваемой льготы
  final_status: string;
  final_explanation: string | null;
  rag_confidence: number | null;
  personal_data: PersonalData | null;
}

export interface FullCaseData extends CaseDataInput {
  id: number;
  created_at: string; // ISO 8601
  updated_at: string | null; // ISO 8601
  errors: Record<string, any>[] | null;
  final_status: string | null;
  final_explanation: string | null;
  rag_confidence: number | null;
}

export interface PassportData {
  last_name: string | null;
  first_name: string | null;
  middle_name: string | null;
  birth_date: string | null; // YYYY-MM-DD
  sex: string | null; // "МУЖ.", "ЖЕН."
  birth_place: string | null;
  passport_series: string | null;
  passport_number: string | null;
  issue_date: string | null; // YYYY-MM-DD
  issuing_authority: string | null;
  department_code: string | null;
}

export interface SnilsData {
  snils_number: string | null;
  last_name: string | null;
  first_name: string | null;
  middle_name: string | null;
  gender: string | null;
  birth_date: string | null; // YYYY-MM-DD
  birth_place: string | null;
}

export interface WorkBookData {
  raw_events: WorkBookEventRecord[];
  records: WorkBookRecordEntry[];
  calculated_total_years: number | null;
}

export interface OcrTaskSubmitResponse {
  task_id: string;
  status: "PROCESSING";
  message: string;
}

export type OcrTaskStatus = "PROCESSING" | "COMPLETED" | "FAILED";

export type OcrResultData = PassportData | SnilsData | WorkBookData | OtherDocumentData;

export interface OcrTaskStatusResponse {
  task_id: string;
  status: OcrTaskStatus;
  data: OcrResultData | null;
  error: {
    detail: string;
    type: string;
  } | null;
}

export interface TasksStatsResponse {
  total: number;
  pending: number;
  expired_processing: number;
  status_specific_counts: {
    PROCESSING: number;
    COMPLETED: number;
    FAILED: number;
    [key: string]: number;
  };
}

export interface DocumentDetail {
  id: string;
  name: string;
  description: string;
  is_critical: boolean;
  condition_text: string | null;
  ocr_type: "passport" | "snils" | "work_book" | "other" | null;
}

export interface DependencyStatus {
  name: string; // "database", "Ollama_LLM", "Ollama_Vision", "neo4j"
  status: "ok" | "error" | "skipped";
  message: string | null;
}

export interface HealthCheckResponse {
  overall_status: "healthy" | "unhealthy";
  timestamp: string; // ISO 8601
  dependencies: DependencyStatus[];
}

// Типы для эндпоинтов конфигурации (льготы СВО)
export interface BenefitTypeInfo {
  id: string;
  display_name: string;
  description: string;
}

// Типы для пользователя
export interface User {
  id: number;
  username: string;
  role: "admin" | "manager";
  is_active: boolean;
}

export interface TokenResponse {
  access_token: string;
  token_type: "bearer";
}

export type DocumentTypeToExtract = "passport" | "snils" | "work_book" | "other";

export interface DocumentExtractionParams {
  document_type: DocumentTypeToExtract;
  image: File;
  ttl_hours?: number; // 1-168
}

export type DocumentFormat = "pdf" | "docx";

export interface StandardErrorResponse {
    error_code: string;
    message: string;
    details?: any;
}

export interface ValidationErrorDetailItem {
    loc: (string | number)[];
    msg: string;
    type: string;
}
export interface HttpValidationError {
    detail: ValidationErrorDetailItem[];
}

export interface StandardizedValidationErrorDetail {
    field: string;
    message: string;
    type: string;
}
export interface StandardizedValidationErrorResponse {
    error_code: "VALIDATION_ERROR";
    message: string;
    details: StandardizedValidationErrorDetail[];
}

export interface ApiError {
  status: number;
  message: string;
  errorCode?: string;
  validationDetails?: StandardizedValidationErrorDetail[] | ValidationErrorDetailItem[];
  rawError?: any;
}

// Тип для данных формы React Hook Form
export interface CaseFormDataTypeForRHF {
  benefit_type?: string; // ID из /api/v1/benefit_types
  personal_data?: Partial<PersonalData> & { 
    name_change_info_checkbox?: boolean;
    passport_series?: string;
    passport_number?: string;
    passport_issue_date?: string; 
    issuing_authority?: string;
    department_code?: string;
    birth_place?: string;
  };
  disability?: Partial<DisabilityInfo> | null;
  work_experience?: Partial<WorkExperience>;
  pension_points?: number | null;
  benefits?: string;
  submitted_documents?: string;
  has_incorrect_document?: boolean;
  other_documents_extracted_data?: Partial<OtherDocumentData>[];
  
  [key: string]: any;
}

// Типы для RAG документов
export interface DocumentListResponse {
  filenames: string[];
}

export interface DocumentUploadResponse {
  filename: string;
  message: string;
}

export interface DocumentDeleteResponse {
  filename: string;
  message: string;
}