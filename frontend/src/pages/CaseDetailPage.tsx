// src/pages/CaseDetailPage.tsx
import React, { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { Typography, Spin, Alert, Descriptions, Tag, Collapse, Button, Space, Modal, message, List, Card, Divider } from 'antd';
import { getFullCaseData, downloadCaseDocument } from '../services/apiClient';
import { FullCaseData, ApiError, WorkBookRecordEntry, OtherDocumentData, PersonalData, DisabilityInfo, WorkExperience } from '../types';
import { ArrowLeftOutlined, DownloadOutlined, InfoCircleOutlined, UserOutlined, IdcardOutlined, SolutionOutlined, PaperClipOutlined, WarningOutlined, ExclamationCircleFilled, ScheduleOutlined, GiftOutlined } from '@ant-design/icons';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import 'katex/dist/katex.min.css';

const { Title, Text, Paragraph } = Typography;
const { Panel } = Collapse;
const { confirm } = Modal;

const CaseDetailPage: React.FC = () => {
  const { caseId } = useParams<{ caseId: string }>();
  const [caseData, setCaseData] = useState<FullCaseData | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [downloading, setDownloading] = useState<{'pdf': boolean, 'docx': boolean}>({ pdf: false, docx: false });

  useEffect(() => {
    if (caseId) {
      const fetchCaseData = async () => {
        setLoading(true);
        try {
          const id = parseInt(caseId, 10);
          if (isNaN(id)) {
            throw new Error('Некорректный ID обращения.');
          }
          const data = await getFullCaseData(id);
          setCaseData(data);
          setError(null);
        } catch (err) {
          const apiErr = err as ApiError;
          setError(apiErr.message || `Не удалось загрузить данные обращения #${caseId}.`);
          console.error(`Fetch Case Data Error (ID: ${caseId}):`, apiErr);
        }
        setLoading(false);
      };
      fetchCaseData();
    }
  }, [caseId]);

  const handleDownload = async (format: 'pdf' | 'docx') => {
    if (!caseId || !caseData) return;

    confirm({
        title: `Подтвердите загрузку документа`, 
        icon: <ExclamationCircleFilled />, 
        content: `Вы уверены, что хотите скачать документ по обращению #${caseId} в формате ${format.toUpperCase()}?`, 
        okText: 'Да, скачать', 
        cancelText: 'Отмена', 
        async onOk() {
            setDownloading(prev => ({ ...prev, [format]: true }));
            try {
              message.loading({ content: `Подготовка ${format.toUpperCase()} документа...`, key: `download-${format}` });
              const blob = await downloadCaseDocument(parseInt(caseId, 10), format);
              const url = window.URL.createObjectURL(blob);
              const a = document.createElement('a');
              a.href = url;
              a.download = `svo_case_${caseId}_document.${format}`;
              document.body.appendChild(a);
              a.click();
              a.remove();
              window.URL.revokeObjectURL(url);
              message.success({ content: `Документ (${format.toUpperCase()}) успешно загружен!`, key: `download-${format}`, duration: 3 });
            } catch (err) {
              const apiErr = err as ApiError;
              console.error("Download error:", apiErr);
              message.error({ content: apiErr.message || `Не удалось скачать документ (${format.toUpperCase()}).`, key: `download-${format}`, duration: 4 });
            } finally {
              setDownloading(prev => ({ ...prev, [format]: false }));
            }
        }
    });
  };

  if (loading) {
    return <div style={{ textAlign: 'center', margin: '20px 0' }}><Spin size="large" tip={`Загрузка данных обращения #${caseId}...`} /></div>;
  }

  if (error) {
    return <Alert message="Ошибка загрузки" description={error} type="error" showIcon />;
  }

  if (!caseData) {
    return <Alert message="Данные не найдены" description={`Не удалось найти информацию по обращению #${caseId}.`} type="warning" showIcon />;
  }

  const renderStatusTag = (status: string | null) => {
    if (!status) return <Tag color="default">Неизвестно</Tag>;
    switch (status) {
      case 'СООТВЕТСТВУЕТ': case 'COMPLETED': return <Tag color="success">{status === 'COMPLETED' ? 'ЗАВЕРШЕНО' : status}</Tag>;
      case 'НЕ СООТВЕТСТВУЕТ': return <Tag color="warning">{status}</Tag>;
      case 'PROCESSING': return <Tag color="processing">В ОБРАБОТКЕ</Tag>;
      case 'ERROR_PROCESSING': case 'FAILED': return <Tag color="error">{status}</Tag>;
      default: return <Tag color="blue">{status}</Tag>;
    }
  };

  // Функция для получения отображаемого названия типа льготы
  const getBenefitTypeDisplayName = (benefitTypeId: string): string => {
    // Здесь можно добавить маппинг ID в читаемые названия
    const benefitTypeMap: Record<string, string> = {
      'monthly_payment': 'Ежемесячная денежная выплата',
      'housing_benefits': 'Жилищные льготы',
      'medical_support': 'Медицинская помощь',
      'educational_benefits': 'Образовательные льготы',
      'tax_benefits': 'Налоговые льготы',
      'land_benefits': 'Земельный участок',
    };
    return benefitTypeMap[benefitTypeId] || benefitTypeId;
  };

  return (
    <div>
      <Button type="link" icon={<ArrowLeftOutlined />} onClick={() => window.history.back()} style={{ marginBottom: '16px', paddingLeft: 0 }}>
        Назад к списку
      </Button>
      <Title level={2} style={{ marginBottom: '5px' }}>Детали обращения <Text type="secondary">#{caseData.id}</Text></Title>
      <Paragraph>
        <Text strong><GiftOutlined /> Тип поддержки:</Text> {getBenefitTypeDisplayName(caseData.benefit_type)} <br />
        <Text strong>Статус:</Text> {renderStatusTag(caseData.final_status)} <br />
        <Text strong>Создано:</Text> {new Date(caseData.created_at).toLocaleString()} <br />
        {caseData.updated_at && <><Text strong>Обновлено:</Text> {new Date(caseData.updated_at).toLocaleString()} <br /></>}
        {typeof caseData.rag_confidence === 'number' && <><Text strong>Уверенность системы:</Text> {(caseData.rag_confidence * 100).toFixed(1)}%</>}
      </Paragraph>

      {caseData.final_explanation && (
        <Collapse defaultActiveKey={['final_explanation_panel']} style={{marginBottom: '20px'}}>
          <Panel header={<><InfoCircleOutlined style={{marginRight: 8}} />Итоговое заключение</>} key="final_explanation_panel">
            {caseData.final_explanation.split(/\n(?=## )/).map((section, index) => {
              let cardTitle = null;
              let cardContent = section;
              const h2Match = section.match(/^## (.*)(?:\n|$)/);

              if (h2Match && h2Match[1]) {
                cardTitle = h2Match[1].trim();
                cardContent = section.substring(h2Match[0].length);
                if (cardContent.startsWith('\n')) {
                  cardContent = cardContent.substring(1);
                }
              }

              return (
                <Card 
                  key={index} 
                  title={cardTitle}
                  style={{ 
                    marginBottom: '16px', 
                    background: '#fff', 
                    boxShadow: '0 2px 8px rgba(0, 0, 0, 0.09)'
                  }}
                  bordered={true}
                >
                  <ReactMarkdown
                    remarkPlugins={[remarkGfm, remarkMath]}
                    rehypePlugins={[rehypeKatex]}
                    components={{
                      h2: ({node, ...props}) => (
                        <>
                          <h2 {...props} style={{ marginBottom: '16px' }} />
                          <Divider />
                        </>
                      ),
                      h3: ({node, ...props}) => (
                        <>
                          <h3 {...props} style={{ marginTop: '20px', marginBottom: '12px' }} />
                          <Divider dashed />
                        </>
                      ),
                    }}
                  >
                    {cardContent || ''}
                  </ReactMarkdown>
                </Card>
              );
            })}
          </Panel>
        </Collapse>
      )}

      <Space style={{marginBottom: '20px'}}>
          <Button icon={<DownloadOutlined />} onClick={() => handleDownload('pdf')} loading={downloading.pdf} disabled={downloading.docx}>
              Скачать заключение (PDF)
          </Button>
          <Button icon={<DownloadOutlined />} onClick={() => handleDownload('docx')} loading={downloading.docx} disabled={downloading.pdf}>
              Скачать заключение (DOCX)
          </Button>
      </Space>

      <Collapse defaultActiveKey={['personal']} accordion>
        {caseData.personal_data && (
          <Panel header={<Text strong><UserOutlined /> Персональные данные</Text>} key="personal">
            <Descriptions bordered column={1} size="small">
              <Descriptions.Item label="ФИО">{[caseData.personal_data.last_name, caseData.personal_data.first_name, caseData.personal_data.middle_name].filter(Boolean).join(' ')}</Descriptions.Item>
              <Descriptions.Item label="Дата рождения">{caseData.personal_data.birth_date}</Descriptions.Item>
              <Descriptions.Item label="СНИЛС">{caseData.personal_data.snils}</Descriptions.Item>
              <Descriptions.Item label="Пол">{caseData.personal_data.gender}</Descriptions.Item>
              <Descriptions.Item label="Гражданство">{caseData.personal_data.citizenship}</Descriptions.Item>
              <Descriptions.Item label="Иждивенцы">{caseData.personal_data.dependents ?? '0'}</Descriptions.Item>
              {caseData.personal_data.name_change_info && (
                  <Descriptions.Item label="Смена ФИО">
                      Прежн. ФИО: {caseData.personal_data.name_change_info.old_full_name || '-'}, 
                      Дата: {caseData.personal_data.name_change_info.date_changed || '-'}
                  </Descriptions.Item>
              )}
            </Descriptions>
          </Panel>
        )}

        {caseData.disability && (
          <Panel header={<Text strong><IdcardOutlined /> Информация об инвалидности</Text>} key="disability">
            <Descriptions bordered column={1} size="small">
              <Descriptions.Item label="Группа">{caseData.disability.group}</Descriptions.Item>
              <Descriptions.Item label="Дата установления">{caseData.disability.date}</Descriptions.Item>
              <Descriptions.Item label="Номер справки МСЭ">{caseData.disability.cert_number || '-'}</Descriptions.Item>
            </Descriptions>
          </Panel>
        )}

        {caseData.work_experience && caseData.work_experience.records && caseData.work_experience.records.length > 0 && (
          <Panel header={<Text strong><SolutionOutlined /> Трудовой стаж</Text>} key="work">
            <Descriptions bordered column={1} size="small" style={{ marginBottom: '16px' }}>
                 <Descriptions.Item label="Общий страховой стаж (лет)">{caseData.work_experience.calculated_total_years ?? '-'}</Descriptions.Item>
            </Descriptions>
            <Title level={5} style={{marginTop: '16px', marginBottom: '8px'}}>Периоды работы:</Title>
            <List
                size="small"
                bordered
                dataSource={caseData.work_experience.records}
                renderItem={(item: WorkBookRecordEntry) => (
                    <List.Item>
                        <List.Item.Meta
                            title={`${item.organization} (${item.position})`}
                            description={`Период: ${item.date_in} - ${item.date_out}`}
                        />
                        {item.special_conditions && <Tag color="orange">Особые условия</Tag>}
                    </List.Item>
                )}
            />
            {caseData.work_experience.raw_events && caseData.work_experience.raw_events.length > 0 && (
                <Collapse ghost style={{ marginTop: '16px' }}>
                    <Panel header="Показать сырые события из OCR" key="raw_events">
                        <List
                            size="small"
                            bordered
                            dataSource={caseData.work_experience.raw_events}
                            renderItem={(event, index) => (
                                <List.Item>
                                    <Text>
                                        <small>({event.date}) [{event.event_type}]</small> {event.raw_text}
                                    </Text>
                                </List.Item>
                            )}
                        />
                    </Panel>
                </Collapse>
            )}
          </Panel>
        )}

        <Panel header={<Text strong><PaperClipOutlined /> Дополнительная информация</Text>} key="additional">
          <Descriptions bordered column={1} size="small">
            <Descriptions.Item label="Пенсионные баллы (ИПК)">{caseData.pension_points ?? '-'}</Descriptions.Item>
            <Descriptions.Item label="Заявленные льготы">{caseData.benefits && caseData.benefits.length > 0 ? caseData.benefits.join(', ') : '-'}</Descriptions.Item>
            <Descriptions.Item label="Представленные документы">{caseData.submitted_documents && caseData.submitted_documents.length > 0 ? caseData.submitted_documents.join(', ') : '-'}</Descriptions.Item>
            <Descriptions.Item label="Наличие некорректных документов">{caseData.has_incorrect_document ? <Tag color="error">Да</Tag> : <Tag color="success">Нет</Tag>}</Descriptions.Item>
          </Descriptions>
          {caseData.other_documents_extracted_data && caseData.other_documents_extracted_data.length > 0 && (
            <>
                <Title level={5} style={{marginTop: '16px', marginBottom: '8px'}}>Данные из прочих загруженных документов:</Title>
                <Collapse ghost>
                    {caseData.other_documents_extracted_data.map((doc: OtherDocumentData, index) => (
                        <Panel header={`Документ ${index + 1}: ${doc.identified_document_type || 'Неизвестный тип'} (станд.: ${doc.standardized_document_type || '-'})`} key={`other_doc_${index}`}>
                            <Descriptions bordered column={1} size="small">
                                {doc.extracted_fields && Object.entries(doc.extracted_fields).map(([key, value]) => (
                                    <Descriptions.Item label={key} key={key}>{String(value)}</Descriptions.Item>
                                ))}
                                <Descriptions.Item label="Оценка LLM (Vision)">{doc.multimodal_assessment || '-'}</Descriptions.Item>
                                <Descriptions.Item label="Анализ LLM (Text)">{doc.text_llm_reasoning || '-'}</Descriptions.Item>
                            </Descriptions>
                        </Panel>
                    ))}
                </Collapse>
            </>
          )}
        </Panel>
        
        {caseData.errors && caseData.errors.length > 0 && (
            <Panel header={<Text strong color="red"><WarningOutlined /> Ошибки обработки</Text>} key="errors_case">
                <List
                    size="small"
                    bordered
                    dataSource={caseData.errors}
                    renderItem={(errorItem: any, _index: number) => (
                        <List.Item>
                            <pre style={{whiteSpace: 'pre-wrap', wordBreak: 'break-all'}}>{JSON.stringify(errorItem, null, 2)}</pre>
                        </List.Item>
                    )}
                />
            </Panel>
        )}
      </Collapse>

    </div>
  );
};

export default CaseDetailPage;