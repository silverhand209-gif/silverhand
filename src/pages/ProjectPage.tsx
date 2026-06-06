import { useState, useEffect, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  Card, Button, Tabs, Upload, Tag, Progress, Space, Loading,
  Textarea, Dialog, Input, MessagePlugin, Divider, Steps, Collapse
} from 'tdesign-react'
import {
  UploadIcon, PlayCircleIcon, CheckCircleIcon, ErrorCircleIcon,
  TimeIcon, ArrowLeftIcon, DownloadIcon, SaveIcon, RefreshIcon,
  FileIcon, FolderOpenIcon
} from 'tdesign-icons-react'
import type { UploadFile } from 'tdesign-react'
import { getProject, uploadNovel, getChapters, generateScript, saveVersion, getVersions } from '../api'
import { useAppStore } from '../store'

const { TabPanel } = Tabs
const { StepItem } = Steps
const { Panel: CollapsePanel } = Collapse

const STAGES = [
  { key: 'chapter_agent', label: '章节解析', desc: '分析章节结构与关键事件' },
  { key: 'character_agent', label: '角色提取', desc: '识别角色性格与关系网络' },
  { key: 'plot_agent', label: '情节重构', desc: '构建幕-场剧本结构' },
  { key: 'dialogue_agent', label: '对白生成', desc: '叙事转角色对白与独白' },
  { key: 'scene_agent', label: '场景设计', desc: '补充环境与氛围描述' },
  { key: 'assembly_agent', label: '整合输出', desc: '生成完整 YAML 剧本' },
]

const stageMap: Record<string, number> = {
  'chapter_agent': 0,
  'character_agent': 1,
  'plot_agent': 2,
  'dialogue_agent': 3,
  'scene_agent': 4,
  'assembly_agent': 5,
}

