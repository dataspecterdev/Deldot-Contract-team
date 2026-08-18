/**
 * DORA API client — all backend calls go through here.
 */

const BASE = '/api'

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(body.detail || `Request failed: ${res.status}`)
  }
  if (res.status === 204) return undefined as T
  return res.json()
}

// --- Projects ---

export interface Project {
  id: string
  name: string
  mode: 'standard' | 'incognito'
  created_at: string
  file_count: number
  status: 'ready' | 'analyzing' | 'complete' | 'error'
  error?: string
}

export interface UploadedFile {
  file_name: string
  size_bytes: number
  uploaded_at: string
}

export interface OutputFile {
  file_name: string
  file_type: string
  size_bytes: number
  download_url: string
}

export function createProject(name: string, mode: 'standard' | 'incognito') {
  return request<Project>('/projects', {
    method: 'POST',
    body: JSON.stringify({ name, mode }),
  })
}

export function listProjects() {
  return request<Project[]>('/projects')
}

export function getProject(id: string) {
  return request<Project>(`/projects/${id}`)
}

export function deleteProject(id: string) {
  return request<void>(`/projects/${id}`, { method: 'DELETE' })
}

// --- File Upload ---

export async function uploadFiles(projectId: string, files: File[]) {
  const form = new FormData()
  files.forEach((f) => form.append('files', f))
  const res = await fetch(`${BASE}/projects/${projectId}/upload`, {
    method: 'POST',
    body: form,
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(body.detail || 'Upload failed')
  }
  return res.json() as Promise<{ uploaded: { file_name: string; size_bytes: number }[]; total: number }>
}

export function listFiles(projectId: string) {
  return request<UploadedFile[]>(`/projects/${projectId}/files`)
}

export function deleteFile(projectId: string, fileName: string) {
  return request<{ deleted: string }>(`/projects/${projectId}/files/${fileName}`, { method: 'DELETE' })
}

// --- Analysis ---

export function triggerAnalysis(projectId: string) {
  return request<{ status: string; message: string }>(`/projects/${projectId}/analyze`, { method: 'POST' })
}

export function getStatus(projectId: string) {
  return request<{ project_id: string; status: string; error?: string }>(`/projects/${projectId}/status`)
}

// --- Outputs ---

export function listOutputs(projectId: string) {
  return request<OutputFile[]>(`/projects/${projectId}/outputs`)
}

export function getOutputDownloadUrl(projectId: string, fileName: string) {
  return `${BASE}/projects/${projectId}/outputs/${fileName}`
}

export async function fetchOutputContent(projectId: string, fileName: string): Promise<string> {
  const res = await fetch(`${BASE}/projects/${projectId}/outputs/${fileName}`)
  if (!res.ok) throw new Error('Failed to fetch output')
  return res.text()
}
