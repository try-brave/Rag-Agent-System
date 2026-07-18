import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  scrollBehavior() {
    return { top: 0 }
  },
  routes: [
    {
      path: '/',
      component: () => import('@/layouts/AppShell.vue'),
      redirect: '/dashboard',
      children: [
        {
          path: '/dashboard',
          name: 'dashboard',
          component: () => import('@/views/DashboardView.vue'),
          meta: { title: '总览看板' },
        },
        {
          path: '/ingest',
          name: 'ingest',
          component: () => import('@/views/IngestView.vue'),
          meta: { title: '上传入库' },
        },
        {
          path: '/documents',
          name: 'documents',
          component: () => import('@/views/DocumentsView.vue'),
          meta: { title: '文档管理' },
        },
        {
          path: '/chunks',
          name: 'chunks',
          component: () => import('@/views/ChunksView.vue'),
          meta: { title: 'Chunk 管理' },
        },
        {
          path: '/retrieval',
          name: 'retrieval',
          component: () => import('@/views/RetrievalView.vue'),
          meta: { title: '检索调试' },
        },
        {
          path: '/chat',
          name: 'chat',
          component: () => import('@/views/ChatView.vue'),
          meta: { title: 'Agent 对话' },
        },
      ],
    },
  ],
})

router.afterEach((to) => {
  const title = typeof to.meta.title === 'string' ? to.meta.title : 'RAG Agent Studio'
  document.title = `${title} | RAG Agent Studio`
})

export default router
