<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'

import { useAppStore } from '@/stores/app'
import { useChatStore } from '@/stores/chat'
import { useDocumentStore } from '@/stores/documents'
import { formatDateTime, truncateText } from '@/utils/format'

const router = useRouter()
const appStore = useAppStore()
const documentStore = useDocumentStore()
const chatStore = useChatStore()

const stats = computed(() => [
  {
    label: '知识文档',
    value: documentStore.documents.length,
    description: '已入库文档总数',
  },
  {
    label: '切分 Chunk',
    value: documentStore.totalChunks,
    description: '当前文档切分总量',
  },
  {
    label: '最近会话',
    value: chatStore.sessions.length,
    description: '已记录的 Agent 会话',
  },
  {
    label: '后端状态',
    value: appStore.backendReady ? '在线' : '检查中',
    description: 'Postgres / Redis / Milvus 健康探测',
  },
])

const latestDocuments = computed(() => documentStore.documents.slice(0, 5))
const latestSessions = computed(() => chatStore.sessions.slice(0, 5))

onMounted(async () => {
  if (!documentStore.documents.length) {
    await documentStore.initialize()
  }
  if (!chatStore.sessions.length) {
    await chatStore.loadSessions()
  }
})
</script>

<template>
  <div class="page-grid">
    <section class="hero-card panel span-12">
      <div>
        <div class="panel-kicker">RAG Product Surface</div>
        <h2 class="hero-title">从文档入库 / OCR图片表格识别、Chunk 观测到 Agent 溯源对话，前后端链路已全部打通【全栈AI开发工程化能力】</h2>
        <p class="hero-description">
          这里汇聚文档、检索、Agent 会话和系统依赖的核心状态。你可以从总览跳入任意模块，直接进行上传、切分检查、检索调试和会话回放。
        </p>
      </div>
      <div class="hero-actions">
        <el-button
          type="primary"
          size="large"
          @click="router.push({ name: 'ingest' })"
        >
          开始导入文档
        </el-button>
        <el-button size="large" @click="router.push({ name: 'chat' })">打开 Agent 对话</el-button>
      </div>
    </section>

    <section v-for="item in stats" :key="item.label" class="metric-card panel span-3">
      <div class="metric-label">{{ item.label }}</div>
      <div class="metric-value">{{ item.value }}</div>
      <div class="metric-description">{{ item.description }}</div>
    </section>

    <section class="panel span-6 section-card">
      <div class="section-heading">
        <div>
          <div class="panel-kicker">Documents</div>
          <h3>最近文档</h3>
        </div>
        <el-button text @click="router.push({ name: 'documents' })">查看全部</el-button>
      </div>
      <div v-if="latestDocuments.length" class="stack-list">
        <article v-for="item in latestDocuments" :key="item.id" class="stack-item">
          <div>
            <div class="stack-title">{{ item.filename }}</div>
            <div class="stack-meta">
              <span>{{ item.file_type }}</span>
              <span>{{ item.chunk_count }} chunks</span>
              <span>{{ formatDateTime(item.updated_at) }}</span>
            </div>
          </div>
          <el-button size="small" @click="router.push({ name: 'chunks', query: { documentId: item.id } })">查看切分</el-button>
        </article>
      </div>
      <el-empty v-else description="暂无文档数据" />
    </section>

    <section class="panel span-6 section-card">
      <div class="section-heading">
        <div>
          <div class="panel-kicker">Sessions</div>
          <h3>最近会话</h3>
        </div>
        <el-button text @click="router.push({ name: 'chat' })">进入对话</el-button>
      </div>
      <div v-if="latestSessions.length" class="stack-list">
        <article v-for="item in latestSessions" :key="item.session_id" class="stack-item wide">
          <div>
            <div class="stack-title">{{ truncateText(item.latest_question, 46) }}</div>
            <div class="stack-meta">
              <span>{{ item.message_count }} 轮消息</span>
              <span>{{ formatDateTime(item.updated_at) }}</span>
            </div>
            <p class="stack-text">{{ truncateText(item.latest_answer || '暂无回答', 100) }}</p>
          </div>
        </article>
      </div>
      <el-empty v-else description="暂无会话记录" />
    </section>
  </div>
</template>
