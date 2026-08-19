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
  files.forEach((f) => {
    // Preserve relative path for folder uploads so same-name files don't collide.
    // webkitRelativePath is set when using folder picker / webkitdirectory.
    const relativePath = (f as any).webkitRelativePath || (f as any)._relativePath || f.name
    form.append('files', f, relativePath)
  })
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

export function deleteFile(projectId: string, filePath: string) {
  return request<{ deleted: string }>(`/projects/${projectId}/files/${filePath}`, { method: 'DELETE' })
}

// --- Package Grouping ---

export interface PackageGroup {
  name: string
  file_count: number
  files: string[]
}

export interface PackagesInfo {
  packages: PackageGroup[]
  loose_files: string[]
  needs_grouping: boolean
}

export function listPackages(projectId: string) {
  return request<PackagesInfo>(`/projects/${projectId}/packages`)
}

export function organizeFiles(projectId: string, groups: Record<string, string[]>) {
  return request<{ moved: { from: string; to: string }[]; errors: string[] }>(`/projects/${projectId}/organize`, {
    method: 'POST',
    body: JSON.stringify({ groups }),
  })
}

// --- Analysis ---

export function triggerAnalysis(projectId: string, modelId?: string) {
  return request<{ status: string; message: string }>(`/projects/${projectId}/analyze`, {
    method: 'POST',
    body: JSON.stringify(modelId ? { model_id: modelId } : {}),
  })
}

export function cancelAnalysis(projectId: string) {
  return request<{ cancelled: boolean; message: string }>(`/projects/${projectId}/cancel`, { method: 'POST' })
}

// --- Models ---

export interface ModelInfo {
  id: string
  name: string
  description: string
}

export interface ModelsResponse {
  default: string
  models: ModelInfo[]
}

export function listModels() {
  return request<ModelsResponse>('/models')
}

export interface StatusResponse {
  project_id: string
  status: string
  error?: string
  tokens?: { input: number; output: number; total: number } | null
  packages_analyzed?: number
  total_flags?: number
  total_findings?: number
}

export function getStatus(projectId: string) {
  return request<StatusResponse>(`/projects/${projectId}/status`)
}

// --- File Viewing ---

export function getFileViewUrl(projectId: string, filePath: string) {
  return `${BASE}/projects/${projectId}/files/${filePath}`
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
