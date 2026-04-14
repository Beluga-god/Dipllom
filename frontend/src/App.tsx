// src/App.tsx
import React from 'react';
import { Routes, Route, Link, useLocation, useNavigate, Navigate } from 'react-router-dom';
import { Layout, Menu, Typography, theme as antdTheme, Breadcrumb, Button, Avatar, Dropdown, Spin, Space, Alert, Result } from 'antd';
import {
  HistoryOutlined,
  QuestionCircleOutlined,
  HomeOutlined,
  ExperimentOutlined,
  ApiOutlined,
  LoginOutlined,
  LogoutOutlined,
  UserOutlined,
  FileTextOutlined,
  GiftOutlined,
} from '@ant-design/icons';

import HomePage from './pages/HomePage';
import CaseHistoryPage from './pages/CaseHistoryPage';
import OcrTasksPage from './pages/OcrTasksPage';
import SystemHealthPage from './pages/SystemHealthPage';
import ConfigAndGuidesPage from './pages/ConfigAndGuidesPage';
import CaseDetailPage from './pages/CaseDetailPage';
import RagDocumentsPage from './pages/RagDocumentsPage';
import NotFoundPage from './pages/NotFoundPage';
import LoginPage from './pages/LoginPage';
import ProtectedRoute from './components/ProtectedRoute';
import { AuthProvider, useAuth } from './contexts/AuthContext';

const { Header, Content, Footer } = Layout;
const { Text } = Typography;

interface MenuItemType {
  key: string;
  icon: React.ReactNode;
  label: React.ReactNode;
  roles: string[];
  children?: MenuItemType[];
}

const AccessDeniedPage: React.FC<{ message?: string, onNavigate: () => void }> = ({ message, onNavigate }) => (
  <Result
    status="403"
    title="403 - Доступ запрещен"
    subTitle={message || "Извините, у вас нет прав для доступа к этой странице."}
    extra={<Button type="primary" onClick={onNavigate}>На главную</Button>}
  />
);

