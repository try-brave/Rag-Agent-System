<script setup lang="ts">
import {
  ChatDotRound,
  Connection,
  Delete,
  Plus,
  Promotion,
  Refresh,
  VideoPause,
} from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { computed, onMounted, ref, watch, nextTick } from 'vue'

import { useAppStore } from '@/stores/app'
import { useChatStore } from '@/stores/chat'
import { formatDateTime, formatScore, truncateText } from '@/utils/format'

const appStore = useAppStore()
const chatStore = useChatStore()

const draftMessage = ref('')
const topK = ref(5)
const messageListRef = ref<HTMLElement | null>(null)

const sessions = computed(() => chatStore.sessions)
const activeSessionId = computed(() => chatStore.activeSessionId)
const activeTurns = computed(() => chatStore.activeTurns)
const selectedTurn = computed(() => chatStore.selectedTurn)

function scrollToBottom() {
  nextTick(() => {
    if (messageListRef.value) {
      messageListRef.value.scrollTop = messageListRef.value.scrollHeight
    }
  })
}

watch(activeTurns, () => {
  scrollToBottom()
}, { deep: true })

function summarizeSourceFilenames(sourceChunks: Array<{ filename?: string | null }>) {
  const filenames = Array.from(new Set(sourceChunks.map((item) => item.filename).filter(Boolean)))
  return filenames.join(' / ')
}

function resetComposer() {
  draftMessage.value = ''
}

async function initializePage() {
  await Promise.all([appStore.refreshHealth(true), chatStore.loadSessions()])

  if (chatStore.activeSessionId) {
    await chatStore.loadHistory(chatStore.activeSessionId)
    return
  }

  chatStore.createBlankSession()
}

async function handleCreateSession() {
  chatStore.createBlankSession()
  resetComposer()
  ElMessage.success('已创建新的空会话')
}

async function handleSelectSession(sessionId: string) {
  await chatStore.selectSession(sessionId)
}

async function handleDeleteSession(sessionId: string) {
  try {
    await ElMessageBox.confirm('删除后会清空该会话的历史与短期记忆，是否继续？', '删除会话确认', {
      type: 'warning',
      confirmButtonText: '确认删除',
      cancelButtonText: '取消',
    })
    await chatStore.deleteSession(sessionId)
    if (!chatStore.activeSessionId) {
      chatStore.createBlankSession()
    }
  } catch {
    // 用户主动取消删除时不需要额外提示。
  }
}

async function handleSendMessage() {
  const message = draftMessage.value.trim()
  if (!message) {
    ElMessage.warning('请输入消息内容')
    return
  }

  await chatStore.sendMessage(message, topK.value)
  resetComposer()
}

function handleStopStreaming() {
  chatStore.stopStreaming()
}

onMounted(async () => {
  await initializePage()
})
</script>

