export type ProjectColor = 'teal' | 'blue' | 'amber' | 'plum'

export interface ProjectInput {
  name: string
  description: string
  color: ProjectColor
}

export interface Project extends ProjectInput {
  id: string
  created_at: string
  updated_at: string
  revision: number
}

export interface ProjectList {
  items: Project[]
  total: number
  limit: number
  offset: number
}

// Future entities reference an immutable project context; no fake endpoints are exposed.
export interface DatasetVersionRef { project_id: string; data_version_id: string }
export interface AnalysisRunRef extends DatasetVersionRef { run_id: string }
export interface EvidenceRef extends AnalysisRunRef { evidence_id: string }
