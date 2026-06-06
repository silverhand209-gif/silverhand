import { useState, useEffect } from 'react'
import {
  Card, Input, Button, Tag, Textarea, Dialog, MessagePlugin,
  Space, Loading, Collapse
} from 'tdesign-react'
import { SearchIcon, AddIcon, BookIcon, FileIcon, BrowseIcon } from 'tdesign-icons-react'
import { getKnowledgeStats, searchKnowledge, addKnowledge } from '../api'

const { Panel: CollapsePanel } = Collapse

const CATEGORY_COLORS: Record<string, string> = {
  '剧本结构': 'primary',
  '角色塑造': 'success',
  '对白技巧': 'warning',
  '场景设计': 'danger',
  '改编技巧': 'default',
  '格式规范': 'purple',
  '类型剧本': 'cyan',
  '用户添加': 'orange',
}

export default function KnowledgePage() {
  const [stats, setStats] = useState<any>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState<any[]>([])
  const [searching, setSearching] = useState(false)
  const [hasSearched, setHasSearched] = useState(false)
  const [showAdd, setShowAdd] = useState(false)
  const [addTitle, setAddTitle] = useState('')
  const [addContent, setAddContent] = useState('')
  const [addCategory, setAddCategory] = useState('用户添加')
  const [adding, setAdding] = useState(false)

  useEffect(() => {
    loadStats()
  }, [])

  const loadStats = async () => {
    try {
      const res = await getKnowledgeStats()
      setStats(res)
    } catch {
      // ignore
    }
  }

  const handleSearch = async () => {
    if (!searchQuery.trim()) return
    setSearching(true)
    setHasSearched(true)
    try {
      const res = await searchKnowledge(searchQuery, 5)
      setSearchResults(res.documents || [])
    } catch (e: any) {
      MessagePlugin.error('搜索失败')
    } finally {
      setSearching(false)
    }
  }

  const handleAdd = async () => {
    if (!addTitle || !addContent) {
      MessagePlugin.warning('请填写标题和内容')
      return
    }
    setAdding(true)
    try {
      await addKnowledge(addTitle, addContent, addCategory)
      MessagePlugin.success('知识添加成功')
      setShowAdd(false)
      setAddTitle('')
      setAddContent('')
      setAddCategory('用户添加')
      await loadStats()
    } catch (e) {
      MessagePlugin.error('添加失败')
    } finally {
      setAdding(false)
    }
  }

  return (
    <div className="fade-in" style={{ maxWidth: 960, margin: '0 auto' }}>
      {/* 顶部标题区 */}
      <div style={{
        display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start',
        marginBottom: 28, padding: '28px 32px',
        background: 'linear-gradient(135deg, #ffffff 0%, #f8f9ff 100%)',
        borderRadius: 16,
        border: '1px solid #e8ecf4',
        boxShadow: '0 1px 4px rgba(0,0,0,0.04)',
      }}>
        <div>
          <h2 style={{ margin: 0, fontSize: 26, fontWeight: 700, color: '#1a1a2e' }}>剧本知识库</h2>
          <p style={{ margin: '6px 0 0', color: '#888', fontSize: 14 }}>
            RAG 检索增强生成 —— AI 在生成各环节时自动检索相关知识作为参考
          </p>
        </div>
        <Button
          theme="primary"
          size="large"
          icon={<AddIcon />}
          onClick={() => setShowAdd(true)}
          style={{
            background: 'linear-gradient(135deg, #667eea, #764ba2)',
            border: 'none',
            borderRadius: 10,
            fontWeight: 600,
            height: 44,
            padding: '0 28px',
            boxShadow: '0 4px 14px rgba(102, 126, 234, 0.35)',
          }}
        >
          添加知识
        </Button>
      </div>

      {/* 统计卡片 */}
      {stats && (
        <div style={{
          display: 'flex', gap: 16, marginBottom: 24,
        }}>
          <Card style={{
            flex: 1, borderRadius: 14, border: '1px solid #e8ecf4',
            background: 'linear-gradient(135deg, #f0f4ff 0%, #faf5ff 100%)',
          }}>
            <div style={{ textAlign: 'center', padding: '8px 0' }}>
              <div style={{ fontSize: 36, fontWeight: 800, color: '#667eea', lineHeight: 1 }}>{stats.total_documents}</div>
              <div style={{ color: '#888', fontSize: 13, marginTop: 6 }}>知识条目</div>
            </div>
          </Card>
          <Card style={{
            flex: 2, borderRadius: 14, border: '1px solid #e8ecf4',
          }}>
            <div style={{ padding: '4px 0' }}>
              <div style={{ fontWeight: 600, fontSize: 14, marginBottom: 10, color: '#444' }}>涵盖类别</div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                {(stats.categories || []).map((cat: string) => (
                  <Tag key={cat} theme={CATEGORY_COLORS[cat] as any || 'default'} variant="light" style={{ borderRadius: 6, padding: '4px 12px' }}>
                    {cat}
                  </Tag>
                ))}
              </div>
            </div>
          </Card>
        </div>
      )}

      {/* 搜索 */}
      <Card style={{
        borderRadius: 14, border: '1px solid #e8ecf4',
        boxShadow: '0 1px 4px rgba(0,0,0,0.03)',
        marginBottom: 24,
      }}>
        <div style={{ display: 'flex', gap: 10 }}>
          <Input
            value={searchQuery}
            onChange={(v) => setSearchQuery(v as string)}
            placeholder="搜索剧本创作知识，如「三幕剧结构」「对白技巧」「角色弧光」..."
            onEnter={handleSearch}
            style={{ flex: 1 }}
          />
          <Button
            theme="primary"
            icon={<SearchIcon />}
            onClick={handleSearch}
            loading={searching}
            style={{
              borderRadius: 10, fontWeight: 500, minWidth: 88,
              background: 'linear-gradient(135deg, #667eea, #764ba2)', border: 'none',
            }}
          >
            搜索
          </Button>
        </div>

        {/* 搜索结果 */}
        {searchResults.length > 0 && (
          <div style={{ marginTop: 20 }}>
            <div style={{
              fontWeight: 600, fontSize: 15, marginBottom: 12, color: '#1a1a2e',
              display: 'flex', alignItems: 'center', gap: 8,
            }}>
              <SearchIcon style={{ color: '#667eea' }} />
              搜索结果 ({searchResults.length} 条)
            </div>
            <Collapse expandIconPlacement="right" style={{ borderRadius: 10 }}>
              {searchResults.map((doc: any, idx: number) => (
                <CollapsePanel
                  key={doc.id || idx}
                  header={
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                      <BookIcon style={{ color: '#667eea' }} />
                      <span style={{ fontWeight: 500 }}>{doc.metadata?.title || '知识条目'}</span>
                      <Tag
                        theme={CATEGORY_COLORS[doc.metadata?.category] as any || 'default'}
                        variant="light"
                        size="small"
                        style={{ borderRadius: 6 }}
                      >
                        {doc.metadata?.category || '通用'}
                      </Tag>
                      {doc.distance !== undefined && (
                        <span style={{ color: '#bbb', fontSize: 12, marginLeft: 'auto' }}>
                          相关度: {Math.round((1 - doc.distance) * 100)}%
                        </span>
                      )}
                    </div>
                  }
                >
                  <div style={{
                    whiteSpace: 'pre-wrap', fontSize: 14, lineHeight: 1.9,
                    color: '#444', padding: '4px 0',
                  }}>
                    {doc.content}
                  </div>
                </CollapsePanel>
              ))}
            </Collapse>
          </div>
        )}

        {hasSearched && searchResults.length === 0 && !searching && (
          <div style={{
            textAlign: 'center', padding: '32px 0 16px', color: '#bbb',
          }}>
            <BrowseIcon style={{ fontSize: 32, marginBottom: 8 }} />
            <div>未找到相关知识，试试其他关键词或添加新知识</div>
          </div>
        )}
      </Card>

      {/* 添加知识对话框 */}
      <Dialog
        header={
          <div style={{ fontSize: 18, fontWeight: 600, color: '#1a1a2e' }}>
            <BookIcon style={{ marginRight: 8, color: '#667eea' }} />
            添加剧本知识
          </div>
        }
        visible={showAdd}
        onClose={() => setShowAdd(false)}
        onConfirm={handleAdd}
        confirmBtn={{
          loading: adding,
          content: '添加到知识库',
          style: {
            background: 'linear-gradient(135deg, #667eea, #764ba2)',
            border: 'none', borderRadius: 8, fontWeight: 600,
          },
        }}
        cancelBtn={{ content: '取消', variant: 'outline', style: { borderRadius: 8 } }}
        width={540}
        destroyOnClose
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: 18, marginTop: 4 }}>
          <div>
            <label style={{ display: 'block', marginBottom: 6, fontWeight: 600, fontSize: 14, color: '#333' }}>知识标题</label>
            <Input
              value={addTitle}
              onChange={(v) => setAddTitle(v as string)}
              placeholder="如：悬疑剧本反转技巧、古装对白注意事项..."
            />
          </div>
          <div>
            <label style={{ display: 'block', marginBottom: 6, fontWeight: 600, fontSize: 14, color: '#333' }}>所属类别</label>
            <Input
              value={addCategory}
              onChange={(v) => setAddCategory(v as string)}
              placeholder="如：对白技巧、场景设计、角色塑造..."
            />
          </div>
          <div>
            <label style={{ display: 'block', marginBottom: 6, fontWeight: 600, fontSize: 14, color: '#333' }}>知识内容</label>
            <Textarea
              value={addContent}
              onChange={(v) => setAddContent(v as string)}
              placeholder="请输入详细的剧本创作知识内容，AI 生成剧本时会自动检索匹配的相关知识作为参考..."
              autosize={{ minRows: 5, maxRows: 12 }}
            />
          </div>
        </div>
      </Dialog>
    </div>
  )
}
