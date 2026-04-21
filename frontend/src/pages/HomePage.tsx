// src/pages/HomePage.tsx
import React, { useState, useEffect } from 'react';
import {
  Steps,
  Button,
  Form,
  message as antdMessage,
  Spin,
  Alert,
  Card,
  Typography,
  Result,
  Row,
  Col,
  Tag,
} from 'antd';
import {
  UserOutlined,
  AuditOutlined,
  InfoCircleOutlined,
  LoadingOutlined,
  GiftOutlined,
} from '@ant-design/icons';
import { useForm, FormProvider, Controller } from 'react-hook-form';

import { createCase, getCaseStatus, getBenefitTypes, getStandardDocumentNames, getBenefitDocuments } from '../services/apiClient';
import type {
  CaseDataInput,
  ProcessOutput,
  ApiError,
  BenefitTypeInfo,
  DocumentDetail,
  CaseFormDataTypeForRHF
} from '../types';

import BenefitTypeStep from '../components/formSteps/BenefitTypeStep';
import PersonalDataStep from '../components/formSteps/PersonalDataStep';
import AdditionalInfoStep from '../components/formSteps/AdditionalInfoStep';
import SummaryStep from '../components/formSteps/SummaryStep';
import ProcessResultDisplay from '../components/ProcessResultDisplay';

const { Title } = Typography;

const POLLING_INTERVAL = 5000;

const initialRHFValues: CaseFormDataTypeForRHF = {
  benefit_type: undefined,
  personal_data: {
    last_name: '',
    first_name: '',
    middle_name: null,
    birth_date: '',
    snils: '',
    gender: '',
    citizenship: 'Россия',
    name_change_info: null,
    name_change_info_checkbox: false,
    dependents: 0,
    passport_series: '',
    passport_number: '',
    passport_issue_date: '',
    issuing_authority: '',
    department_code: '',
    birth_place: '',
  },
  disability: null,
  pension_points: null,
  benefits: '',
  documents: '',
  has_incorrect_document: false,
  other_documents_extracted_data: [],
};

