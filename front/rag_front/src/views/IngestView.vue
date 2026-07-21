<script setup lang="ts">
import { Check, Files, Refresh, Upload } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import type { UploadFile, UploadFiles } from 'element-plus'
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'

import { notifyError } from '@/api/http'
import type { BatchUploadItem } from '@/api/modules/documents'
import { useDocumentStore } from '@/stores/documents'
import { formatDateTime, formatFileSize } from '@/utils/format'

const router = useRouter()
const documentStore = useDocumentStore()

const uploading = ref(false)
const textSubmitting = ref(false)

const uploadForm = reactive({
  knowledge_base: 'default',
  preferred_splitter: '',
  files: [] as File[],
})

const textForm = reactive({
  filename: '',
  knowledge_base: 'default',
  preferred_splitter: '',
  content: '',
})

const splitterOptions = computed(() => documentStore.splitters)
const latestDocuments = computed(() => documentStore.documents.slice(0, 6))

function handleUploadChange(uploadFile: UploadFile, uploadFiles: UploadFiles) {
  uploadForm.files = uploadFiles.map((f) => f.raw!).filter(Boolean)
}

function handleUploadRemove(_file: UploadFile, uploadFiles: UploadFiles) {
  uploadForm.files = uploadFiles.map((f) => f.raw!).filter(Boolean)
}

async function submitUploadDocument() {
  if (uploadForm.files.length === 0) {
    ElMessage.warning('请先选择要上传的文档')
    return
  }

  uploading.value = true
  try {
    const results: BatchUploadItem[] = await documentStore.createBatchUploadDocuments({
      files: uploadForm.files,
      knowledge_base: uploadForm.knowledge_base,
      preferred_splitter: uploadForm.preferred_splitter || null,
    })

    const successCount = results.filter((r) => !r.error).length
    const failCount = results.filter((r) => r.error).length

    if (failCount > 0) {
      const errors = results.filter((r) => r.error).map((r) => r.error).join('; ')
      ElMessage.warning(`上传完成：成功 ${successCount} 个，失败 ${failCount} 个。${errors}`)
    } else {
      ElMessage.success(`全部 ${successCount} 个文档已上传、解析并写入向量索引`)
    }

    Object.assign(uploadForm, {
      knowledge_base: 'default',
      preferred_splitter: '',
      files: [],
    })
    // 跳转到文档列表而非单个文档的 chunks 页
    await router.push({ name: 'documents' })
  } catch (error) {
    notifyError(error, '上传文档失败')
  } finally {
    uploading.value = false
  }
}

