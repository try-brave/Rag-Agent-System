<script setup lang="ts">
import { Check, Plus, Refresh, Upload, Delete } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { UploadFile } from 'element-plus'
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'

import { notifyError } from '@/api/http'
import { useDocumentStore } from '@/stores/documents'
import { formatDateTime, formatFileSize } from '@/utils/format'

const router = useRouter()
const documentStore = useDocumentStore()

const textDialogVisible = ref(false)
const uploadDialogVisible = ref(false)
const rebuildingDocumentId = ref('')

const textForm = reactive({
  filename: '',
  knowledge_base: 'default',
  preferred_splitter: '',
  content: '',
})

const uploadForm = reactive({
  knowledge_base: 'default',
  preferred_splitter: '',
  file: null as File | null,
})

const splitterOptions = computed(() => documentStore.splitters)

function handleUploadChange(uploadFile: UploadFile) {
  uploadForm.file = uploadFile.raw || null
}

async function submitTextDocument() {
  try {
    await documentStore.createTextDocument({
      filename: textForm.filename,
      knowledge_base: textForm.knowledge_base,
      preferred_splitter: textForm.preferred_splitter || null,
      content: textForm.content,
    })
    ElMessage.success('文本已完成入库')
    textDialogVisible.value = false
    Object.assign(textForm, {
      filename: '',
      knowledge_base: 'default',
      preferred_splitter: '',
      content: '',
    })
  } catch (error) {
    notifyError(error, '文本入库失败')
  }
}

async function submitUploadDocument() {
  if (!uploadForm.file) {
    ElMessage.warning('请先选择文件')
    return
  }

  try {
    await documentStore.createUploadDocument({
      file: uploadForm.file,
      knowledge_base: uploadForm.knowledge_base,
      preferred_splitter: uploadForm.preferred_splitter || null,
    })
    ElMessage.success('文件已上传并完成入库')
    uploadDialogVisible.value = false
    Object.assign(uploadForm, {
      knowledge_base: 'default',
      preferred_splitter: '',
      file: null,
    })
  } catch (error) {
    notifyError(error, '文件上传失败')
  }
}

async function handleRebuild(documentId: string) {
  rebuildingDocumentId.value = documentId
  try {
    await documentStore.triggerRebuild(documentId)
    ElMessage.success('文档索引重建完成')
  } catch (error) {
    notifyError(error, '重建索引失败')
  } finally {
    rebuildingDocumentId.value = ''
  }
}

async function handleDeleteDocument(documentId: string) {
  try {
    await ElMessageBox.confirm(
      '删除文档将级联删除其所有的 Chunk 记录及 Milvus 向量，并且会尝试删除物理源文件，操作不可逆。确定继续？',
      '彻底删除确认',
      {
        type: 'error',
        confirmButtonText: '确认彻底删除',
        cancelButtonText: '取消',
      }
    )
    await documentStore.removeDocument(documentId)
    ElMessage.success('文档已彻底删除')
  } catch (error) {
    if (error !== 'cancel') {
      notifyError(error, '删除文档失败')
    }
  }
}

onMounted(async () => {
  await documentStore.initialize()
})
</script>