const HomePage: React.FC = () => {
  const [antdForm] = Form.useForm();

  const rhfMethods = useForm<CaseFormDataTypeForRHF>({
    defaultValues: initialRHFValues,
    mode: 'onChange',
  });
  const { control, watch, setValue, getValues, formState: { errors: rhfErrors }, trigger, handleSubmit, reset: rhfReset } = rhfMethods;

  const [currentStep, setCurrentStep] = useState(0);
  const [loading, setLoading] = useState(false);
  const [submissionResult, setSubmissionResult] = useState<ProcessOutput | null>(null);
  const [pollingCaseId, setPollingCaseId] = useState<number | null>(null);
  const [finalCaseStatus, setFinalCaseStatus] = useState<ProcessOutput | null>(null);
  const [submissionError, setSubmissionError] = useState<string | null>(null);
  const [personalDataStepValid, setPersonalDataStepValid] = useState(false);

  const [benefitTypes, setBenefitTypes] = useState<BenefitTypeInfo[]>([]);
  const [loadingBenefitTypes, setLoadingBenefitTypes] = useState(true);
  const [standardDocNames, setStandardDocNames] = useState<string[]>([]);
  const [requiredDocsForType, setRequiredDocsForType] = useState<DocumentDetail[]>([]);

  useEffect(() => {
    const fetchInitialData = async () => {
      setLoadingBenefitTypes(true);
      try {
        const types = await getBenefitTypes();
        setBenefitTypes(types);
        const stdNames = await getStandardDocumentNames();
        setStandardDocNames(stdNames);
      } catch (error) {
        console.error("Error fetching initial data for form:", error);
        antdMessage.error('Ошибка загрузки справочников для формы.');
      } finally {
        setLoadingBenefitTypes(false);
      }
    };
    fetchInitialData();
  }, []);

  const selectedBenefitTypeRHF = watch('benefit_type');

  useEffect(() => {
    if (selectedBenefitTypeRHF) {
      const fetchReqDocs = async () => {
        try {
          const docs = await getBenefitDocuments(selectedBenefitTypeRHF);
          setRequiredDocsForType(docs);
        } catch (error) {
          console.error("Error fetching required documents:", error);
          setRequiredDocsForType([]);
        }
      };
      fetchReqDocs();
    } else {
      setRequiredDocsForType([]);
    }
  }, [selectedBenefitTypeRHF]);

  // Только 4 шага
  const steps = [
    {
      title: 'Тип поддержки',
      icon: <GiftOutlined />,
      content: (
        <Controller
          name="benefit_type"
          control={control}
          rules={{ required: 'Пожалуйста, выберите тип поддержки!' }}
          render={({ field }) => (
            <BenefitTypeStep
              form={antdForm}
              benefitTypes={benefitTypes}
              loadingBenefitTypes={loadingBenefitTypes}
              currentValue={field.value}
              onChange={(value) => {
                field.onChange(value);
                trigger();
              }}
            />
          )}
        />
      ),
      fieldsToValidate: ['benefit_type'],
    },
    {
      title: 'Личные данные',
      icon: <UserOutlined />,
      content: (
        <PersonalDataStep
          control={control}
          watch={watch}
          setValue={setValue}
          form={antdForm}
          errors={rhfErrors}
          onValidationStateChange={setPersonalDataStepValid}
        />
      ),
      fieldsToValidate: [
        'personal_data.last_name', 'personal_data.first_name',
        'personal_data.birth_date', 'personal_data.snils',
        'personal_data.gender', 'personal_data.citizenship',
        'personal_data.dependents'
      ],
    },
    {
      title: 'Доп. информация',
      icon: <InfoCircleOutlined />,
      content: (
        <AdditionalInfoStep
          control={control}
          errors={rhfErrors}
          benefitType={selectedBenefitTypeRHF || null}
          setValue={setValue}
          getValues={getValues}
          trigger={trigger}
          standardDocNames={standardDocNames}
          requiredDocsForType={requiredDocsForType}
        />
      ),
      fieldsToValidate: [],
    },
    {
      title: 'Сводка и отправка',
      icon: <AuditOutlined />,
      content: <SummaryStep formData={getValues()} />,
    },
  ];

  const getVisibleSteps = () => {
    return steps; // Показываем все 4 шага
  };

  const currentVisibleSteps = getVisibleSteps();
  const activeStepContent = currentVisibleSteps[currentStep]?.content;
  const activeStepFieldsToValidate = currentVisibleSteps[currentStep]?.fieldsToValidate as string[] | undefined;

  const next = async () => {
    let isValid = true;
    if (activeStepFieldsToValidate && activeStepFieldsToValidate.length > 0) {
      isValid = await trigger(activeStepFieldsToValidate);
    }
    if (isValid) {
      setCurrentStep(currentStep + 1);
    } else {
      antdMessage.error('Пожалуйста, заполните все обязательные поля на текущем шаге.');
    }
  };

  const prev = () => {
    setCurrentStep(currentStep - 1);
  };

  const handleFormSubmitRHF = async (data: CaseFormDataTypeForRHF) => {
    setLoading(true);
    setSubmissionError(null);
    setSubmissionResult(null);
    setFinalCaseStatus(null);

    const apiPayload: CaseDataInput = {
      benefit_type: data.benefit_type!,
      personal_data: {
        last_name: data.personal_data!.last_name!,
        first_name: data.personal_data!.first_name!,
        middle_name: data.personal_data!.middle_name || null,
        birth_date: data.personal_data!.birth_date!,
        snils: data.personal_data!.snils!,
        gender: data.personal_data!.gender!,
        citizenship: data.personal_data!.citizenship!,
        name_change_info: data.personal_data!.name_change_info_checkbox && data.personal_data!.name_change_info
          ? data.personal_data!.name_change_info
          : null,
        dependents: data.personal_data!.dependents || 0,
      },
      disability: null,
      work_experience: null,
      pension_points: data.pension_points || null,
      benefits: data.benefits ? data.benefits.split(',').map((s: string) => s.trim()).filter(Boolean) : [],
      submitted_documents: data.documents ? data.documents.split(',').map((s: string) => s.trim()).filter(Boolean) : [],
      has_incorrect_document: data.has_incorrect_document || false,
      other_documents_extracted_data: [],
    };

    console.log('Submitting API Payload:', apiPayload);

    try {
      const result = await createCase(apiPayload);
      setSubmissionResult(result);
      if (result.case_id && result.final_status === 'PROCESSING') {
        setPollingCaseId(result.case_id);
      } else {
        setFinalCaseStatus(result);
      }
    } catch (err) {
      const apiErr = err as ApiError;
      console.error('Form submission error:', apiErr);
      let errorMessageText = apiErr.message || 'Произошла ошибка при отправке обращения.';
      if (apiErr.validationDetails && Array.isArray(apiErr.validationDetails)) {
        const fieldsErrors = apiErr.validationDetails.map(detail => {
          let fieldPath = (detail as any).field?.replace(/^body\./, '') || (detail as any).loc?.slice(1).join('.');
          const message = (detail as any).msg || (detail as any).message || 'Неизвестная ошибка поля';
          return `${fieldPath}: ${message}`;
        }).join('; ');
        errorMessageText += ` Детали: ${fieldsErrors}`;
      }
      setSubmissionError(errorMessageText);
      antdMessage.error(errorMessageText, 7);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    let intervalId: number | undefined;
    if (pollingCaseId) {
      setLoading(true);
      const pollStatus = async () => {
        try {
          console.log(`Polling status for case ID: ${pollingCaseId}`);
          const statusResult = await getCaseStatus(pollingCaseId);
          if (statusResult.final_status !== 'PROCESSING') {
            setFinalCaseStatus(statusResult);
            setPollingCaseId(null);
            if (intervalId) clearInterval(intervalId);
            setLoading(false);
            antdMessage.success(`Обработка обращения #${statusResult.case_id} завершена. Статус: ${statusResult.final_status}`);
          } else {
            setSubmissionResult(statusResult);
          }
        } catch (error) {
          console.error('Polling error:', error);
          antdMessage.warning('Ошибка при опросе статуса обращения. Поллинг будет продолжен.');
        }
      };
      pollStatus();
      intervalId = window.setInterval(pollStatus, POLLING_INTERVAL);
    }
    return () => {
      if (intervalId) clearInterval(intervalId);
      if (pollingCaseId) setLoading(false);
    };
  }, [pollingCaseId]);

  const resetFormAndState = () => {
    rhfReset(initialRHFValues);
    antdForm.resetFields();
    setCurrentStep(0);
    setSubmissionResult(null);
    setPollingCaseId(null);
    setFinalCaseStatus(null);
    setSubmissionError(null);
    setLoading(false);
    setPersonalDataStepValid(false);
  };

  if (finalCaseStatus) {
    return (
      <Result
        status={finalCaseStatus.final_status.toLowerCase().includes('соответствует') ? 'success' : finalCaseStatus.final_status.toLowerCase().includes('не соответствует') ? 'error' : 'info'}
        title={`Обработка обращения завершена`}
        subTitle={`Статус обращения ID ${finalCaseStatus.case_id}: ${finalCaseStatus.final_status}`}
        extra={[
          <Button type="primary" key="new" onClick={resetFormAndState}>
            Создать новое обращение
          </Button>,
        ]}
      >
        <div style={{ maxWidth: '800px', margin: '0 auto', textAlign: 'left' }}>
          <ProcessResultDisplay result={finalCaseStatus} />
        </div>
      </Result>
    );
  }

  if (submissionResult && pollingCaseId) {
    return (
      <div style={{ textAlign: 'center', padding: '50px' }}>
        <Spin indicator={<LoadingOutlined style={{ fontSize: 48 }} spin />} tip={`Обращение #${submissionResult.case_id} принято в обработку. Ожидаем результат...`} size="large" />
        <Typography.Paragraph style={{ marginTop: 20 }}>
          Текущий статус: <Tag color="blue">{submissionResult.final_status}</Tag>
        </Typography.Paragraph>
        <Typography.Paragraph style={{ whiteSpace: 'pre-wrap', color: '#888' }}>
          {submissionResult.explanation}
        </Typography.Paragraph>
      </div>
    );
  }

  return (
    <FormProvider {...rhfMethods}>
      <Card style={{ maxWidth: '1000px', margin: '20px auto' }}>
        <Title level={2} style={{ textAlign: 'center', marginBottom: '30px' }}>
          Создание нового обращения
        </Title>
        <Steps
          current={currentStep}
          items={currentVisibleSteps.map(item => ({ key: item.title, title: item.title, icon: item.icon }))}
          style={{ marginBottom: '40px' }}
          progressDot
        />

        <Form
          form={antdForm}
          layout="vertical"
          name="benefit_case_form_rhf"
          onFinish={handleSubmit(handleFormSubmitRHF)}
        >
          <Spin spinning={loading && currentStep === currentVisibleSteps.length - 1} tip="Отправка данных...">
            <div style={{ minHeight: '300px', marginBottom: '24px' }}>
              {activeStepContent}
            </div>
          </Spin>

          {submissionError && !pollingCaseId && (
            <Alert message="Ошибка отправки" description={submissionError} type="error" showIcon style={{ marginBottom: '24px' }} />
          )}

          <Row justify="space-between">
            <Col>
              {currentStep > 0 && (
                <Button style={{ margin: '0 8px' }} onClick={prev}>
                  Назад
                </Button>
              )}
            </Col>
            <Col>
              {currentStep < currentVisibleSteps.length - 1 && (
                <Button
                  type="primary"
                  onClick={next}
                  disabled={currentVisibleSteps[currentStep]?.title === 'Личные данные' && !personalDataStepValid}
                >
                  Далее
                </Button>
              )}
              {currentStep === currentVisibleSteps.length - 1 && (
                <Button type="primary" htmlType="submit" loading={loading}>
                  Отправить обращение
                </Button>
              )}
            </Col>
          </Row>
        </Form>
      </Card>
    </FormProvider>
  );
};

export default HomePage;