export default function ProjectPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { generation, startGeneration, updateGenerationProgress, completeGeneration } = useAppStore()

  const [project, setProject] = useState<any>(null)
  const [chapters, setChapters] = useState<any[]>([])
  const [versions, setVersions] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState('upload')
  const [yamlContent, setYamlContent] = useState('')
  const [currentStep, setCurrentStep] = useState(-1)
  const [completedSteps, setCompletedSteps] = useState<number[]>([])
  const [genErrors, setGenErrors] = useState<string[]>([])
  const [showSaveVersion, setShowSaveVersion] = useState(false)
  const [versionName, setVersionName] = useState('')
  const [versionComment, setVersionComment] = useState('')
  const abortRef = useRef<AbortController | null>(null)

  useEffect(() => {
    if (id) loadProject()
    return () => {
      abortRef.current?.abort()
    }
  }, [id])

  const loadProject = async () => {
    setLoading(true)
    try {
      const res = await getProject(id!)
      setProject(res.project)
      setChapters(res.chapters || [])
      setVersions(res.versions || [])
      if (res.project.script_yaml) {
        setYamlContent(res.project.script_yaml)
        setActiveTab('script')
      }
    } catch (e: any) {
      MessagePlugin.error('加载项目失败')
      navigate('/')
    } finally {
      setLoading(false)
    }
  }

  const handleUpload = async (file: UploadFile) => {
    if (!file.raw) return { status: 'fail', error: '文件无效' }
    try {
      const res = await uploadNovel(id!, file.raw)
      MessagePlugin.success(res.message)
      await loadProject()
      return { status: 'success' }
    } catch (e: any) {
      MessagePlugin.error('上传失败: ' + (e.response?.data?.detail || e.message))
      return { status: 'fail', error: '上传失败' }
    }
  }

  const handlePasteText = async () => {
    try {
      const text = await navigator.clipboard.readText()
      if (!text) {
        MessagePlugin.warning('剪贴板为空')
        return
      }
      const blob = new Blob([text], { type: 'text/plain' })
      const file = new File([blob], 'novel.txt', { type: 'text/plain' })
      const res = await uploadNovel(id!, file)
      MessagePlugin.success(res.message)
      await loadProject()
    } catch (e: any) {
      MessagePlugin.error('粘贴上传失败')
    }
  }

  const handleGenerate = async () => {
    if (!project?.chapter_count || project.chapter_count < 3) {
      MessagePlugin.warning('请先上传至少3章小说内容')
      return
    }
    startGeneration()
    setCurrentStep(0)
    setCompletedSteps([])
    setGenErrors([])
    setActiveTab('progress')

    abortRef.current = generateScript(
      id!,
      (stage, data) => {
        updateGenerationProgress(stage, data)
        const stepIdx = stageMap[stage]
        if (stepIdx !== undefined) {
          setCompletedSteps(prev => {
            if (prev.includes(stepIdx)) return prev  // 防止重复（并行场景）
            const updated = [...prev, stepIdx]
            // currentStep = 已完成数（并行阶段可能有多个同时完成）
            setCurrentStep(updated.length)
            return updated
          })
        }
        if (data?.errors?.length) {
          setGenErrors(prev => [...prev, ...data.errors])
        }
      },
      async (yaml, errors) => {
        completeGeneration()
        setCurrentStep(STAGES.length)
        setCompletedSteps(Array.from({ length: STAGES.length }, (_, i) => i))
        if (errors.length) {
          setGenErrors(errors)
          MessagePlugin.warning(`生成完成，但有 ${errors.length} 个警告`)
        } else {
          MessagePlugin.success('剧本生成完成！')
        }
        setYamlContent(yaml)
        setActiveTab('script')
        await loadProject()
      },
      (err) => {
        completeGeneration()
        MessagePlugin.error('生成过程出错: ' + err.message)
      }
    )
  }

  const handleSaveVersion = async () => {
    if (!versionName) {
      MessagePlugin.warning('请输入版本号')
      return
    }
    try {
      await saveVersion(id!, versionName, yamlContent, versionComment)
      MessagePlugin.success('版本保存成功')
      setShowSaveVersion(false)
      setVersionName('')
      setVersionComment('')
      await loadProject()
    } catch (e: any) {
      MessagePlugin.error('保存失败')
    }
  }

  const handleDownload = () => {
    const blob = new Blob([yamlContent], { type: 'text/yaml' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${project?.title || 'script'}.yaml`
    a.click()
    URL.revokeObjectURL(url)
  }

  const handleUpdateYaml = async () => {
    try {
      const { updateProject } = await import('../api')
      await updateProject(id!, { script_yaml: yamlContent })
      MessagePlugin.success('剧本已保存')
      await loadProject()
    } catch (e) {
      MessagePlugin.error('保存失败')
    }
  }

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: 80 }}>
        <Loading size="large" text="加载项目..." />
      </div>
    )
  }

  if (!project) return null

  return (
    <div className="fade-in" style={{ maxWidth: 1100, margin: '0 auto' }}>
      {/* 顶部导航 */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 16, marginBottom: 24,
        padding: '20px 28px', borderRadius: 14,
        background: '#fff', border: '1px solid #e8ecf4',
        boxShadow: '0 1px 4px rgba(0,0,0,0.03)',
      }}>
        <Button
          variant="text"
          icon={<ArrowLeftIcon />}
          onClick={() => navigate('/')}
          style={{ color: '#666', borderRadius: 8 }}
        >
          返回
        </Button>
        <div style={{ flex: 1 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <h2 style={{ margin: 0, fontSize: 20, fontWeight: 700, color: '#1a1a2e' }}>{project.title}</h2>
            <Tag theme="primary" variant="light" style={{ borderRadius: 6 }}>
              {project.script_type === 'movie' ? '电影' : project.script_type === 'tv_series' ? '电视剧' : project.script_type === 'web_series' ? '网剧' : project.script_type === 'stage_play' ? '舞台剧' : project.script_type}
            </Tag>
            {project.chapter_count > 0 && (
              <Tag theme="success" variant="light" style={{ borderRadius: 6 }}>
                {project.chapter_count} 章
              </Tag>
            )}
          </div>
          <div style={{ color: '#999', fontSize: 13, marginTop: 4 }}>
            {project.original_work && `原著：${project.original_work}`}
            {project.original_author && `　作者：${project.original_author}`}
          </div>
        </div>
      </div>

      {/* 主内容区 */}
      <Card style={{ borderRadius: 14, border: '1px solid #e8ecf4', boxShadow: '0 1px 4px rgba(0,0,0,0.03)' }}>
        <Tabs value={activeTab} onChange={(v) => setActiveTab(v as string)}>
          {/* ==================== 上传小说 ==================== */}
          <TabPanel value="upload" label={
            <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <UploadIcon /> 上传小说
            </span>
          }>
            <div style={{ padding: '24px 0' }}>
              <div style={{
                padding: '16px 20px', borderRadius: 10,
                background: 'linear-gradient(135deg, #f0f4ff 0%, #f8f9ff 100%)',
                border: '1px solid #e0e7ff',
                marginBottom: 24,
              }}>
                <div style={{ fontSize: 14, color: '#4a5568', lineHeight: 1.7 }}>
                  <span style={{ fontWeight: 600, color: '#667eea' }}>📖 使用说明：</span>
                  上传 .txt 格式小说文件，系统将自动识别「第X章」进行章节分割。
                  要求至少 <strong>3 个章节</strong> 以上，以便 AI 充分理解故事结构和人物关系。
                </div>
              </div>

              <Space direction="vertical" style={{ width: '100%' }} size={20}>
                <Card
                  bordered
                  style={{
                    borderRadius: 12, border: '2px dashed #d0d5dd',
                    background: '#fafbfc', textAlign: 'center',
                  }}
                >
                  <div style={{ padding: '16px 0' }}>
                    <Upload
                      action=""
                      theme="file-flow"
                      accept=".txt"
                      autoUpload={false}
                      requestMethod={handleUpload}
                      tips="仅支持 .txt 文件，编码支持 UTF-8 / GBK"
                      placeholder="点击或拖拽上传小说文件"
                    />
                  </div>
                </Card>

                <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
                  <Divider layout="horizontal" style={{ flex: 1, margin: 0 }} />
                  <span style={{ color: '#bbb', fontSize: 13, whiteSpace: 'nowrap' }}>或者</span>
                  <Divider layout="horizontal" style={{ flex: 1, margin: 0 }} />
                </div>

                <Button
                  variant="outline"
                  block
                  onClick={handlePasteText}
                  icon={<FolderOpenIcon />}
                  style={{ borderRadius: 10, height: 48, fontSize: 14, fontWeight: 500 }}
                >
                  从剪贴板粘贴小说文本
                </Button>
              </Space>

              {chapters.length > 0 && (
                <div style={{
                  marginTop: 28, padding: '20px 24px',
                  borderRadius: 12, background: '#fafbfc',
                  border: '1px solid #e8ecf4',
                }}>
                  <div style={{
                    fontWeight: 600, marginBottom: 14, fontSize: 15, color: '#1a1a2e',
                    display: 'flex', alignItems: 'center', gap: 8,
                  }}>
                    <FileIcon style={{ color: '#667eea' }} />
                    已上传章节 ({chapters.length} 章)
                  </div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                    {chapters.map((ch: any) => (
                      <Tag key={ch.id} variant="light" style={{ borderRadius: 6, padding: '4px 12px', fontSize: 13 }}>
                        第{ch.chapter_number}章 {ch.title}
                      </Tag>
                    ))}
                  </div>

                  {chapters.length >= 3 && (
                    <div style={{ marginTop: 28, textAlign: 'center' }}>
                      <Button
                        theme="primary"
                        size="large"
                        icon={<PlayCircleIcon />}
                        onClick={handleGenerate}
                        loading={generation.isGenerating}
                        disabled={generation.isGenerating}
                        style={{
                          background: 'linear-gradient(135deg, #667eea, #764ba2)',
                          border: 'none',
                          padding: '0 48px',
                          height: 52,
                          fontSize: 17,
                          fontWeight: 600,
                          borderRadius: 12,
                          boxShadow: '0 6px 20px rgba(102, 126, 234, 0.35)',
                        }}
                      >
                        🚀 开始生成剧本
                      </Button>
                      <div style={{ color: '#aaa', fontSize: 13, marginTop: 10 }}>
                        预计需要 2-5 分钟，AI 将依次完成章节解析、角色提取、情节重构、对白生成、场景设计和整合输出
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          </TabPanel>

          {/* ==================== 生成进度 ==================== */}
          <TabPanel value="progress" label={
            <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <TimeIcon /> 生成进度
            </span>
          }>
            <div style={{ padding: '24px 0' }}>
              {!generation.isGenerating && currentStep < 0 ? (
                <div style={{
                  textAlign: 'center', padding: 60, color: '#999',
                  background: '#fafbfc', borderRadius: 12, border: '1px dashed #d0d5dd',
                }}>
                  <FolderOpenIcon style={{ fontSize: 40, color: '#ccc', marginBottom: 12 }} />
                  <div>请先在「上传小说」标签页上传内容，然后点击「开始生成剧本」</div>
                </div>
              ) : (
                <>
                  <Steps current={currentStep} theme="dot" style={{ marginBottom: 32 }}>
                    {STAGES.map((stage, idx) => (
                      <StepItem
                        key={stage.key}
                        title={stage.label}
                        content={stage.desc}
                        status={
                          completedSteps.includes(idx) ? 'finish'
                            : currentStep > idx ? 'process' : 'default'
                        }
                      />
                    ))}
                  </Steps>

                  {generation.isGenerating && (
                    <div style={{ textAlign: 'center', padding: 32 }}>
                      <Loading size="medium" text="AI 正在创作中..." />
                      <Progress
                        percentage={Math.round((currentStep / STAGES.length) * 100)}
                        style={{ maxWidth: 300, margin: '16px auto 0' }}
                        theme="plump"
                        strokeWidth={6}
                      />
                    </div>
                  )}

                  {genErrors.length > 0 && (
                    <Collapse style={{ marginTop: 20, borderRadius: 10 }}>
                      <CollapsePanel header={
                        <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                          <ErrorCircleIcon style={{ color: '#e37318' }} />
                          警告信息 ({genErrors.length})
                        </span>
                      }>
                        {genErrors.map((err, i) => (
                          <div key={i} style={{ color: '#e37318', fontSize: 13, marginBottom: 4, fontFamily: 'monospace' }}>
                            {err}
                          </div>
                        ))}
                      </CollapsePanel>
                    </Collapse>
                  )}

                  {currentStep >= STAGES.length && (
                    <div style={{
                      textAlign: 'center', padding: 40,
                      background: 'linear-gradient(135deg, #f0fdf4, #ecfdf5)',
                      borderRadius: 14, border: '1px solid #bbf7d0',
                    }}>
                      <CheckCircleIcon style={{ fontSize: 52, color: '#22c55e' }} />
                      <div style={{ fontSize: 20, fontWeight: 700, marginTop: 12, color: '#166534' }}>
                        剧本生成完成！
                      </div>
                      <div style={{ color: '#15803d', fontSize: 14, marginTop: 4, marginBottom: 16 }}>
                        AI 已成功将小说转换为结构化剧本
                      </div>
                      <Button
                        theme="primary"
                        size="large"
                        onClick={() => setActiveTab('script')}
                        style={{
                          background: 'linear-gradient(135deg, #22c55e, #16a34a)',
                          border: 'none', borderRadius: 10, fontWeight: 600,
                          boxShadow: '0 4px 14px rgba(34, 197, 94, 0.3)',
                        }}
                      >
                        查看剧本
                      </Button>
                    </div>
                  )}
                </>
              )}
            </div>
          </TabPanel>

          {/* ==================== 剧本预览 ==================== */}
          <TabPanel value="script" label={
            <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <FileIcon /> 剧本预览
            </span>
          }>
            <div style={{ padding: '8px 0' }}>
              {yamlContent ? (
                <>
                  <div style={{
                    display: 'flex', gap: 8, marginBottom: 16, padding: '12px 16px',
                    background: '#fafbfc', borderRadius: 10, border: '1px solid #e8ecf4',
                    flexWrap: 'wrap',
                  }}>
                    <Button
                      icon={<SaveIcon />}
                      onClick={handleUpdateYaml}
                      style={{ borderRadius: 8, fontWeight: 500 }}
                    >
                      保存修改
                    </Button>
                    <Button
                      icon={<DownloadIcon />}
                      variant="outline"
                      onClick={handleDownload}
                      style={{ borderRadius: 8 }}
                    >
                      下载 YAML
                    </Button>
                    <Button
                      variant="outline"
                      onClick={() => setShowSaveVersion(true)}
                      style={{ borderRadius: 8 }}
                    >
                      保存为新版本
                    </Button>
                    <div style={{ flex: 1 }} />
                    <Button
                      icon={<RefreshIcon />}
                      variant="text"
                      onClick={handleGenerate}
                      disabled={generation.isGenerating}
                      style={{ borderRadius: 8 }}
                    >
                      重新生成
                    </Button>
                  </div>

                  <Textarea
                    value={yamlContent}
                    onChange={(v) => setYamlContent(v as string)}
                    autosize={{ minRows: 22, maxRows: 60 }}
                    style={{
                      fontFamily: "'Fira Code', 'Cascadia Code', 'JetBrains Mono', monospace",
                      fontSize: 13,
                      lineHeight: 1.7,
                      borderRadius: 10,
                      border: '1px solid #e0e0e0',
                      background: '#1e1e2e',
                      color: '#cdd6f4',
                      padding: 20,
                    }}
                  />

                  {/* 版本历史 */}
                  {versions.length > 0 && (
                    <div style={{ marginTop: 28 }}>
                      <div style={{
                        fontWeight: 600, marginBottom: 12, fontSize: 15,
                        display: 'flex', alignItems: 'center', gap: 8,
                      }}>
                        <TimeIcon /> 版本历史
                      </div>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                        {versions.map((v: any) => (
                          <Card key={v.id} size="small" style={{ borderRadius: 10, border: '1px solid #e8ecf4' }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                                <Tag theme="success" variant="light" style={{ borderRadius: 6 }}>{v.version}</Tag>
                                {v.comment && <span style={{ color: '#666', fontSize: 13 }}>{v.comment}</span>}
                              </div>
                              <span style={{ color: '#999', fontSize: 12 }}>
                                {new Date(v.created_at).toLocaleString('zh-CN')}
                              </span>
                            </div>
                          </Card>
                        ))}
                      </div>
                    </div>
                  )}
                </>
              ) : (
                <div style={{
                  textAlign: 'center', padding: 60, color: '#999',
                  background: '#fafbfc', borderRadius: 12, border: '1px dashed #d0d5dd',
                }}>
                  <FileIcon style={{ fontSize: 40, color: '#ccc', marginBottom: 12 }} />
                  <div style={{ fontSize: 15 }}>暂无剧本内容</div>
                  <div style={{ fontSize: 13, marginTop: 4 }}>
                    请先在「上传小说」标签页上传内容并生成剧本
                  </div>
                </div>
              )}
            </div>
          </TabPanel>
        </Tabs>
      </Card>

      {/* 保存版本对话框 */}
      <Dialog
        header={
          <div style={{ fontSize: 18, fontWeight: 600 }}>保存为新版本</div>
        }
        visible={showSaveVersion}
        onClose={() => setShowSaveVersion(false)}
        onConfirm={handleSaveVersion}
        confirmBtn={{
          content: '保存版本',
          style: {
            background: 'linear-gradient(135deg, #667eea, #764ba2)',
            border: 'none', borderRadius: 8, fontWeight: 600,
          },
        }}
        width={440}
        destroyOnClose
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16, marginTop: 8 }}>
          <div>
            <label style={{ display: 'block', marginBottom: 6, fontWeight: 500, fontSize: 14 }}>版本号</label>
            <Input
              value={versionName}
              onChange={(v) => setVersionName(v as string)}
              placeholder="如 v1.0, v1.1, draft-2"
              style={{ borderRadius: 8 }}
            />
          </div>
          <div>
            <label style={{ display: 'block', marginBottom: 6, fontWeight: 500, fontSize: 14 }}>备注</label>
            <Textarea
              value={versionComment}
              onChange={(v) => setVersionComment(v as string)}
              placeholder="此版本的修改说明（可选）"
              autosize={{ minRows: 2, maxRows: 4 }}
              style={{ borderRadius: 8 }}
            />
          </div>
        </div>
      </Dialog>
    </div>
  )
}