<template>
  <div class="page-grid chat-page-grid">
    <section class="panel span-12 toolbar-card">
      <div>
        <div class="panel-kicker">Agent Console</div>
        <h2>多轮对话、工具调用与溯源结果全链路观测</h2>
        <p class="page-description">
          当前页面直连后端流式对话接口，可查看会话历史、实时生成内容、工具调用过程以及最终命中的来源 Chunk。
        </p>
      </div>
      <div class="toolbar-actions wrap">
        <el-tag :type="appStore.backendReady ? 'success' : 'danger'" effect="dark">
          {{ appStore.backendReady ? '后端可用' : '等待后端' }}
        </el-tag>
        <el-button :icon="Refresh" @click="initializePage">刷新会话</el-button>
        <el-button :icon="Plus" @click="handleCreateSession">新建会话</el-button>
      </div>
    </section>

    <section class="panel span-3 section-card fixed-height">
      <div class="section-heading">
        <div>
          <div class="panel-kicker">Sessions</div>
          <h3>会话列表</h3>
        </div>
        <el-tag effect="dark">{{ sessions.length }}</el-tag>
      </div>

      <div class="chat-session-list">
        <article
          v-for="session in sessions"
          :key="session.session_id"
          class="session-row"
          :class="{ 'is-active': activeSessionId === session.session_id }"
        >
          <div class="session-row-top">
            <strong>{{ truncateText(session.latest_question || session.session_id, 24) }}</strong>
            <el-button
              text
              type="danger"
              :icon="Delete"
              @click.stop="handleDeleteSession(session.session_id)"
            />
          </div>
          <div class="session-row-body" @click="handleSelectSession(session.session_id)">
            <div class="stack-meta">
              <span>{{ session.message_count }} 轮</span>
              <span>{{ formatDateTime(session.updated_at) }}</span>
            </div>
            <p class="stack-text">{{ truncateText(session.latest_answer || '暂无回答', 40) }}</p>
          </div>
        </article>
      </div>

      <el-empty
        v-if="!sessions.length"
        description="暂无历史会话，可直接新建或发送首条消息"
      />
    </section>

    <section class="panel span-6 section-card fixed-height">
      <div class="section-heading">
        <div>
          <div class="panel-kicker">Conversation</div>
          <h3>对话窗口</h3>
        </div>
        <el-tag effect="dark">{{ activeTurns.length }} 条记录</el-tag>
      </div>

      <div class="chat-message-list" ref="messageListRef">
        <template v-for="turn in activeTurns" :key="turn.id">
          <!-- 用户消息气泡 -->
          <div class="chat-bubble-wrapper is-user">
            <div class="chat-bubble">
              <div class="bubble-header">
                <span class="bubble-time">{{ formatDateTime(turn.createdAt) }}</span>
                <span class="bubble-name">我</span>
              </div>
              <div class="bubble-content">{{ turn.userQuestion }}</div>
            </div>
          </div>

          <!-- Agent 回复气泡 -->
          <div
            class="chat-bubble-wrapper is-agent"
            :class="{ 'is-selected': chatStore.selectedTurnId === turn.id }"
            @click="chatStore.selectedTurnId = turn.id"
          >
            <div class="chat-bubble">
              <div class="bubble-header">
                <span class="bubble-name">Agent</span>
                <span class="bubble-time">{{ turn.latencyMs ? `${turn.latencyMs} ms` : turn.pending ? '生成中' : '--' }}</span>
              </div>
              <div class="bubble-content answer-text">
                <template v-if="turn.answer">{{ turn.answer }}</template>
                <template v-else-if="turn.pending">
                  <div class="typing-indicator">
                    <span></span><span></span><span></span>
                  </div>
                </template>
                <template v-else>暂无回答</template>
              </div>

              <!-- 执行状态与来源标识 -->
              <div class="bubble-footer">
                <div class="pill-row">
                  <span class="meta-pill">route: {{ turn.route }}</span>
                  <span class="meta-pill" v-if="turn.sourceChunks.length">
                    sources: {{ turn.sourceChunks.length }}
                  </span>
                  <span class="meta-pill" :class="{ 'is-danger': turn.failed }">
                    {{ turn.failed ? turn.errorMessage || '执行失败' : turn.pending ? '执行中' : '已完成' }}
                  </span>
                </div>
                <div v-if="turn.sourceChunks.length" class="stack-meta source-summary">
                  <span>检索命中文档：{{ summarizeSourceFilenames(turn.sourceChunks) || '未命名文档' }}</span>
                </div>
              </div>
            </div>
          </div>
        </template>
      </div>

      <div class="chat-composer">
        <el-input
          v-model="draftMessage"
          type="textarea"
          :rows="4"
          resize="none"
          placeholder="输入你的问题，例如：总结 rule.md 的编码规范，并给出来源 chunk"
          @keyup.ctrl.enter="handleSendMessage"
        />
        <div class="composer-actions">
          <div class="composer-config">
            <span>Top K</span>
            <el-input-number v-model="topK" :min="1" :max="20" />
          </div>
          <div class="toolbar-actions">
            <el-button
              :icon="VideoPause"
              :disabled="!chatStore.sending"
              @click="handleStopStreaming"
            >
              停止生成
            </el-button>
            <el-button
              type="primary"
              :icon="Promotion"
              :loading="chatStore.sending"
              @click="handleSendMessage"
            >
              发送消息
            </el-button>
          </div>
        </div>
      </div>
    </section>

    <section class="panel span-3 section-card fixed-height">
      <div class="section-heading">
        <div>
          <div class="panel-kicker">Trace</div>
          <h3>执行轨迹与来源</h3>
        </div>
        <el-tag effect="dark">{{ selectedTurn?.events.length || 0 }} 个事件</el-tag>
      </div>

      <template v-if="selectedTurn">
        <div class="detail-grid compact">
          <div class="detail-item"><span>Session</span><strong>{{ selectedTurn.sessionId }}</strong></div>
          <div class="detail-item"><span>Route</span><strong>{{ selectedTurn.route }}</strong></div>
          <div class="detail-item"><span>Latency</span><strong>{{ selectedTurn.latencyMs ?? '--' }}</strong></div>
          <div class="detail-item"><span>Source Chunks</span><strong>{{ selectedTurn.sourceChunks.length }}</strong></div>
        </div>

        <div class="trace-section">
          <div class="code-panel-title">工具事件</div>
          <div class="timeline-list">
            <article v-for="event in selectedTurn.events" :key="`${selectedTurn.id}-${event.timestamp}-${event.type}`" class="timeline-item">
              <div class="timeline-header">
                <strong>{{ event.type }}</strong>
                <span>{{ formatDateTime(event.timestamp) }}</span>
              </div>
              <div class="stack-meta">
                <span v-if="event.phase">phase: {{ event.phase }}</span>
                <span v-if="event.tool_name">tool: {{ event.tool_name }}</span>
                <span v-if="event.status">status: {{ event.status }}</span>
              </div>
              <pre v-if="event.args">{{ JSON.stringify(event.args, null, 2) }}</pre>
              <p v-else class="stack-text">{{ event.content || event.message || '无额外内容' }}</p>
            </article>
          </div>
        </div>

        <div class="trace-section">
          <div class="code-panel-title">来源 Chunk</div>
          <div v-if="selectedTurn.sourceChunks.length" class="source-list">
            <article v-for="item in selectedTurn.sourceChunks" :key="`${selectedTurn.id}-${item.ref_id}`" class="source-card">
              <div class="result-card-top">
                <div>
                  <div class="stack-title">{{ item.filename || 'unknown' }}</div>
                  <div class="stack-meta">
                    <span>ref #{{ item.ref_id }}</span>
                    <span>chunk #{{ item.chunk_index ?? '--' }}</span>
                    <span>page {{ item.page_number ?? '--' }}</span>
                  </div>
                </div>
                <el-tag type="success">score {{ formatScore(item.score) }}</el-tag>
              </div>
              <p class="stack-text">{{ item.content }}</p>
              <div class="pill-row">
                <span class="meta-pill">splitter: {{ item.splitter_name || '--' }}</span>
                <span class="meta-pill">parser: {{ item.parser_name || '--' }}</span>
                <span class="meta-pill">section: {{ item.section_title || item.section_type || '--' }}</span>
              </div>
            </article>
          </div>
          <el-empty v-else description="当前轮次还没有来源片段" />
        </div>
      </template>

      <el-empty v-else description="选择一轮对话后查看执行轨迹和来源 Chunk" />
    </section>
  </div>
</template>
