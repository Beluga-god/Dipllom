// src/pages/CaseHistoryPage.tsx
import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  Typography,
  Table,
  Spin,
  Alert,
  Button,
  Input,
  Row,
  Card,
  Col,
  Tag,
  Tooltip,
  Space,
  Modal,
  message as antdMessage,
  Empty,
} from 'antd';
import {
  HistoryOutlined,
  SyncOutlined,
  SearchOutlined,
  DownloadOutlined,
  EyeOutlined,
  FilePdfOutlined,
  FileWordOutlined,
  DeleteOutlined,
  ExclamationCircleFilled,
  GiftOutlined,
} from '@ant-design/icons';
import { Link } from 'react-router-dom';
import { getCaseHistory, downloadCaseDocument, deleteCase } from '../services/apiClient';
import type { CaseHistoryEntry, ApiError, PersonalData, DocumentFormat } from '../types';
import dayjs from 'dayjs';
import { useAuth } from '../contexts/AuthContext';

const { Title, Text } = Typography;
const { Search } = Input;
const { confirm } = Modal;

const ITEMS_PER_PAGE = 10;

// Маппинг ID типа льготы в читаемое название
const getBenefitTypeDisplayName = (benefitTypeId: string): string => {
  const benefitTypeMap: Record<string, string> = {
    'monthly_payment': 'Ежемесячная выплата',
    'housing_benefits': 'Жилищные льготы',
    'medical_support': 'Медицинская помощь',
    'educational_benefits': 'Образовательные льготы',
    'tax_benefits': 'Налоговые льготы',
    'land_benefits': 'Земельный участок',
  };
  return benefitTypeMap[benefitTypeId] || benefitTypeId;
};

