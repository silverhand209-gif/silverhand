import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 120000,
})

// 项目 API
export const listProjects = () => api.get('/projects').then(r => r.data)
export const createProject = (data: { title: string; original_work?: string; original_author?: string; script_type?: string }) =>
  api.post('/projects', data).then(r => r.data)
export const getProject = (id: string) => api.get(`/projects/${id}`).then(r => r.data)
export const updateProject = (id: string, data: Record<string, any>) =>
  api.put(`/projects/${id}`, data).then(r => r.data)
export const deleteProject = (id: string) => api.delete(`/projects/${id}`).then(r => r.data)

// 章节 API
export const uploadNovel = (id: string, file: File, chapterMode = 'auto') => {
  const form = new FormData()
  form.append('file', file)
  form.append('chapter_mode', chapterMode)
  return api.post(`/projects/${id}/upload`, form).then(r => r.data)
}
export const getChapters = (id: string) => api.get(`/projects/${id}/chapters`).then(r => r.data)

// 生成 API (SSE)
export const generateScript = (id: string, onProgress: (stage: string, data: any) => void, onComplete: (yaml: string, errors: string[]) => void, onError: (err: any) => void) => {
  const eventSource = new EventSource(`/api/projects/${id}/generate`, { withCredentials: true })

  // 使用 fetch + ReadableStream 代替 EventSource（支持 POST）
  const controller = new AbortController()

  fetch(`/api/projects/${id}/generate`, {
    method: 'POST',
    signal: controller.signal,
    headers: { 'Accept': 'text/event-stream' },
  }).then(async response => {
    if (!response.ok) throw new Error(`HTTP ${response.status}`)
    const reader = response.body?.getReader()
    if (!reader) throw new Error('No reader')

    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            const event = JSON.parse(line.slice(6))
            if (event.type === 'progress') {
              onProgress(event.stage, event.data)
            } else if (event.type === 'complete') {
              onComplete(event.yaml || '', event.errors || [])
            }
          } catch (e) {
            // ignore parse errors
          }
        }
      }
    }
  }).catch(err => {
    onError(err)
  })

  return controller
}

// 版本 API
export const getVersions = (id: string) => api.get(`/projects/${id}/versions`).then(r => r.data)
export const saveVersion = (id: string, version: string, yamlContent: string, comment = '') => {
  const form = new FormData()
  form.append('version', version)
  form.append('yaml_content', yamlContent)
  form.append('comment', comment)
  return api.post(`/projects/${id}/versions`, form).then(r => r.data)
}

// 知识库 API
export const getKnowledgeStats = () => api.get('/knowledge/stats').then(r => r.data)
export const searchKnowledge = (query: string, topK = 3) => {
  const form = new FormData()
  form.append('query', query)
  form.append('top_k', String(topK))
  return api.post('/knowledge/search', form).then(r => r.data)
}
export const addKnowledge = (title: string, content: string, category = '用户添加') =>
  api.post('/knowledge/add', { title, content, category }).then(r => r.data)
