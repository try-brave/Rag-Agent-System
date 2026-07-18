<script setup lang="ts">
import {
  ChatDotRound,
  Connection,
  DataLine,
  Document,
  Expand,
  HomeFilled,
  Refresh,
  Upload,
} from '@element-plus/icons-vue'
import { computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { useAppStore } from '@/stores/app'
import { useDocumentStore } from '@/stores/documents'

const route = useRoute()
const router = useRouter()
const appStore = useAppStore()
const documentStore = useDocumentStore()

const menuItems = [
  { label: '总览看板', routeName: 'dashboard', icon: HomeFilled },
  { label: '上传入库', routeName: 'ingest', icon: Upload },
  { label: '文档管理', routeName: 'documents', icon: Document },
  { label: 'Chunk 管理', routeName: 'chunks', icon: Expand },
  { label: '检索调试', routeName: 'retrieval', icon: DataLine },
  { label: 'Agent 对话', routeName: 'chat', icon: ChatDotRound },
]

const activeMenu = computed(() => String(route.name || 'dashboard'))
const pageTitle = computed(() => String(route.meta.title || 'RAG Agent Studio'))
const backendStatusType = computed(() => (appStore.backendReady ? 'success' : 'danger'))
const backendStatusLabel = computed(() => (appStore.backendReady ? '后端已连接' : '后端待连接'))

function goTo(routeName: string) {
  router.push({ name: routeName })
}

async function refreshAll() {
  await Promise.all([appStore.refreshHealth(true), documentStore.initialize()])
}

onMounted(async () => {
  await refreshAll()
})
</script>

<template>
  <div class="app-shell">
    <aside class="app-sidebar">
      <div class="brand-card">
        <div class="brand-mark">RA</div>
        <div>
          <div class="brand-title">RAG Agent Studio</div>
          <div class="brand-subtitle">高可视化知识检索与 Agent 控台</div>
        </div>
      </div>

      <nav class="nav-list">
        <button
          v-for="item in menuItems"
          :key="item.routeName"
          class="nav-item"
          :class="{ 'is-active': activeMenu === item.routeName }"
          @click="goTo(item.routeName)"
        >
          <el-icon><component :is="item.icon" /></el-icon>
          <span>{{ item.label }}</span>
        </button>
      </nav>

      <div class="sidebar-footer panel">
        <div class="status-row">
          <div>
            <div class="panel-kicker">链路状态</div>
            <div class="panel-title">{{ backendStatusLabel }}</div>
          </div>
          <el-tag :type="backendStatusType" effect="dark">
            {{ appStore.health?.ok ? 'READY' : 'CHECK' }}
          </el-tag>
        </div>
        <div v-if="appStore.health" class="service-grid">
          <div v-for="(service, key) in appStore.health.services" :key="key" class="service-pill">
            <el-icon><Connection /></el-icon>
            <span>{{ key }}</span>
            <i :class="['service-dot', service.ok ? 'is-ok' : 'is-bad']" />
          </div>
        </div>
      </div>
    </aside>

    <div class="app-main">
      <header class="topbar panel">
        <div>
          <div class="panel-kicker">Workspace</div>
          <h1 class="topbar-title">{{ pageTitle }}</h1>
        </div>
        <div class="topbar-actions">
          <el-button :icon="Refresh" @click="refreshAll">刷新数据</el-button>
        </div>
      </header>

      <main class="content-area">
        <RouterView />
      </main>
    </div>
  </div>
</template>