async function submitTextDocument() {
  if (!textForm.filename.trim() || !textForm.content.trim()) {
    ElMessage.warning('请填写文件名和正文内容')
    return
  }

  textSubmitting.value = true
  try {
    const document = await documentStore.createTextDocument({
      filename: textForm.filename.trim(),
      knowledge_base: textForm.knowledge_base,
      preferred_splitter: textForm.preferred_splitter || null,
      content: textForm.content,
    })
    ElMessage.success('文本已完成入库并建立向量索引')
    Object.assign(textForm, {
      filename: '',
      knowledge_base: 'default',
      preferred_splitter: '',
      content: '',
    })
    await router.push({ name: 'chunks', query: { documentId: document.id } })
  } catch (error) {
    notifyError(error, '文本入库失败')
  } finally {
    textSubmitting.value = false
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
        <div class="panel-kicker">Dedicated Ingestion</div>
        <h2>上传文档并解析入向量数据库</h2>
        <p class="page-description">
          这个页面只负责“上传 -> 解析 -> 切分 -> 写入向量索引”，完成后可直接跳到 Chunk 管理页查看切分和溯源结果。
        </p>
      </div>
      <div class="toolbar-actions wrap">
        <el-button :icon="Refresh" @click="documentStore.initialize()">刷新数据</el-button>
        <el-button :icon="Files" @click="router.push({ name: 'documents' })">查看文档列表</el-button>
      </div>
    </section>

    <section class="panel span-6 section-card">
      <div class="section-heading">
        <div>
          <div class="panel-kicker">Upload File</div>
          <h3>文件上传入库</h3>
        </div>
        <el-tag effect="dark">推荐主流程</el-tag>
      </div>

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
            multiple
            :auto-upload="false"
            :show-file-list="true"
            :on-change="handleUploadChange"
            :on-remove="handleUploadRemove"
          >
            <el-icon class="el-icon--upload"><Upload /></el-icon>
            <div class="el-upload__text">拖拽文件到这里，或 <em>点击选择多个文件</em></div>
            <template #tip>
              <div class="upload-tip">支持 `txt / md / pdf / docx`，可同时选择多个文件批量入库。</div>
            </template>
          </el-upload>
        </el-form-item>
      </el-form>

      <div class="toolbar-actions">
        <el-button type="primary" :icon="Upload" :loading="uploading" @click="submitUploadDocument">
          上传并解析入库
        </el-button>
      </div>
    </section>

    <section class="panel span-6 section-card">
      <div class="section-heading">
        <div>
          <div class="panel-kicker">Pipeline</div>
          <h3>执行说明</h3>
        </div>
      </div>

      <div class="stack-list">
        <article class="stack-item">
          <div class="stack-title">1. 上传源文件</div>
          <p class="stack-text">选择文档后，后端先保存原始文件，再根据文件类型选择解析器。</p>
        </article>
        <article class="stack-item">
          <div class="stack-title">2. 自动切分</div>
          <p class="stack-text">系统根据结构化、半结构化或非结构化策略切分内容，并生成 Chunk 元数据。</p>
        </article>
        <article class="stack-item">
          <div class="stack-title">3. 写入向量库</div>
          <p class="stack-text">Chunk 内容完成向量化后写入 Milvus，同时把文档元数据记录到 PostgreSQL。</p>
        </article>
        <article class="stack-item">
          <div class="stack-title">4. 跳转验证</div>
          <p class="stack-text">上传成功后可直接进入 Chunk 管理页，继续查看切分结果、检索命中和 Agent 溯源。</p>
        </article>
      </div>
    </section>

    <section class="panel span-12 section-card">
      <div class="section-heading">
        <div>
          <div class="panel-kicker">Text Fallback</div>
          <h3>纯文本快速入库</h3>
        </div>
        <el-tag effect="dark">备用方式</el-tag>
      </div>

      <el-form label-position="top">
        <el-form-item label="文件名">
          <el-input v-model="textForm.filename" placeholder="例如：product_rules.md" />
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
          <el-input v-model="textForm.content" type="textarea" :rows="10" placeholder="直接粘贴需要入库的文本内容" />
        </el-form-item>
      </el-form>

      <div class="toolbar-actions">
        <el-button type="primary" plain :icon="Check" :loading="textSubmitting" @click="submitTextDocument">
          文本直接入库
        </el-button>
      </div>
    </section>

    <section class="panel span-12 section-card">
      <div class="section-heading">
        <div>
          <div class="panel-kicker">Recent Documents</div>
          <h3>最近入库结果</h3>
        </div>
        <el-tag effect="dark">{{ documentStore.documents.length }} 份文档</el-tag>
      </div>

      <el-table v-loading="documentStore.loading" :data="latestDocuments" stripe>
        <el-table-column prop="filename" label="文件名" min-width="240" />
        <el-table-column prop="knowledge_base" label="知识库" min-width="120" />
        <el-table-column prop="file_type" label="类型" width="100" />
        <el-table-column prop="chunk_count" label="Chunks" width="100" />
        <el-table-column label="大小" width="120">
          <template #default="scope">{{ formatFileSize(scope.row.file_size) }}</template>
        </el-table-column>
        <el-table-column label="更新时间" min-width="160">
          <template #default="scope">{{ formatDateTime(scope.row.updated_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="260" fixed="right">
          <template #default="scope">
            <div class="inline-actions">
              <el-button size="small" @click="router.push({ name: 'chunks', query: { documentId: scope.row.id } })">
                查看切分
              </el-button>
              <el-button size="small" @click="router.push({ name: 'retrieval', query: { keyword: scope.row.filename } })">
                检索调试
              </el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>
    </section>
  </div>
</template>
