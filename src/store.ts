import { create } from 'zustand'

interface Project {
  id: string
  title: string
  original_work: string
  original_author: string
  script_type: string
  status: string
  current_stage: string
  chapter_count: number
  script_yaml: string | null
  created_at: string
  updated_at: string
}

interface GenerationState {
  isGenerating: boolean
  currentStage: string
  progress: { stage: string; data: any }[]
  errors: string[]
}

interface AppStore {
  projects: Project[]
  currentProject: Project | null
  generation: GenerationState
  setProjects: (projects: Project[]) => void
  setCurrentProject: (project: Project | null) => void
  startGeneration: () => void
  updateGenerationProgress: (stage: string, data: any) => void
  completeGeneration: () => void
  addGenerationError: (error: string) => void
}

export const useAppStore = create<AppStore>((set) => ({
  projects: [],
  currentProject: null,
  generation: {
    isGenerating: false,
    currentStage: '',
    progress: [],
    errors: [],
  },

  setProjects: (projects) => set({ projects }),
  setCurrentProject: (project) => set({ currentProject: project }),

  startGeneration: () => set((state) => ({
    generation: {
      isGenerating: true,
      currentStage: 'starting',
      progress: [],
      errors: [],
    },
  })),

  updateGenerationProgress: (stage, data) => set((state) => ({
    generation: {
      ...state.generation,
      currentStage: stage,
      progress: [...state.generation.progress, { stage, data }],
    },
  })),

  completeGeneration: () => set((state) => ({
    generation: {
      ...state.generation,
      isGenerating: false,
    },
  })),

  addGenerationError: (error) => set((state) => ({
    generation: {
      ...state.generation,
      errors: [...state.generation.errors, error],
    },
  })),
}))
