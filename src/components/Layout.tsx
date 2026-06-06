import { Outlet, useNavigate, useLocation } from 'react-router-dom'
import { Layout as TLayout, Button, Space } from 'tdesign-react'
import { BrowseIcon, BookIcon } from 'tdesign-icons-react'

const { Header, Content, Footer } = TLayout

export default function Layout() {
  const navigate = useNavigate()
  const location = useLocation()

  const menuItems = [
    { value: '/', label: '项目列表', icon: <BrowseIcon /> },
    { value: '/knowledge', label: '知识库', icon: <BookIcon /> },
  ]

  const isActive = (path: string) => {
    if (path === '/') return location.pathname === '/'
    return location.pathname.startsWith(path)
  }

  return (
    <TLayout style={{ minHeight: '100vh', background: '#f0f2f5' }}>
      <Header style={{
        background: 'linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%)',
        padding: '0 32px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        height: 60,
        boxShadow: '0 2px 12px rgba(0,0,0,0.15)',
        position: 'sticky',
        top: 0,
        zIndex: 100,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 24 }}>
          <span
            style={{
              color: '#fff',
              fontSize: 20,
              fontWeight: 700,
              cursor: 'pointer',
              letterSpacing: 1,
              background: 'linear-gradient(135deg, #a78bfa, #f0abfc)',
              WebkitBackgroundClip: 'text',
              WebkitTextFillColor: 'transparent',
            }}
            onClick={() => navigate('/')}
          >
            📜 小说转剧本
          </span>
          <div style={{ display: 'flex', gap: 4 }}>
            {menuItems.map(item => (
              <Button
                key={item.value}
                variant="text"
                onClick={() => navigate(item.value)}
                style={{
                  color: isActive(item.value) ? '#fff' : 'rgba(255,255,255,0.6)',
                  background: isActive(item.value) ? 'rgba(255,255,255,0.12)' : 'transparent',
                  fontWeight: isActive(item.value) ? 600 : 400,
                  borderRadius: 8,
                  transition: 'all 0.2s',
                }}
              >
                <Space size={6}>
                  {item.icon}
                  {item.label}
                </Space>
              </Button>
            ))}
          </div>
        </div>
        <div style={{ color: 'rgba(255,255,255,0.5)', fontSize: 12 }}>
          AI 辅助剧本创作工具 v1.0
        </div>
      </Header>
      <Content style={{ padding: '28px 32px', maxWidth: 1200, margin: '0 auto', width: '100%' }}>
        <Outlet />
      </Content>
      <Footer style={{ textAlign: 'center', color: '#999', fontSize: 12, padding: '16px 0', background: 'transparent' }}>
        Novel to Script © 2026
      </Footer>
    </TLayout>
  )
}
