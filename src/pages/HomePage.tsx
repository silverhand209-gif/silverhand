import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Card, Button, Input, Dialog, Form, Select, MessagePlugin,
  Tag, Loading, Popconfirm, Empty, Space
} from 'tdesign-react'
import { AddIcon, DeleteIcon, TimeIcon, FileIcon } from 'tdesign-icons-react'
import { listProjects, createProject, deleteProject } from '../api'
import { useAppStore } from '../store'

const { FormItem } = Form

export default function HomePage() {
  const navigate = useNavigate()
  const { projects, setProjects } = useAppStore()
  const [loading, setLoading] = useState(true)
  const [showCreate, setShowCreate] = useState(false)
  const [creating, setCreating] = useState(false)
  const [form] = Form.useForm()

  useEffect(() => {
    loadProjects()
  }, [])

  const loadProjects = async () => {
    setLoading(true)
    try {
      const res = await listProjects()
      setProjects(res.projects || [])
    } catch (e: any) {
      if (e.code === 'ECONNREFUSED' || e.code === 'ERR_NETWORK') {
        MessagePlugin.error('无法连接到后端服务，请确认后端已启动')
      } else if (e.response?.status) {
        MessagePlugin.error(`加载项目列表失败: ${e.response.data?.detail || e.message}`)
      } else {
        setProjects([])
      }
    } finally {
      setLoading(false)
    }
  }

  const handleCreate = async () => {
    try {
      await form.validate()
    } catch {
      return
    }
    const fields = form.getFieldsValue(true) as Record<string, any>
    if (!fields.title?.trim()) {
      MessagePlugin.warning('请输入项目名称')
      return
    }
    setCreating(true)
    try {
      const res = await createProject({
        title: fields.title.trim(),
        original_work: fields.original_work || '',
        original_author: fields.original_author || '',
        script_type: fields.script_type || 'movie',
      })
      MessagePlugin.success('项目创建成功')
      setShowCreate(false)
      form.reset()
      navigate(`/project/${res.project.id}`)
    } catch (e: any) {
      const detail = e.response?.data?.detail
      const msg = typeof detail === 'string' ? detail : (e.message || '未知错误')
      MessagePlugin.error('创建失败: ' + msg)
    } finally {
      setCreating(false)
    }
  }

  const handleDelete = async (id: string) => {
    try {
      await deleteProject(id)
      MessagePlugin.success('删除成功')
      // 直接从本地列表移除，避免刷新请求失败时弹错误提示
      setProjects(projects.filter(p => p.id !== id))
    } catch (e) {
      MessagePlugin.error('删除失败')
    }
  }

  const scriptTypeLabels: Record<string, string> = {
    movie: '电影',
    tv_series: '电视剧',
    stage_play: '舞台剧',
    web_series: '网剧',
  }

  const stageLabels: Record<string, { label: string; theme: 'default' | 'warning' | 'success' }> = {
    init: { label: '待开始', theme: 'default' },
    chapter_analysis: { label: '章节解析中', theme: 'warning' },
    character_analysis: { label: '角色提取中', theme: 'warning' },
    plot_structure: { label: '情节重构中', theme: 'warning' },
    dialogue_generation: { label: '对白生成中', theme: 'warning' },
    scene_design: { label: '场景设计中', theme: 'warning' },
    assembly: { label: '整合输出中', theme: 'warning' },
    completed: { label: '已完成', theme: 'success' },
    draft: { label: '草稿', theme: 'default' },
  }

  return (
    <div className="fade-in">
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
          <h2 style={{ margin: 0, fontSize: 26, fontWeight: 700, color: '#1a1a2e' }}>我的剧本项目</h2>
          <p style={{ margin: '6px 0 0', color: '#888', fontSize: 14 }}>
            上传小说章节，AI 自动转换为结构化剧本
          </p>
        </div>
        <Button
          theme="primary"
          size="large"
          icon={<AddIcon />}
          onClick={() => setShowCreate(true)}
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
          新建项目
        </Button>
      </div>

      {/* 项目列表 */}
      {loading ? (
        <div style={{ textAlign: 'center', padding: 80 }}>
          <Loading size="large" text="加载中..." />
        </div>
      ) : projects.length === 0 ? (
        <Card style={{
          textAlign: 'center', padding: '60px 40px',
          borderRadius: 16, border: '1px dashed #d0d5dd',
          background: '#fafbfc',
        }}>
          <Empty
            description="还没有项目，点击上方「新建项目」创建第一个剧本"
            style={{ fontSize: 14, color: '#999' }}
          />
        </Card>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          {projects.map(project => {
            const stage = stageLabels[project.current_stage || 'draft'] || stageLabels.draft
            return (
              <Card
                key={project.id}
                hover
                bordered
                style={{
                  borderRadius: 12,
                  transition: 'all 0.2s',
                  border: '1px solid #e8ecf4',
                  overflow: 'hidden',
                }}
              >
                <div
                  style={{ cursor: 'pointer' }}
                  onClick={() => navigate(`/project/${project.id}`)}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div style={{ flex: 1 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
                        <FileIcon style={{ color: '#667eea', fontSize: 18 }} />
                        <span style={{ fontSize: 17, fontWeight: 600, color: '#1a1a2e' }}>{project.title}</span>
                        <Tag theme="primary" variant="light" size="small" style={{ borderRadius: 6 }}>
                          {scriptTypeLabels[project.script_type] || project.script_type}
                        </Tag>
                        <Tag theme={stage.theme} variant="light" size="small" style={{ borderRadius: 6 }}>
                          {stage.label}
                        </Tag>
                      </div>
                      <div style={{ color: '#999', fontSize: 13 }}>
                        {project.original_work && (
                          <span>原著：{project.original_work}　</span>
                        )}
                        {project.chapter_count > 0 && (
                          <span>已上传 {project.chapter_count} 章　</span>
                        )}
                        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                          <TimeIcon style={{ fontSize: 13 }} />
                          {new Date(project.updated_at).toLocaleString('zh-CN')}
                        </span>
                      </div>
                    </div>
                    <Popconfirm
                      content="确定删除此项目？所有数据将无法恢复"
                      theme="danger"
                      onConfirm={() => handleDelete(project.id)}
                    >
                      <Button
                        variant="text"
                        shape="square"
                        icon={<DeleteIcon />}
                        theme="danger"
                        onClick={(e: React.MouseEvent) => e.stopPropagation()}
                        style={{ opacity: 0.6 }}
                      />
                    </Popconfirm>
                  </div>
                </div>
              </Card>
            )
          })}
        </div>
      )}

      {/* 创建项目对话框 */}
      <Dialog
        header={
          <div style={{ fontSize: 18, fontWeight: 600, color: '#1a1a2e' }}>
            新建剧本项目
          </div>
        }
        visible={showCreate}
        onClose={() => { setShowCreate(false); form.reset() }}
        onConfirm={handleCreate}
        confirmBtn={{
          loading: creating,
          content: '创建项目',
          style: {
            background: 'linear-gradient(135deg, #667eea, #764ba2)',
            border: 'none',
            borderRadius: 8,
            fontWeight: 600,
          },
        }}
        cancelBtn={{
          content: '取消',
          variant: 'outline',
          style: { borderRadius: 8 },
        }}
        width={520}
        style={{ borderRadius: 16 }}
        destroyOnClose
      >
        <div style={{ padding: '8px 0' }}>
          <Form form={form} labelWidth={80} colon>
            <FormItem label="项目名称" name="title" rules={[{ required: true, message: '请输入项目名称' }]}>
              <Input placeholder="如：斗破苍穹剧本改编" style={{ borderRadius: 8 }} />
            </FormItem>
            <FormItem label="原著名称" name="original_work">
              <Input placeholder="小说原名（选填）" style={{ borderRadius: 8 }} />
            </FormItem>
            <FormItem label="原著作者" name="original_author">
              <Input placeholder="作者名（选填）" style={{ borderRadius: 8 }} />
            </FormItem>
            <FormItem label="剧本类型" name="script_type" initialData="movie">
              <Select
                options={[
                  { label: '🎬 电影剧本', value: 'movie' },
                  { label: '📺 电视剧本', value: 'tv_series' },
                  { label: '💻 网剧剧本', value: 'web_series' },
                  { label: '🎭 舞台剧本', value: 'stage_play' },
                ]}
                style={{ borderRadius: 8 }}
              />
            </FormItem>
          </Form>
        </div>
      </Dialog>
    </div>
  )
}
