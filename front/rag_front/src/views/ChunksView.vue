<script setup lang="ts">
import { Delete, EditPen, Refresh, Search } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { fetchChunks, updateChunk, deleteChunk } from '@/api/modules/chunks'
import { notifyError } from '@/api/http'
import { useDocumentStore } from '@/stores/documents'
import type { ChunkItem } from '@/types/api'
import { formatDateTime, truncateText } from '@/utils/format'

const route = useRoute()
const router = useRouter()
const documentStore = useDocumentStore()

const loading = ref(false)
const keyword = ref('')
const selectedDocumentId = ref(String(route.query.documentId || ''))
const chunks = ref<ChunkItem[]>([])
const selectedChunk = ref<ChunkItem | null>(null)
const editDialogVisible = ref(false)
const editForm = reactive({
  content: '',
  enabled: true,
  metadataText: '{}',
})

const documentOptions = computed(() => documentStore.documents)
const filteredChunks = computed(() =>
  chunks.value.filter((item) => {
    if (!keyword.value.trim()) {
      return true
    }
    return item.content.toLowerCase().includes(keyword.value.trim().toLowerCase())
  }),
)

async function loadChunks() {
  loading.value = true
  try {
    chunks.value = await fetchChunks({
      document_id: selectedDocumentId.value || undefined,
      limit: 500,
    })
    const firstChunk = chunks.value[0]
    if (!selectedChunk.value && firstChunk) {
      selectedChunk.value = firstChunk
    }
  } catch (error) {
    notifyError(error, '加载 Chunk 列表失败')
  } finally {
    loading.value = false
  }
}

function openEdit(chunk: ChunkItem) {
  selectedChunk.value = chunk
  editForm.content = chunk.content
  editForm.enabled = chunk.enabled
  editForm.metadataText = JSON.stringify(chunk.metadata_json, null, 2)
  editDialogVisible.value = true
}

async function submitEdit() {
  if (!selectedChunk.value) {
    return
  }

  try {
    const metadata = JSON.parse(editForm.metadataText)
    const updated = await updateChunk(selectedChunk.value.id, {
      content: editForm.content,
      enabled: editForm.enabled,
      metadata_json: metadata,
    })
    chunks.value = chunks.value.map((item) => (item.id === updated.id ? updated : item))
    selectedChunk.value = updated
    editDialogVisible.value = false
    ElMessage.success('Chunk 已更新')
  } catch (error) {
    notifyError(error, '更新 Chunk 失败，请检查 JSON 格式')
  }
}

async function handleDeleteChunk(chunk: ChunkItem) {
  try {
    await ElMessageBox.confirm('删除后该片段对应的向量也将被移除，确定继续？', '物理删除确认', {
      type: 'warning',
      confirmButtonText: '确认删除',
      cancelButtonText: '取消',
    })
    await deleteChunk(chunk.id)
    ElMessage.success('Chunk 已物理删除')
    
    // 更新本地状态
    chunks.value = chunks.value.filter(item => item.id !== chunk.id)
    if (selectedChunk.value?.id === chunk.id) {
      selectedChunk.value = chunks.value[0] || null
    }
  } catch (error) {
    if (error !== 'cancel') {
      notifyError(error, '删除 Chunk 失败')
    }
  }
}

watch(selectedDocumentId, async (value) => {
  await router.replace({ name: 'chunks', query: value ? { documentId: value } : {} })
  await loadChunks()
})

onMounted(async () => {
  await documentStore.initialize()
  await loadChunks()
})
</script>

