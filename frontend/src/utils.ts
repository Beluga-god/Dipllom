import { format, isValid } from 'date-fns';
import { CaseFormDataTypeForRHF, CaseDataInput, PersonalData, OtherDocumentData } from './types';

// Вспомогательная функция для форматирования Date в YYYY-MM-DD
export const formatDateForInput = (date: Date | null | undefined): string => {
  if (!date || !isValid(date)) return '';
  return format(date, 'yyyy-MM-dd');
};

export const prepareDataForApi = (formData: CaseFormDataTypeForRHF): CaseDataInput => {
  // Создаем объект personal_data для API, включая dependents
  const apiPersonalData: PersonalData = {
    last_name: formData.personal_data?.last_name || '',
    first_name: formData.personal_data?.first_name || '',
    middle_name: formData.personal_data?.middle_name || null,
    birth_date: formData.personal_data?.birth_date || '',
    snils: formData.personal_data?.snils || '',
    gender: formData.personal_data?.gender || '',
    citizenship: formData.personal_data?.citizenship || '',
    dependents: typeof formData.personal_data?.dependents === 'number' ? formData.personal_data.dependents : 0,
    name_change_info: (formData.personal_data?.name_change_info?.old_full_name || formData.personal_data?.name_change_info?.date_changed) && formData.personal_data?.name_change_info
            ? {
                old_full_name: formData.personal_data.name_change_info.old_full_name,
                date_changed: formData.personal_data.name_change_info.date_changed
              }
            : null,
  };

  // Очищаем other_documents_extracted_data, оставляя только нужные поля
  const sanitizedOtherDocumentsData = formData.other_documents_extracted_data?.map(doc => {
    const newDoc: Partial<OtherDocumentData> = {};
    if (doc.standardized_document_type) {
      newDoc.standardized_document_type = doc.standardized_document_type;
    }
    if (doc.extracted_fields) {
      newDoc.extracted_fields = doc.extracted_fields;
    }
    return newDoc as OtherDocumentData;
  }).filter(Boolean) as OtherDocumentData[] | undefined;

  // Подготовка work_experience
  const workExperienceData = formData.work_experience ? {
      ...formData.work_experience,
      calculated_total_years: formData.work_experience.calculated_total_years ?? null,
      records: formData.work_experience.records?.map(r => ({
          ...r,
          special_conditions: r.special_conditions ?? false
      })) ?? null
  } : null;

  const dataToSend: CaseDataInput = {
    benefit_type: formData.benefit_type || '',
    personal_data: apiPersonalData,
    work_experience: workExperienceData,
    pension_points: formData.pension_points || null,
    benefits: (formData.benefits || '').split(',').map((s: string) => s.trim()).filter(Boolean),
    submitted_documents: (formData.documents || '').split(',').map((s: string) => s.trim()).filter(Boolean),
    has_incorrect_document: formData.has_incorrect_document || null,
    disability: formData.disability 
        ? {
            group: formData.disability.group || "1",
            date: formData.disability.date || '',
            cert_number: formData.disability.cert_number || null
          }
        : null,
    other_documents_extracted_data: sanitizedOtherDocumentsData || null
  };
  return dataToSend;
};