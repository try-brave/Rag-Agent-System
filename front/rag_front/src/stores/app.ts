import { defineStore } from 'pinia'

import { fetchSystemHealth } from '@/api/modules/system'
import { notifyError } from '@/api/http'
import type { HealthResponse } from '@/types/api'

export const useAppStore = defineStore('app', {
  state: () => ({
    initialized: false,
    health: null as HealthResponse | null,
    healthLoading: false,
  }),
  getters: {
    backendReady: (state) => state.health?.ok ?? false,
  },
  actions: {
    async refreshHealth(silent = false) {
      this.healthLoading = true
      try {
        this.health = await fetchSystemHealth()
        this.initialized = true
      } catch (error) {
        if (!silent) {
          notifyError(error, '无法连接后端服务')
        }
      } finally {
        this.healthLoading = false
      }
    },
  },
})