<template>
  <div class="page-grid">
    <section class="panel span-12 toolbar-card">
      <div>
        <div class="panel-kicker">Chunk Explorer</div>
        <h2>切分结果观测与编辑</h2>
        <p class="page-description">支持按文档过滤、全文搜索、查看元数据、启停检索并直接编辑 Chunk 内容，便于验证切分质量和溯源字段。</p>
      </div>
      <div class="toolbar-actions wrap">
        <el-select v-model="selectedDocumentId" clearable placeholder="全部文档" style="width: 260px">
          <el-option v-for="item in documentOptions" :key="item.id" :label="item.filename" :value="item.id" />
        </el-select>
        <el-input v-model="keyword" placeholder="搜索 chunk 内容" style="width: 260px">
          <template #prefix><el-icon><Search /></el-icon></template>
        </el-input>
        <el-button :icon="Refresh" @click="loadChunks">刷新</el-button>
      </div>
    </section>

    <section class="panel span-5 section-card fixed-height">
      <div class="section-heading">
        <div>
          <div class="panel-kicker">List</div>
          <h3>Chunk 列表</h3>
        </div>
        <el-tag effect="dark">{{ filteredChunks.length }}</el-tag>
      </div>

      <div v-loading="loading" class="chunk-list">
        <button
          v-for="item in filteredChunks"
          :key="item.id"
          class="chunk-row"
          :class="{ 'is-active': selectedChunk?.id === item.id }"
          @click="selectedChunk = item"
        >
          <div class="chunk-row-top">
            <strong>#{{ item.chunk_index }}</strong>
            <el-tag size="small" :type="item.enabled ? 'success' : 'info'">{{ item.enabled ? '启用' : '停用' }}</el-tag>
          </div>
          <div class="chunk-row-text">{{ truncateText(item.content, 120) }}</div>
        </button>
      </div>
    </section>

    <section v-if="selectedChunk" class="panel span-7 section-card fixed-height">
      <div class="section-heading">
        <div>
          <div class="panel-kicker">Detail</div>
          <h3>Chunk 详情</h3>
        </div>
        <div class="toolbar-actions">
          <el-button type="danger" plain :icon="Delete" @click="handleDeleteChunk(selectedChunk)">删除</el-button>
          <el-button type="primary" :icon="EditPen" @click="openEdit(selectedChunk)">编辑</el-button>
        </div>
      </div>

      <div class="detail-grid two-columns compact">
        <div class="detail-item"><span>ID</span><strong>{{ selectedChunk.id }}</strong></div>
        <div class="detail-item"><span>Document ID</span><strong>{{ selectedChunk.document_id }}</strong></div>
        <div class="detail-item"><span>Page</span><strong>{{ selectedChunk.page_number ?? '--' }}</strong></div>
        <div class="detail-item"><span>Tokens</span><strong>{{ selectedChunk.token_count }}</strong></div>
        <div class="detail-item"><span>Start Offset</span><strong>{{ selectedChunk.start_offset ?? '--' }}</strong></div>
        <div class="detail-item"><span>End Offset</span><strong>{{ selectedChunk.end_offset ?? '--' }}</strong></div>
        <div class="detail-item"><span>更新时间</span><strong>{{ formatDateTime(selectedChunk.updated_at) }}</strong></div>
        <div class="detail-item"><span>Vector ID</span><strong>{{ selectedChunk.vector_id || '--' }}</strong></div>
      </div>

      <div class="code-panel">
        <div class="code-panel-title">内容正文</div>
        <pre>{{ selectedChunk.content }}</pre>
      </div>

      <div class="code-panel">
        <div class="code-panel-title">元数据</div>
        <pre>{{ JSON.stringify(selectedChunk.metadata_json, null, 2) }}</pre>
      </div>
    </section>

    <el-dialog v-model="editDialogVisible" title="编辑 Chunk" width="820">
      <el-form label-position="top">
        <el-form-item label="是否启用检索">
          <el-switch v-model="editForm.enabled" />
        </el-form-item>
        <el-form-item label="正文内容">
          <el-input v-model="editForm.content" type="textarea" :rows="10" />
        </el-form-item>
        <el-form-item label="metadata_json">
          <el-input v-model="editForm.metadataText" type="textarea" :rows="12" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitEdit">保存更新</el-button>
      </template>
    </el-dialog>
  </div>
</template>
