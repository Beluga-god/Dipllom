// src/components/formSteps/BenefitTypeStep.tsx
import React from 'react';
import { Form, Spin, Alert, Typography, Empty, Card, Row, Col } from 'antd';
import type { FormInstance } from 'antd/es/form';
import type { CaseDataInput, BenefitTypeInfo } from '../../types';

const { Paragraph, Text } = Typography;

interface BenefitTypeStepProps {
  form: FormInstance<CaseDataInput>;
  benefitTypes: BenefitTypeInfo[];
  loadingBenefitTypes: boolean;
  currentValue?: string;
  onChange?: (value: string) => void;
}

const BenefitTypeStep: React.FC<BenefitTypeStepProps> = ({
  form,
  benefitTypes,
  loadingBenefitTypes,
  currentValue,
  onChange,
}) => {
  if (loadingBenefitTypes) {
    return (
      <div style={{ textAlign: 'center', padding: '30px' }}>
        <Spin tip="Загрузка типов поддержки..." />
      </div>
    );
  }

  if (!loadingBenefitTypes && benefitTypes.length === 0) {
    return <Empty description="Типы поддержки не найдены или не загружены." />;
  }

  const handleCardClick = (benefitTypeId: string) => {
    if (onChange) {
      onChange(benefitTypeId);
    }
  };

  return (
    <>
      <Paragraph style={{ marginBottom: '20px', textAlign: 'center' }}>
        Пожалуйста, выберите тип поддержки, на которую подается обращение.
        От выбранного типа будет зависеть дальнейший набор шагов и необходимых документов.
      </Paragraph>
      <Form.Item
        rules={[{ required: true, message: 'Пожалуйста, выберите тип поддержки!' }]}
      >
        <Row gutter={[16, 16]}>
          {benefitTypes.map((bt) => (
            <Col xs={24} sm={12} md={8} key={bt.id}>
              <Card
                hoverable
                onClick={() => handleCardClick(bt.id)}
                style={{
                  height: '100%',
                  border: currentValue === bt.id ? '2px solid #1890ff' : '1px solid #d9d9d9',
                  boxShadow: currentValue === bt.id ? '0 0 0 2px rgba(24, 144, 255, 0.2)' : 'none'
                }}
                bodyStyle={{ padding: '16px', display: 'flex', flexDirection: 'column', justifyContent: 'space-between', height: '100%' }}
              >
                <div>
                  <Text strong style={{ display: 'block', marginBottom: '8px', fontSize: '1.1em' }}>{bt.display_name}</Text>
                  <Paragraph type="secondary" style={{ fontSize: '0.9em', marginBottom: 0, flexGrow: 1 }}>
                    {bt.description}
                  </Paragraph>
                </div>
              </Card>
            </Col>
          ))}
        </Row>
      </Form.Item>
    </>
  );
};

export default BenefitTypeStep;