const AppContent: React.FC = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const { token: { colorBgContainer, borderRadiusLG } } = antdTheme.useToken();
  const { isAuthenticated, user, logout, isLoading } = useAuth();

  const commonMenuItems: MenuItemType[] = [
    {
      key: '/ocr-tasks',
      icon: <ExperimentOutlined />,
      label: <Link to="/ocr-tasks">Статистика OCR</Link>,
      roles: ['admin', 'manager'],
    },
    {
      key: '/rag-documents',
      icon: <FileTextOutlined />,
      label: <Link to="/rag-documents">База знаний</Link>,
      roles: ['admin'],
    },
    {
      key: '/guides',
      icon: <QuestionCircleOutlined />,
      label: <Link to="/guides">Справочники</Link>,
      roles: ['admin', 'manager'],
    },
    {
      key: '/health',
      icon: <ApiOutlined />,
      label: <Link to="/health">Состояние системы</Link>,
      roles: ['admin', 'manager'],
    },
  ];

  const managerMenuItems: MenuItemType[] = [
    {
      key: '/',
      icon: <GiftOutlined />,
      label: <Link to="/">Новое обращение</Link>,
      roles: ['manager'],
    },
    {
      key: '/history',
      icon: <HistoryOutlined />,
      label: <Link to="/history">История обращений</Link>,
      roles: ['manager'],
    },
  ];

  let visibleMenuItems: MenuItemType[] = [];
  if (user?.role === 'admin') {
    visibleMenuItems = commonMenuItems.filter(item => item.roles.includes('admin'));
  } else if (user?.role === 'manager') {
    visibleMenuItems = [
      ...managerMenuItems.filter(item => item.roles.includes('manager')),
      ...commonMenuItems.filter(item => item.roles.includes('manager') && !managerMenuItems.find(mItem => mItem.key === item.key))
    ];
  } else {
    visibleMenuItems = [];
  }

  if (user?.role === 'admin') {
    const adminOrder = ['/ocr-tasks', '/rag-documents', '/guides', '/health'];
    visibleMenuItems.sort((a, b) => adminOrder.indexOf(a.key) - adminOrder.indexOf(b.key));
  }

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const userMenuItems = [
    {
        key: 'username',
        label: <Text strong>Пользователь: {user?.username || ''} ({user?.role || ''})</Text>,
        disabled: true,
        icon: <UserOutlined />
    },
    {
        type: 'divider' as const,
    },
    {
      key: 'logout',
      icon: <LogoutOutlined />,
      label: 'Выйти',
      onClick: handleLogout,
    },
  ];

  const breadcrumbNameMap: Record<string, string> = {
    '/': 'Новое обращение',
    '/history': 'История обращений',
    '/history/:caseId': 'Детали обращения',
    '/ocr-tasks': 'Статистика OCR задач',
    '/rag-documents': 'База знаний',
    '/guides': 'Справочники и конфигурация',
    '/health': 'Состояние системы',
    '/login': 'Вход в систему'
  };

  const pathSnippets = location.pathname.split('/').filter(i => i);
  const extraBreadcrumbItems = pathSnippets.map((_, index) => {
    const url = `/${pathSnippets.slice(0, index + 1).join('/')}`;
    let name = breadcrumbNameMap[url];
    if (!name && url.startsWith('/history/')) {
        name = `Обращение #${pathSnippets[index]}`;
    }

    return (
      <Breadcrumb.Item key={url}>
        {index === pathSnippets.length -1 || !name ? (
          <span>{name || pathSnippets[index]}</span>
        ) : (
          <Link to={url}>{name}</Link>
        )}
      </Breadcrumb.Item>
    );
  });

  const breadcrumbItems = [
    <Breadcrumb.Item key="home">
      { user?.role !== 'admin' && <Link to="/"><GiftOutlined /></Link> }
      { user?.role === 'admin' && visibleMenuItems.length > 0 && 
         <Link to={visibleMenuItems[0].key}><HomeOutlined /></Link>
      }
    </Breadcrumb.Item>,
  ].concat(extraBreadcrumbItems);

  let selectedMenuKey = location.pathname;
  const pathSegments = location.pathname.split('/').filter(Boolean);
  if (pathSegments.length > 1 && visibleMenuItems.some(item => item.key === `/${pathSegments[0]}`)) {
    selectedMenuKey = `/${pathSegments[0]}`;
  } else if (pathSegments.length === 0 && location.pathname === '/' && visibleMenuItems.some(item => item.key === '/')) {
    selectedMenuKey = '/';
  } else if (!visibleMenuItems.some(item => item.key === selectedMenuKey) && pathSegments.length > 0) {
    const parentKey = `/${pathSegments[0]}`;
    if (visibleMenuItems.some(item => item.key === parentKey)) {
        selectedMenuKey = parentKey;
    }
  } else if (location.pathname === '/login') {
      selectedMenuKey = '';
  }

  const AdminRouteGuard: React.FC<{ children: JSX.Element, to: string }> = ({ children, to }) => {
    if (user?.role === 'admin') {
        const firstAdminPage = visibleMenuItems.find(item => item.roles.includes('admin'))?.key || '/ocr-tasks';
        return <AccessDeniedPage onNavigate={() => navigate(firstAdminPage)} />;
    }
    return children;
  };

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Header style={{ display: 'flex', alignItems: 'center', padding: '0 24px', background: colorBgContainer, justifyContent: 'space-between' }}>
        <Space>
            <div style={{ height: 32, marginRight: 24, background: 'rgba(0, 0, 0, 0.1)', textAlign: 'center', lineHeight: '32px', color: '#1677ff', borderRadius: '4px', padding: '0 10px', fontWeight: 'bold' }}>
                SVO-AI
            </div>
            {isAuthenticated && (
                 <Menu
                    theme="light"
                    mode="horizontal"
                    selectedKeys={[selectedMenuKey]}
                    items={visibleMenuItems}
                    style={{ flex: 1, minWidth: 0, borderBottom: 'none' }}
                    overflowedIndicator={<UserOutlined />}
                />
            )}
        </Space>
        
        <Space>
            {isLoading ? (
                <Spin size="small" />
            ) : isAuthenticated && user ? (
                <Dropdown menu={{ items: userMenuItems }} placement="bottomRight">
                    <Button type="text" style={{height: 'auto'}}>
                        <Space>
                             <Avatar icon={<UserOutlined />} size="small" style={{backgroundColor: '#1890ff'}}/>
                             <Text style={{color: 'rgba(0, 0, 0, 0.85)'}}>{user.username}</Text>
                        </Space>
                    </Button>
                </Dropdown>
            ) : (
                location.pathname !== '/login' && (
                    <Button icon={<LoginOutlined />} onClick={() => navigate('/login')}>
                        Войти
                    </Button>
                )
            )}
        </Space>
      </Header>
      <Content style={{ margin: '0 16px' }}>
        { location.pathname !== '/login' && isAuthenticated && (
            <Breadcrumb style={{ margin: '16px 0' }}>
                {breadcrumbItems}
            </Breadcrumb>
        )}
        <div
          style={{
            padding: location.pathname === '/login' ? 0 : 24,
            minHeight: 360,
            background: location.pathname === '/login' ? 'transparent' : colorBgContainer,
            borderRadius: location.pathname === '/login' ? 0 : borderRadiusLG,
          }}
        >
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/" element={
              <ProtectedRoute>
                <AdminRouteGuard to="/">
                  <HomePage />
                </AdminRouteGuard>
              </ProtectedRoute>
            } />
            <Route path="/history" element={
              <ProtectedRoute>
                <AdminRouteGuard to="/history">
                  <CaseHistoryPage />
                </AdminRouteGuard>
              </ProtectedRoute>
            } />
            <Route path="/history/:caseId" element={
              <ProtectedRoute>
                <AdminRouteGuard to="/history/:caseId">
                  <CaseDetailPage />
                </AdminRouteGuard>
              </ProtectedRoute>
            } />
            <Route path="/ocr-tasks" element={<ProtectedRoute><OcrTasksPage /></ProtectedRoute>} />
            <Route path="/rag-documents" element={<ProtectedRoute><RagDocumentsPage /></ProtectedRoute>} />
            <Route path="/guides" element={<ProtectedRoute><ConfigAndGuidesPage /></ProtectedRoute>} />
            <Route path="/health" element={<ProtectedRoute><SystemHealthPage /></ProtectedRoute>} />
            <Route path="*" element={<NotFoundPage />} />
          </Routes>
        </div>
      </Content>
      <Footer style={{ textAlign: 'center' }}>
        Система поддержки участников СВО (SVO-AI) ©{new Date().getFullYear()}
      </Footer>
    </Layout>
  );
}

function App() {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  );
}

export default App;