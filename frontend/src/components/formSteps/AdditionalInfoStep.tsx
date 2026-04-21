import React from 'react';
import { Control, Controller, FieldErrors } from 'react-hook-form';
import { Form, Typography, Divider, Input, Select, Row, Col, Checkbox } from 'antd';
import { CaseFormDataTypeForRHF } from '../../types';
import TagInput from '../formInputs/TagInput';

const { Title, Text, Paragraph } = Typography;
const { TextArea } = Input;
const { Option } = Select;

interface AdditionalInfoStepProps {
    control: Control<CaseFormDataTypeForRHF>;
    errors: FieldErrors<CaseFormDataTypeForRHF>;
    benefitType: string | null;
    setValue: any;
    getValues: any;
    trigger: any;
    standardDocNames?: string[];
    requiredDocsForType?: any[];
}

const AdditionalInfoStep: React.FC<AdditionalInfoStepProps> = ({
    control,
    errors,
    benefitType,
    setValue,
    getValues,
    trigger,
    standardDocNames,
    requiredDocsForType
}) => {
    // Определяем, нужно ли показывать поле "Пенсионные баллы" (только для пенсионных льгот)
    const showPensionPoints = benefitType === 'retirement_standard';

    return (
        <div style={{ maxWidth: '700px', margin: '0 auto' }}>
            <Title level={4} style={{ marginBottom: '20px', textAlign: 'center' }}>
                Дополнительная информация о льготах
            </Title>

            {showPensionPoints && (
    <Form.Item
        label="Пенсионные баллы (ИПК) — если запрашивается пенсия"
        name="pension_points"
        validateStatus={errors.pension_points ? 'error' : ''}
        help={errors.pension_points?.message as string | undefined}
    >
        <Controller
            name="pension_points"
            control={control}
            render={({ field }) => (
                <Input 
                    {...field}
                    value={field.value ?? undefined}
                    type="number" 
                    placeholder="Например: 45.2"
                    style={{ width: '100%' }}
                />
            )}
        />
    </Form.Item>
)}

            <Divider style={{ margin: '24px 0' }} />

            <Title level={5} style={{ marginBottom: '16px' }}>
                Какие льготы и выплаты вас интересуют?
            </Title>
            <Paragraph type="secondary" style={{ marginBottom: '16px' }}>
                Введите названия льгот, которые вы хотите получить (например: "Ежемесячная выплата", "Земельный участок", "Льготная ипотека").
            </Paragraph>

            <Form.Item
                label="Льготы и выплаты"
                name="benefits"
                validateStatus={errors.benefits ? 'error' : ''}
                help={errors.benefits?.message as string | undefined}
            >
                <Controller
                    name="benefits"
                    control={control}
                    render={({ field }) => (
                        <TagInput 
                            fieldOnChange={field.onChange} 
                            value={field.value}
                            placeholder="Добавить льготу и нажать Enter"
                        />
                    )}
                />
            </Form.Item>

            <Divider style={{ margin: '24px 0' }} />

            <Title level={5} style={{ marginBottom: '16px' }}>
                Какие документы у вас есть?
            </Title>
            <Paragraph type="secondary" style={{ marginBottom: '16px' }}>
                Укажите, какие документы вы можете предоставить для подтверждения льгот:
            </Paragraph>

            <Form.Item
                label="Представленные документы"
                name="documents"
                validateStatus={errors.documents ? 'error' : ''}
                help={errors.documents?.message as string | undefined}
            >
                <Controller
                    name="documents"
                    control={control}
                    render={({ field }) => (
                        <TagInput 
                            fieldOnChange={field.onChange} 
                            value={field.value}
                            placeholder="Добавить документ и нажать Enter"
                        />
                    )}
                />
            </Form.Item>

            <Divider style={{ margin: '24px 0' }} />

            <Title level={5} style={{ marginBottom: '16px' }}>
                Дополнительные сведения
            </Title>

            <Form.Item name="has_incorrect_document" valuePropName="checked">
                <Controller
                    name="has_incorrect_document"
                    control={control}
                    defaultValue={false}
                    render={({ field: { onChange, value, ref } }) => (
                        <Checkbox 
                            onChange={onChange} 
                            checked={!!value}
                            ref={ref}
                        >
                            У меня есть некорректно оформленные документы
                        </Checkbox>
                    )}
                />
            </Form.Item>

            <Paragraph type="secondary" style={{ marginTop: '16px', fontSize: '12px' }}>
                * Все поля заполняются вручную. При необходимости вы можете обратиться за консультацией.
            </Paragraph>
        </div>
    );
};

export default AdditionalInfoStep;