<template>
  <div class="page-grid">
    <section class="panel span-12 toolbar-card">
      <div>
        <div class="panel-kicker">Ingestion Pipeline</div>
        <h2>文档入库与索引重建</h2>
        <p class="page-description">支持文件上传、纯文本导入、切分策略选择与索引重建，所有结果都会同步写入文档列表和 Chunk 管理页。</p>
      </div>
      <div class="toolbar-actions">
        <el-button :icon="Refresh" @click="documentStore.initialize()">刷新列表</el-button>
        <el-button :icon="Plus" @click="textDialogVisible = true">纯文本入库</el-button>
        <el-button type="primary" :icon="Upload" @click="uploadDialogVisible = true">上传文件</el-button>
      </div>
    </section>

    <section class="panel span-12 section-card">
      <div class="section-heading">
        <div>
          <div class="panel-kicker">Documents</div>
          <h3>知识文档列表</h3>
        </div>
        <el-tag effect="dark">{{ documentStore.documents.length }} 份文档</el-tag>
      </div>

      <el-table v-loading="documentStore.loading" :data="documentStore.documents" stripe>
        <el-table-column prop="filename" label="文件名" min-width="240" />
        <el-table-column prop="knowledge_base" label="知识库" min-width="120" />
        <el-table-column prop="file_type" label="类型" width="100" />
        <el-table-column prop="chunk_count" label="Chunks" width="100" />
        <el-table-column label="大小" width="120">
          <template #default="scope">{{ formatFileSize(scope.row.file_size) }}</template>
        </el-table-column>
        <el-table-column label="更新时间" min-width="150">
          <template #default="scope">{{ formatDateTime(scope.row.updated_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="360" fixed="right">
          <template #default="scope">
            <div class="inline-actions">
              <el-button size="small" @click="router.push({ name: 'chunks', query: { documentId: scope.row.id } })">查看切分</el-button>
              <el-button size="small" @click="router.push({ name: 'retrieval', query: { keyword: scope.row.filename } })">检索调试</el-button>
              <el-button
                size="small"
                :loading="rebuildingDocumentId === scope.row.id"
                @click="handleRebuild(scope.row.id)"
              >
                重建索引
              </el-button>
              <el-button
                type="danger"
                plain
                size="small"
                @click="handleDeleteDocument(scope.row.id)"
              >
                删除
              </el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>
    </section>

    <el-dialog v-model="textDialogVisible" title="纯文本快速入库" width="720">
      <el-form label-position="top">
        <el-form-item label="文件名">
          <el-input v-model="textForm.filename" placeholder="例如：rule.md" />
        </el-form-item>
        <div class="form-grid two-columns">
          <el-form-item label="知识库名称">
            <el-input v-model="textForm.knowledge_base" />
          </el-form-item>
          <el-form-item label="切分策略">
            <el-select v-model="textForm.preferred_splitter" clearable placeholder="自动判断">
              <el-option v-for="item in splitterOptions" :key="item.name" :label="item.name" :value="item.name" />
            </el-select>
          </el-form-item>
        </div>
        <el-form-item label="正文内容">
          <el-input v-model="textForm.content" type="textarea" :rows="14" placeholder="输入要入库的完整文本内容" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="textDialogVisible = false">取消</el-button>
        <el-button type="primary" :icon="Check" @click="submitTextDocument">开始入库</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="uploadDialogVisible" title="上传文件并入库" width="620">
      <el-form label-position="top">
        <div class="form-grid two-columns">
          <el-form-item label="知识库名称">
            <el-input v-model="uploadForm.knowledge_base" />
          </el-form-item>
          <el-form-item label="切分策略">
            <el-select v-model="uploadForm.preferred_splitter" clearable placeholder="自动判断">
              <el-option v-for="item in splitterOptions" :key="item.name" :label="item.name" :value="item.name" />
            </el-select>
          </el-form-item>
        </div>
        <el-form-item label="文件选择">
          <el-upload
            drag
            :auto-upload="false"
            :show-file-list="true"
            :limit="1"
            :on-change="handleUploadChange"
            :on-remove="() => { uploadForm.file = null }"
          >
            <el-icon class="el-icon--upload"><Upload /></el-icon>
            <div class="el-upload__text">拖拽文件到此处，或 <em>点击选择文件</em></div>
            <template #tip>
              <div class="upload-tip">支持 txt / md / pdf / docx，上传后自动解析、切分和写入向量索引。</div>
            </template>
          </el-upload>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="uploadDialogVisible = false">取消</el-button>
        <el-button type="primary" :icon="Upload" @click="submitUploadDocument">上传并入库</el-button>
      </template>
    </el-dialog>
  </div>
</template>
