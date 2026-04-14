// src/pages/ConfigAndGuidesPage.tsx
import React, { useState, useEffect } from 'react';
import {
  Typography,
  Row,
  Col,
  Select,
  List,
  Card,
  Spin,
  Alert,
  Divider,
  Tag,
  Empty,
  Collapse,
} from 'antd';
import {
  getBenefitTypes,
  getBenefitDocuments,
  getStandardDocumentNames,
} from '../services/apiClient';
import type {
  BenefitTypeInfo,
  DocumentDetail,
  ApiError,
} from '../types';

const { Title, Text, Paragraph } = Typography;
const { Panel } = Collapse;

const ConfigAndGuidesPage: React.FC = () => {
  const [benefitTypes, setBenefitTypes] = useState<BenefitTypeInfo[]>([]);
  const [selectedBenefitTypeId, setSelectedBenefitTypeId] = useState<string | undefined>(undefined);
  const [requiredDocuments, setRequiredDocuments] = useState<DocumentDetail[]>([]);
  const [standardDocNames, setStandardDocNames] = useState<string[]>([]);

  const [loadingTypes, setLoadingTypes] = useState<boolean>(true);
  const [loadingDocs, setLoadingDocs] = useState<boolean>(false);
  const [loadingStandardNames, setLoadingStandardNames] = useState<boolean>(true);

  const [errorTypes, setErrorTypes] = useState<string | null>(null);
  const [errorDocs, setErrorDocs] = useState<string | null>(null);
  const [errorStandardNames, setErrorStandardNames] = useState<string | null>(null);

  // Загрузка типов льгот
  useEffect(() => {
    const fetchTypes = async () => {
      setLoadingTypes(true);
      setErrorTypes(null);
      try {
        const data = await getBenefitTypes();
        setBenefitTypes(data);
        if (data.length > 0) {
          // setSelectedBenefitTypeId(data[0].id); // Автоматически выбираем первый тип (раскомментировать при необходимости)
        }
      } catch (err) {
        const apiErr = err as ApiError;
        setErrorTypes(apiErr.message || 'Не удалось загрузить типы льгот.');
        console.error('Error fetching benefit types:', apiErr);
      } finally {
        setLoadingTypes(false);
      }
    };
    fetchTypes();
  }, []);

  // Загрузка документов для выбранного типа льготы
  useEffect(() => {
    if (selectedBenefitTypeId) {
      const fetchDocs = async () => {
        setLoadingDocs(true);
        setErrorDocs(null);
        setRequiredDocuments([]);
        try {
          const data = await getBenefitDocuments(selectedBenefitTypeId);
          setRequiredDocuments(data);
        } catch (err) {
          const apiErr = err as ApiError;
          setErrorDocs(apiErr.message || 'Не удалось загрузить список документов.');
          console.error('Error fetching benefit documents:', apiErr);
        } finally {
          setLoadingDocs(false);
        }
      };
      fetchDocs();
    } else {
      setRequiredDocuments([]);
    }
  }, [selectedBenefitTypeId]);

  // Загрузка стандартных имен документов
  useEffect(() => {
    const fetchStandardNames = async () => {
      setLoadingStandardNames(true);
      setErrorStandardNames(null);
      try {
        const data = await getStandardDocumentNames();
        setStandardDocNames(data);
      } catch (err) {
        const apiErr = err as ApiError;
        setErrorStandardNames(apiErr.message || 'Не удалось загрузить стандартные имена документов.');
        console.error('Error fetching standard document names:', apiErr);
      } finally {
        setLoadingStandardNames(false);
      }
    };
    fetchStandardNames();
  }, []);

  const handleBenefitTypeChange = (value: string) => {
    setSelectedBenefitTypeId(value);
  };

  return (
    <div style={{ maxWidth: '1200px', margin: '0 auto' }}>
      <Title level={2} style={{ textAlign: 'center', marginBottom: '24px' }}>
        Справочники и Конфигурация Системы
      </Title>

      <Row gutter={[24, 24]}>
        {/* Секция Типы льгот и Документы */}
        <Col xs={24} md={12}>
          <Card title="Типы поддержки и необходимые документы">
            {loadingTypes && <Spin tip="Загрузка типов льгот..." />}
            {errorTypes && <Alert message={errorTypes} type="error" showIcon />}
            {!loadingTypes && !errorTypes && benefitTypes.length > 0 && (
              <>
                <Paragraph>Выберите тип поддержки, чтобы увидеть список необходимых документов:</Paragraph>
                <Select
                  style={{ width: '100%', marginBottom: '16px' }}
                  placeholder="Выберите тип поддержки"
                  onChange={handleBenefitTypeChange}
                  value={selectedBenefitTypeId}
                  loading={loadingTypes}
                  showSearch
                  optionFilterProp="children"
                  filterOption={(input, option) =>
                    (option?.label ?? '').toLowerCase().includes(input.toLowerCase())
                  }
                  options={benefitTypes.map(bt => ({value: bt.id, label: bt.display_name}))}
                />

                {selectedBenefitTypeId && benefitTypes.find(bt => bt.id === selectedBenefitTypeId) && (
                    <Alert
                        type="info"
                        style={{marginBottom: '16px'}}
                        message={<Text strong>{benefitTypes.find(bt => bt.id === selectedBenefitTypeId)?.display_name}</Text>}
                        description={benefitTypes.find(bt => bt.id === selectedBenefitTypeId)?.description}
                    />
                )}

                {loadingDocs && <Spin tip="Загрузка документов..." />}
                {errorDocs && <Alert message={errorDocs} type="error" showIcon />}
                {!loadingDocs && !errorDocs && selectedBenefitTypeId && (
                  requiredDocuments.length > 0 ? (
                    <List
                      itemLayout="vertical"
                      dataSource={requiredDocuments}
                      renderItem={(doc: DocumentDetail) => (
                        <List.Item
                          key={doc.id}
                          extra={ doc.is_critical ? <Tag color="red">Обязательный</Tag> : <Tag color="gold">Желательный</Tag> }
                        >
                          <List.Item.Meta
                            title={<Text strong>{doc.name}</Text>}
                            description={doc.description}
                          />
                          {doc.condition_text && (
                            <Text type="secondary" italic style={{ display: 'block', marginTop: '4px' }}>
                              Условие: {doc.condition_text}
                            </Text>
                          )}
                           {doc.ocr_type && (
                            <Text type="secondary" style={{ display: 'block', marginTop: '4px' }}>
                              Тип для OCR: <Tag>{doc.ocr_type}</Tag>
                            </Text>
                          )}
                           <Text type="secondary" style={{ display: 'block', marginTop: '4px' }}>
                              ID документа: <Text code>{doc.id}</Text>
                            </Text>
                        </List.Item>
                      )}
                    />
                  ) : (
                     selectedBenefitTypeId && <Empty description="Документы для этого типа поддержки не найдены или не требуются." />
                  )
                )}
                {!selectedBenefitTypeId && !loadingDocs && <Empty description="Выберите тип поддержки для просмотра документов." />}
              </>
            )}
             {!loadingTypes && !errorTypes && benefitTypes.length === 0 && (
                <Empty description="Типы поддержки не найдены." />
             )}
          </Card>
        </Col>

        {/* Секция Стандартные имена документов */}
        <Col xs={24} md={12}>
          <Card title="Стандартные наименования документов">
            <Paragraph>
              Это список всех уникальных стандартных названий документов, которые могут быть определены системой,
              например, при OCR "прочих" документов. Используется для выбора `standardized_document_type`
              в `OtherDocumentData`.
            </Paragraph>
            {loadingStandardNames && <Spin tip="Загрузка имен..." />}
            {errorStandardNames && <Alert message={errorStandardNames} type="error" showIcon />}
            {!loadingStandardNames && !errorStandardNames && (
              standardDocNames.length > 0 ? (
                <Collapse accordion bordered={false} defaultActiveKey={['1']}>
                    <Panel header={`Показать ${standardDocNames.length} стандартных наименований`} key="1">
                        <List
                            size="small"
                            bordered
                            dataSource={standardDocNames.sort()}
                            renderItem={(name) => <List.Item>{name}</List.Item>}
                            style={{ maxHeight: '400px', overflowY: 'auto' }}
                        />
                    </Panel>
                </Collapse>

              ) : (
                <Empty description="Стандартные имена документов не найдены." />
              )
            )}
          </Card>
        </Col>
      </Row>
      <Divider style={{marginTop: '32px'}} />
      <Paragraph type="secondary" style={{textAlign: 'center', marginTop: '16px'}}>
        Эта страница предоставляет справочную информацию, получаемую с бэкенда.
        Она полезна для понимания, какие данные ожидает система.
      </Paragraph>
    </div>
  );
};

export default ConfigAndGuidesPage;