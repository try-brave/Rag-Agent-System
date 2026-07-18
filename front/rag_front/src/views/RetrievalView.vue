<script setup lang="ts">
import { Search } from '@element-plus/icons-vue'
import { onMounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'

import { searchRetrieval } from '@/api/modules/retrieval'
import { notifyError } from '@/api/http'
import type { RetrievalHitItem } from '@/types/api'
import { formatScore } from '@/utils/format'

const route = useRoute()
const loading = ref(false)
const results = ref<RetrievalHitItem[]>([])
const form = reactive({
  query: String(route.query.keyword || ''),
  topK: 5,
})

function getSourceTagType(source: string | null | undefined) {
  switch (source) {
    case 'hybrid':
      return 'danger'
    case 'vector':
      return 'primary'
    case 'bm25':
      return 'warning'
    case 'postgres_fallback':
      return 'info'
    default:
      return 'info'
  }
}

function getSourceLabel(source: string | null | undefined) {
  switch (source) {
    case 'hybrid':
      return '混合融合'
    case 'vector':
      return '向量检索'
    case 'bm25':
      return 'BM25'
    case 'postgres_fallback':
      return 'PostgreSQL 兜底'
    default:
      return '未标注'
  }
}

function formatRouteLabel(item: RetrievalHitItem) {
  if (item.retrieval_sources?.length) {
    return item.retrieval_sources.map(source => getSourceLabel(source)).join(' + ')
  }
  return getSourceLabel(item.retrieval_source)
}

async function runSearch() {
  if (!form.query.trim()) {
    return
  }

  loading.value = true
  try {
    const response = await searchRetrieval(form.query, form.topK)
    results.value = response.items
  } catch (error) {
    notifyError(error, '检索调试失败')
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  if (form.query) {
    await runSearch()
  }
})
</script>

<template>
  <div class="page-grid">
    <section class="panel span-12 toolbar-card">
      <div>
        <div class="panel-kicker">Retrieval Debugger</div>
        <h2>检索链路调试台</h2>
          <p class="page-description">
            直接命中后端 `/retrieval/search`，查看 Milvus 向量检索、BM25 词法检索与 RRF 融合后的最终召回结果，并对照来源、分数、排名与切分元数据。
          </p>
      </div>
      <div class="toolbar-actions wrap grow">
        <el-input v-model="form.query" placeholder="输入检索问题或关键词" @keyup.enter="runSearch">
          <template #prefix><el-icon><Search /></el-icon></template>
        </el-input>
        <el-input-number v-model="form.topK" :min="1" :max="20" />
        <el-button type="primary" @click="runSearch">开始检索</el-button>
      </div>
    </section>

    <section class="panel span-12 section-card" v-loading="loading">
      <div class="section-heading">
        <div>
          <div class="panel-kicker">Results</div>
          <h3>召回结果</h3>
        </div>
        <el-tag effect="dark">{{ results.length }} 条</el-tag>
      </div>

      <div v-if="results.length" class="result-grid">
        <article v-for="item in results" :key="`${item.chunk_id}-${item.chunk_index}`" class="result-card">
          <div class="result-card-top">
            <div class="result-card-title-block">
              <div class="stack-title">{{ item.filename || 'unknown' }}</div>
              <div class="stack-meta">
                <span>#{{ item.chunk_index ?? '--' }}</span>
                <span>{{ item.section_title || item.section_type || '未命名片段' }}</span>
              </div>
            </div>
            <div class="result-card-badges">
              <el-tag :type="getSourceTagType(item.retrieval_source)">{{ getSourceLabel(item.retrieval_source) }}</el-tag>
              <el-tag type="success">最终 {{ formatScore(item.score) }}</el-tag>
            </div>
          </div>

          <div class="score-grid">
            <div class="score-item">
              <span class="score-label">融合分数</span>
              <strong>{{ item.fused_score != null ? formatScore(item.fused_score) : '--' }}</strong>
            </div>
            <div class="score-item">
              <span class="score-label">向量分数</span>
              <strong>{{ item.vector_score != null ? formatScore(item.vector_score) : '--' }}</strong>
            </div>
            <div class="score-item">
              <span class="score-label">BM25 分数</span>
              <strong>{{ item.bm25_score != null ? formatScore(item.bm25_score) : '--' }}</strong>
            </div>
            <div class="score-item">
              <span class="score-label">融合排名</span>
              <strong>#{{ item.rank_fused ?? '--' }}</strong>
            </div>
          </div>

          <div class="pill-row">
            <span class="meta-pill">命中路径: {{ formatRouteLabel(item) }}</span>
            <span class="meta-pill">vector rank: {{ item.rank_vector ?? '--' }}</span>
            <span class="meta-pill">bm25 rank: {{ item.rank_bm25 ?? '--' }}</span>
          </div>

          <p class="stack-text">{{ item.content }}</p>

          <div class="pill-row">
            <span class="meta-pill">splitter: {{ item.splitter_name || '--' }}</span>
            <span class="meta-pill">parser: {{ item.parser_name || '--' }}</span>
            <span class="meta-pill">page: {{ item.page_number ?? '--' }}</span>
            <span class="meta-pill">file_type: {{ item.file_type || '--' }}</span>
          </div>
        </article>
      </div>
      <el-empty v-else description="输入检索问题后查看召回结果" />
    </section>
  </div>
</template>