const CaseHistoryPage: React.FC = () => {
  const { user } = useAuth();
  const [historyData, setHistoryData] = useState<CaseHistoryEntry[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState<string>('');

  const [currentPage, setCurrentPage] = useState<number>(1);
  const [totalItems, setTotalItems] = useState<number>(0);

  const fetchHistory = useCallback(async (page: number, currentSearchTerm: string) => {
    setLoading(true);
    setError(null);
    try {
      const data = await getCaseHistory(0, 100);
      setHistoryData(data);
    } catch (err) {
      const apiErr = err as ApiError;
      setError(apiErr.message || 'Не удалось загрузить историю обращений.');
      console.error('Error fetching case history:', apiErr);
      setHistoryData([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchHistory(currentPage, searchTerm);
  }, [fetchHistory, currentPage]);

  const handleSearch = (value: string) => {
    setSearchTerm(value);
    setCurrentPage(1);
  };

  const handleTableChange = (pagination: any) => {
    setCurrentPage(pagination.current);
  };

  const handleDownload = async (caseId: number, format: DocumentFormat) => {
    const key = `download-${caseId}-${format}`;
    antdMessage.loading({ content: `Загрузка ${format.toUpperCase()} для обращения #${caseId}...`, key, duration: 0 });

    try {
      const blob = await downloadCaseDocument(caseId, format);
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      const filename = `svo_case_${caseId}.${format}`;
      link.setAttribute('download', filename);
      document.body.appendChild(link);
      link.click();
      link.parentNode?.removeChild(link);
      window.URL.revokeObjectURL(url);
      antdMessage.success({ content: `Файл ${filename} успешно скачан.`, key, duration: 3 });
    } catch (err) {
      const apiErr = err as ApiError;
      console.error('Download error:', apiErr);
      antdMessage.error({ content: `Ошибка скачивания: ${apiErr.message}`, key, duration: 5 });
    }
  };

  const showDeleteConfirm = (caseId: number) => {
    confirm({
      title: 'Вы уверены, что хотите удалить это обращение?',
      icon: <ExclamationCircleFilled />,
      content: `Обращение #${caseId} будет удалено без возможности восстановления.`,
      okText: 'Да, удалить',
      okType: 'danger',
      cancelText: 'Отмена',
      onOk: async () => {
        try {
          antdMessage.loading({ content: `Удаление обращения #${caseId}...`, key: `delete-${caseId}` });
          await deleteCase(caseId);
          antdMessage.success({ content: `Обращение #${caseId} успешно удалено.`, key: `delete-${caseId}` });
          fetchHistory(currentPage, searchTerm);
        } catch (err) {
          const apiErr = err as ApiError;
          console.error('Delete error:', apiErr);
          antdMessage.error({ content: `Ошибка удаления: ${apiErr.message}`, key: `delete-${caseId}`, duration: 5 });
        }
      },
    });
  };

  const filteredData = useMemo(() => {
    if (!searchTerm) {
      return historyData;
    }
    const lowerSearchTerm = searchTerm.toLowerCase();
    return historyData.filter(entry => {
      const fio = entry.personal_data ?
        `${entry.personal_data.last_name || ''} ${entry.personal_data.first_name || ''} ${entry.personal_data.middle_name || ''}`.toLowerCase() : '';
      const snils = entry.personal_data?.snils?.replace(/\D/g, '') || '';
      const benefitTypeDisplay = getBenefitTypeDisplayName(entry.benefit_type).toLowerCase();

      return (
        entry.id.toString().includes(lowerSearchTerm) ||
        fio.includes(lowerSearchTerm) ||
        (snils && snils.includes(lowerSearchTerm.replace(/\D/g, ''))) ||
        benefitTypeDisplay.includes(lowerSearchTerm) ||
        entry.benefit_type.toLowerCase().includes(lowerSearchTerm) ||
        entry.final_status.toLowerCase().includes(lowerSearchTerm)
      );
    });
  }, [historyData, searchTerm]);

  const columns = [
    {
      title: 'ID Обращения',
      dataIndex: 'id',
      key: 'id',
      sorter: (a: CaseHistoryEntry, b: CaseHistoryEntry) => a.id - b.id,
      render: (id: number) => <Link to={`/history/${id}`}>{id}</Link>,
    },
    {
      title: 'Дата создания',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (date: string) => dayjs(date).format('DD.MM.YYYY HH:mm'),
      sorter: (a: CaseHistoryEntry, b: CaseHistoryEntry) => dayjs(a.created_at).unix() - dayjs(b.created_at).unix(),
    },
    {
      title: 'ФИО Заявителя',
      key: 'fio',
      render: (_: any, record: CaseHistoryEntry) => {
        const pd = record.personal_data;
        if (!pd) return <Text type="secondary">Нет данных</Text>;
        return `${pd.last_name || ''} ${pd.first_name || ''} ${pd.middle_name || ''}`.trim() || <Text type="secondary">Не указано</Text>;
      },
    },
    {
      title: 'СНИЛС',
      key: 'snils',
      render: (_: any, record: CaseHistoryEntry) => record.personal_data?.snils || <Text type="secondary">Нет данных</Text>,
    },
    {
      title: 'Тип поддержки',
      dataIndex: 'benefit_type',
      key: 'benefit_type',
      render: (benefitType: string) => getBenefitTypeDisplayName(benefitType),
    },
    {
      title: 'Итоговый статус',
      dataIndex: 'final_status',
      key: 'final_status',
      render: (status: string) => {
        let color = 'default';
        if (status.toLowerCase().includes('соответствует')) color = 'success';
        else if (status.toLowerCase().includes('не соответствует')) color = 'error';
        else if (status.toLowerCase().includes('processing')) color = 'processing';
        else if (status.toLowerCase().includes('failed') || status.toLowerCase().includes('error')) color = 'error';
        return <Tag color={color}>{status}</Tag>;
      },
    },
    {
      title: 'Уверенность системы',
      dataIndex: 'rag_confidence',
      key: 'rag_confidence',
      render: (confidence: number | null) => confidence !== null ? `${(confidence * 100).toFixed(1)}%` : <Text type="secondary">-</Text>,
      sorter: (a: CaseHistoryEntry, b: CaseHistoryEntry) => (a.rag_confidence || 0) - (b.rag_confidence || 0),
    },
    {
      title: 'Действия',
      key: 'actions',
      align: 'center' as const,
      render: (_: any, record: CaseHistoryEntry) => (
        <Space size="small">
          <Tooltip title="Просмотреть детали обращения">
            <Link to={`/history/${record.id}`}>
              <Button icon={<EyeOutlined />} size="small" />
            </Link>
          </Tooltip>
          <Tooltip title="Скачать заключение (PDF)">
            <Button
              icon={<FilePdfOutlined />}
              size="small"
              onClick={() => handleDownload(record.id, 'pdf')}
              disabled={record.final_status === "PROCESSING"}
            />
          </Tooltip>
          <Tooltip title="Скачать заключение (DOCX)">
            <Button
              icon={<FileWordOutlined />}
              size="small"
              onClick={() => handleDownload(record.id, 'docx')}
              disabled={record.final_status === "PROCESSING"}
            />
          </Tooltip>
          {(user?.role === 'admin' || user?.role === 'manager') && (
            <Tooltip title="Удалить обращение">
              <Button
                icon={<DeleteOutlined />}
                size="small"
                danger
                onClick={() => showDeleteConfirm(record.id)}
              />
            </Tooltip>
          )}
        </Space>
      ),
    },
  ];

  if (loading && historyData.length === 0) {
    return (
      <div style={{ textAlign: 'center', padding: '50px' }}>
        <Spin size="large" tip="Загрузка истории обращений..." />
      </div>
    );
  }
  
  return (
    <Card>
      <Row justify="space-between" align="middle" style={{ marginBottom: 24 }}>
        <Col>
          <Title level={3} style={{ margin: 0 }}>
            <HistoryOutlined style={{ marginRight: 8 }} />
            История обращений
          </Title>
        </Col>
        <Col>
          <Button icon={<SyncOutlined />} onClick={() => fetchHistory(currentPage, searchTerm)} loading={loading}>
            Обновить
          </Button>
        </Col>
      </Row>

      <Search
        placeholder="Поиск по ID, ФИО, СНИЛС, типу поддержки или статусу..."
        allowClear
        enterButton={<Button icon={<SearchOutlined />}>Поиск</Button>}
        size="large"
        onSearch={handleSearch}
        onChange={(e) => { if(!e.target.value) handleSearch('');}}
        style={{ marginBottom: 24 }}
        loading={loading && searchTerm !== ''}
      />

      {error && (
        <Alert
          message="Ошибка загрузки истории обращений"
          description={error}
          type="error"
          showIcon
          style={{ marginBottom: 24 }}
        />
      )}

      <Table
        columns={columns}
        dataSource={filteredData}
        rowKey="id"
        loading={loading}
        pagination={{
          current: currentPage,
          pageSize: ITEMS_PER_PAGE,
          total: filteredData.length,
          showSizeChanger: true,
          pageSizeOptions: ['10', '20', '50'],
        }}
        onChange={handleTableChange}
        scroll={{ x: 1200 }}
        locale={{ emptyText: <Empty description="Обращения не найдены или соответствуют фильтру."/> }}
      />
    </Card>
  );
};

export default CaseHistoryPage;