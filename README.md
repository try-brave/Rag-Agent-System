# RAG Agent System

一个面向知识库问答的全链路 RAG 系统，包含：

- 后端 RAG 入库、检索、Agent 对话服务
- 前端管理工作台
- 文档上传与纯文本入库
- Chunk 切分可视化与人工编辑
- 检索调试台
- Agent 流式对话与来源溯源展示

---

## 1. 项目目标

本系统解决的是一个典型的知识管理与问答问题：

1. 把业务文档、说明文档、规则文档、PDF、Markdown、Docx 等内容统一纳入知识库。
2. 在入库阶段完成解析、切分、向量化、元数据落库。
3. 在查询阶段支持向量检索、降级检索、溯源展示。
4. 在问答阶段支持 Agent 对话、流式输出、工具调用观测、来源 Chunk 展示。
5. 在前端提供完整的知识管理控制台，而不是只提供接口。

---

## 2. 当前已完成功能

### 2.1 后端能力

- FastAPI 服务启动、依赖预热、健康检查
- PostgreSQL / Redis / Milvus 连接与状态探测
- 文档上传入库
- 纯文本快速入库
- 文档解析：
  - `txt`
  - `md`
  - `pdf`
  - `docx`
- 三种切分策略：
  - `structured`
  - `semi_structured`
  - `unstructured`
- Chunk 元数据持久化
- 向量写入 Milvus
- 文档列表查询
- Chunk 列表查询与编辑
- 文档重建索引
- 检索调试接口
- Agent 同步问答
- Agent 流式 SSE 问答
- 会话列表、历史记录、删除会话
- 回答来源 `source_chunks` 返回
- 向量检索日志与调试日志输出

### 2.2 前端能力

- 工作台式布局：侧栏 + 顶栏 + 内容区
- 总览看板
- 独立“上传入库”页面
- 文档管理页面
- Chunk 管理页面
- 检索调试页面
- Agent 对话页面
- 流式消息接收与渲染
- 工具事件与来源片段展示
- 后端连接状态显示
- 上传、纯文本入库、索引重建、检索、聊天等完整交互链路

---

## 3. 技术栈

### 3.1 后端

- Python 3.10+
- FastAPI
- SQLAlchemy 2.x
- Pydantic 2.x
- Redis
- PostgreSQL
- Milvus
- LangChain 1.x
- LangGraph 1.x
- langgraph-checkpoint-postgres
- DashScope / Tongyi

### 3.2 前端

- Vue 3
- Vite
- TypeScript
- Pinia
- Vue Router
- Axios
- Element Plus

---

## 4. 目录结构

```text
rag_agent
├── backend
│   ├── app
│   │   ├── agent          # Agent 构建、工具、提示词、memory、trace
│   │   ├── api/v1         # REST API 路由
│   │   ├── core           # PostgreSQL / Redis / Milvus / Embedding / LLM
│   │   ├── models         # ORM 模型
│   │   ├── rag            # loader / ingest / retriever / splitters
│   │   ├── schemas        # Pydantic 请求响应模型
│   │   ├── services       # 业务服务层
│   │   └── utils          # 日志、SSE、存储、文本工具
│   ├── storage/uploads    # 上传原始文件落盘目录
│   ├── tests              # 基础测试
│   ├── .env               # 运行配置
│   ├── requirements.txt
│   └── run.py             # 启动入口
├── front/rag_front
│   ├── src/api            # 前端 API 封装
│   ├── src/layouts        # 工作台布局
│   ├── src/router         # 路由
│   ├── src/stores         # Pinia store
│   ├── src/views          # 页面
│   └── src/types          # TS 数据契约
├── CONFIG_REFERENCE.md    # 环境配置说明
├── rule.md                # 编码规范
└── README.md
```

---

## 5. 系统整体架构

### 5.1 架构分层

系统可以分为 6 层：

1. 展示层：Vue 前端工作台
2. API 层：FastAPI 路由
3. 服务层：Document / Chunk / Retrieval / Chat Service
4. RAG 核心层：Loader / Splitter / Ingest / Retriever
5. 数据层：
   - PostgreSQL：文档、Chunk、查询日志
   - Milvus：向量索引
   - Redis：缓存与会话类能力预留
6. 模型与 Agent 层：
   - DashScope Embedding
   - Tongyi Chat Model
   - LangChain Agent
   - LangGraph Checkpointer

### 5.2 典型调用链

#### 文档入库链路

1. 前端上传文件或提交纯文本。
2. FastAPI 接口接收请求。
3. `DocumentService` 调用 `ingest_*` 方法。
4. `loader.py` 将源文档解析为统一的 `LoadedDocument`。
5. `ingest.py` 根据 section 类型自动选择切分策略。
6. 生成 `Chunk` 记录并写入 PostgreSQL。
7. 使用 Embedding 模型向量化文本。
8. 将向量与 metadata 写入 Milvus。
9. 更新文档状态与 chunk 数量。
10. 前端在文档页、Chunk 页、检索页中可立即看到结果。

#### 检索链路

1. 用户输入查询。
2. 后端优先走 Milvus 相似度检索。
3. 如果 Milvus 检索失败或没有结果，则降级到 PostgreSQL 模糊匹配。
4. 返回 Chunk 内容、score、文件名、页码、切分策略、标题等信息。

#### Agent 对话链路

1. 前端发起 `/api/v1/chat/stream`。
2. 后端先做一次确定性的知识库预检索。
3. 命中的片段作为 `sources` 事件先发回前端。
4. 同时把预检索结果拼入 Agent 上下文。
5. Agent 继续执行工具/模型推理。
6. 前端实时接收：
   - `status`
   - `token`
   - `tool_call`
   - `tool_result`
   - `tool_error`
   - `sources`
   - `done`
7. 最终前端展示回答、工具轨迹、命中文档与来源 Chunk。

---

## 6. 后端模块说明

### 6.1 配置中心

配置由 `backend/app/config.py` 统一管理，当前集中维护：

- 应用运行配置
- CORS 配置
- DashScope API Key
- Embedding 模型配置
- Milvus 地址与集合名
- PostgreSQL DSN
- Redis URL
- 上传目录与大小限制

特点：

- 所有依赖统一入口，不在业务代码里散落
- `.env` 与字段一一对应，便于排查
- 通过 `BaseSettings` 自动加载

### 6.2 API 路由

当前 API 前缀为：

```text
/api/v1
```

主要路由：

#### 文档相关

- `POST /documents/ingest-text`
- `POST /documents/upload`
- `GET /documents`
- `GET /documents/splitters/options`
- `GET /documents/{document_id}`
- `GET /documents/{document_id}/chunks`
- `POST /documents/{document_id}/rebuild-index`

#### Chunk 相关

- `GET /chunks`
- `GET /chunks/{chunk_id}`
- `PATCH /chunks/{chunk_id}`

#### 检索相关

- `POST /retrieval/search`

#### 聊天相关

- `POST /chat`
- `POST /chat/stream`
- `GET /chat/sessions`
- `GET /chat/sessions/{session_id}/history`
- `DELETE /chat/sessions/{session_id}`

#### 系统健康检查

- `GET /health`

---

## 7. 数据库设计

本项目当前的关系型数据库核心表有 3 张：

- `document`
- `chunk`
- `query_log`

所有业务表都带统一时间字段：

- `created_at: DateTime(timezone=True)`
- `updated_at: DateTime(timezone=True)`

### 7.1 `document` 表

用途：存储文档级元信息，不直接存储切分后的细粒度内容。

| 字段名 | 类型 | 可空 | 说明 |
|---|---|---:|---|
| `id` | `String(36)` | 否 | 文档主键，UUID |
| `knowledge_base` | `String(100)` | 否 | 所属知识库名称 |
| `filename` | `String(255)` | 否 | 原始文件名 |
| `file_type` | `String(32)` | 否 | 文件类型，如 `pdf/md/docx/txt` |
| `source_path` | `String(500)` | 是 | 文件在服务器的存储路径 |
| `file_size` | `BigInteger` | 是 | 文件大小，单位字节 |
| `status` | `String(32)` | 否 | 文档状态，如 `uploaded/parsed/indexed/failed` |
| `chunk_count` | `Integer` | 否 | 当前文档生成的 chunk 数量 |
| `summary` | `Text` | 是 | 文档摘要或解析摘要 |
| `created_at` | `DateTime(timezone=True)` | 否 | 创建时间 |
| `updated_at` | `DateTime(timezone=True)` | 否 | 更新时间 |

关系：

- `document` 1 对多 `chunk`

### 7.2 `chunk` 表

用途：这是系统实现“切分可视化”和“答案溯源”的核心表。

| 字段名 | 类型 | 可空 | 说明 |
|---|---|---:|---|
| `id` | `String(36)` | 否 | Chunk 主键，UUID |
| `document_id` | `ForeignKey(document.id)` | 否 | 所属文档 ID |
| `chunk_index` | `Integer` | 否 | 在文档中的顺序编号 |
| `content` | `Text` | 否 | Chunk 正文 |
| `metadata_json` | `JSON` | 否 | 结构化元数据 |
| `token_count` | `Integer` | 否 | 预估 token 数量 |
| `page_number` | `Integer` | 是 | 来源页码 |
| `start_offset` | `Integer` | 是 | 原文起始偏移量 |
| `end_offset` | `Integer` | 是 | 原文结束偏移量 |
| `vector_id` | `String(128)` | 是 | Milvus 对应向量 ID |
| `enabled` | `Boolean` | 否 | 是否参与检索 |
| `created_at` | `DateTime(timezone=True)` | 否 | 创建时间 |
| `updated_at` | `DateTime(timezone=True)` | 否 | 更新时间 |

`metadata_json` 当前承载的核心溯源字段包括：

- `chunk_id`
- `document_id`
- `knowledge_base`
- `filename`
- `file_type`
- `parser_name`
- `chunk_index`
- `splitter_name`
- `source_path`
- `section_type`
- `section_title`
- `section_index`
- `page_number`
- `vector_id`
- `manual_edited`

这里有一个非常关键的设计认知：

- **PostgreSQL `chunk.metadata_json` 是当前系统的业务主元数据存储。**
- **Milvus 中也会带一份 metadata，但它更偏“检索时使用的副本”，不是唯一事实来源。**

也就是说，当前元数据是“双写”结构，但职责并不相同：

#### PostgreSQL 中存什么

PostgreSQL 的 `chunk` 表负责存储：

- 可编辑的正文 `content`
- 可管理的元数据 `metadata_json`
- 开关状态 `enabled`
- `page_number / start_offset / end_offset`
- `vector_id`
- 与文档的关系 `document_id`

这部分是：

- 前端 Chunk 管理页直接读取的数据源
- 文档重建索引时的参考数据
- 业务管理和人工编辑的主数据

#### Milvus 中存什么

Milvus 中存的是“检索用向量记录”，每条记录除了向量本身，还会附带 metadata 副本，例如：

- `chunk_id`
- `document_id`
- `filename`
- `file_type`
- `parser_name`
- `splitter_name`
- `section_type`
- `section_title`
- `page_number`
- `source_path`

这部分主要用于：

- 相似度检索时直接返回足够的上下文
- 命中后快速构造前端检索结果和来源信息
- 避免每次检索都必须先回表拼接基础信息

因此可以把当前设计理解成：

- **PostgreSQL = 主数据 + 可管理数据**
- **Milvus = 检索索引 + 元数据副本**

如果两边字段都存在，以 PostgreSQL 中的 `chunk` 记录为准。

### 7.3 `query_log` 表

用途：存储问答日志、来源引用和会话数据，支撑聊天历史与审计。

| 字段名 | 类型 | 可空 | 说明 |
|---|---|---:|---|
| `id` | `String(36)` | 否 | 查询日志主键，UUID |
| `session_id` | `String(100)` | 是 | 会话 ID |
| `user_question` | `Text` | 否 | 用户问题 |
| `answer` | `Text` | 是 | 最终回答 |
| `route` | `String(50)` | 否 | 处理链路，如 `rag/sql/web` |
| `latency_ms` | `Integer` | 是 | 处理耗时 |
| `source_chunks` | `JSON` | 否 | 回答引用的来源片段摘要 |
| `created_at` | `DateTime(timezone=True)` | 否 | 创建时间 |
| `updated_at` | `DateTime(timezone=True)` | 否 | 更新时间 |

---

## 8. Milvus 向量库设计

### 8.1 当前用途

Milvus 主要承担两类能力：

1. RAG 知识库向量检索
2. Agent 记忆/会话持久化的扩展能力预留

当前代码中，知识库主集合由以下配置决定：

- `MILVUS_COLLECTION`

### 8.2 当前向量字段

当前向量维度：

- `1536`

对应模型：

- `text-embedding-v1`

当前索引配置：

- `index_type = AUTOINDEX`
- `metric_type = COSINE`

### 8.3 当前知识库集合中的字段形态

根据当前代码写入方式和现有集合界面，Milvus 知识库集合中通常可以看到以下字段：

| 字段名 | 类型 | 说明 |
|---|---|---|
| `pk` | `Int64` | 向量主键，Milvus 自动生成 |
| `text` | `VarChar(65535)` | 原始 Chunk 文本 |
| `vector` | `FloatVector(1536)` | 文本向量 |
| `chunk_id` | `VarChar` | 关联 PostgreSQL 中的 Chunk ID |
| `document_id` | `VarChar` | 关联 PostgreSQL 中的 Document ID |
| `filename` | `VarChar` | 原始文件名 |
| `file_type` | `VarChar` | 文件类型 |
| `splitter_name` | `VarChar` | 切分策略 |
| `parser_name` | `VarChar` | 解析器名称 |
| `section_type` | `VarChar` | section 类型 |
| `section_title` | `VarChar` | 节标题 |
| `page_number` | 数值或 metadata 映射字段 | 来源页码 |
| `source_path` | `VarChar` | 源文件路径 |

说明：

- PostgreSQL 是业务主数据源。
- Milvus 是检索索引和向量召回层。
- `chunk_id` 和 `document_id` 负责把向量结果反查回关系库与前端溯源。

---

## 9. RAG 知识管理方式

本系统不是把文档当成一整块黑盒文本，而是按“文档 -> section -> chunk -> 向量”方式进行知识管理。

### 9.1 知识对象层级

#### 第 1 层：文档级

由 `document` 表管理，负责：

- 文档身份
- 文件类型
- 所属知识库
- 源文件路径
- 文档状态
- chunk 数量

#### 第 2 层：section 级

由 `loader.py` 解析阶段产生，负责：

- PDF 按页
- Markdown 按标题
- Docx 按标题块
- 纯文本按整体 section

这一层不单独落表，但 section metadata 会进入 Chunk metadata。

#### 第 3 层：chunk 级

由切分器生成，负责：

- 最终检索粒度
- token 数量
- offset
- page_number
- 标题与章节信息
- parser / splitter 信息

#### 第 4 层：向量级

由 Embedding 后写入 Milvus，负责：

- 语义检索
- 相似度召回
- 反向追踪 chunk_id/document_id

### 9.2 解析策略

#### txt

- 编码自动探测
- 解析器：`plain_text_loader`
- section 类型：`full_text`

#### md

- 按 Markdown 标题分段
- 解析器：`markdown_loader`
- section 类型：`markdown_heading`

#### pdf

- 按页抽取文本
- 解析器：`pypdf_loader`
- section 类型：`pdf_page`

#### docx

- 按 Heading 标题块聚合
- 解析器：`docx_loader`
- section 类型：`docx_heading_block`

### 9.3 切分策略

#### `structured`

适用于：

- 字段定义
- 参数说明
- SQL / DDL
- 配置项列表

特点：

- 优先保持条目语义完整
- 按结构化行模式分块

#### `semi_structured`

适用于：

- Markdown / Docx 标题段
- 方案文档
- 业务说明文档

特点：

- 优先按段落块聚合
- 超长时再二次拆分

#### `unstructured`

适用于：

- 普通自然语言文本

特点：

- 按长度 + 分隔符切分
- 保留 overlap

### 9.4 元数据驱动的知识管理

本系统的知识管理不是“只存向量”，而是“向量 + 关系数据 + 元数据联动”：

- PostgreSQL 负责业务事实和可管理性
- Milvus 负责召回效率
- `metadata_json` 负责溯源能力

这也是为什么前端能直接展示：

- 来源文件名
- 页码
- 标题
- splitter
- parser
- offset

### 9.5 元数据到底存在哪里

这一节专门回答“知识库管理的元数据到底存哪里”的问题。

#### 结论

当前元数据不是只存在 Milvus，也不是只存在 PostgreSQL，而是：

1. **主存储在 PostgreSQL**
2. **检索副本在 Milvus**

#### 为什么这么设计

如果只把元数据存在 Milvus，会有几个问题：

- 不适合做后台管理
- 不适合人工编辑
- 不适合复杂筛选和审计
- 不适合做文档级管理关系

如果只把元数据存在 PostgreSQL，也会有问题：

- 每次向量检索后都要回表补字段
- 检索链路更重
- 返回前端溯源信息时更麻烦

所以当前采用的是“两层存储”：

##### 第一层：PostgreSQL 主元数据

位置：

- `document` 表
- `chunk` 表中的 `metadata_json`
- `query_log` 表中的 `source_chunks`

适合做：

- 后台管理
- Chunk 编辑
- 文档查看
- 会话回放
- 重建索引
- 审计与调试

##### 第二层：Milvus 检索副本

位置：

- 向量集合中的 metadata 字段

适合做：

- 向量召回后直接返回来源信息
- 低成本构造检索命中结果
- Agent 回答时附带来源摘要

#### 两边数据怎么对应

通过这些字段关联：

- `chunk_id`
- `document_id`
- `vector_id`

关系可以理解为：

```text
document(1) -> chunk(N) -> milvus vector(N)
```

其中：

- `document.id` 对应多个 `chunk.document_id`
- `chunk.id` 会被写入 Milvus metadata 中的 `chunk_id`
- `chunk.vector_id` 会记录 Milvus 中那条向量记录的主键

---

### 9.6 入库时元数据怎么同步

当前同步逻辑主要在 `backend/app/rag/ingest.py`。

#### 第一步：生成 PostgreSQL 元数据

在 `ingest_loaded_document()` 中，系统先构造 `Chunk` 模型：

- `content`
- `metadata_json`
- `page_number`
- `start_offset`
- `end_offset`
- `token_count`

这一步完成后，PostgreSQL 已经拿到了“业务主数据”。

#### 第二步：写入 Milvus 时复制 metadata

后续在 `vector_store.add_texts()` 前，会把每个 chunk 的 `metadata_json` 再整理一份：

- 补上 `chunk_id`
- 作为 `metadatas` 参数一起写入 Milvus

然后 Milvus 返回向量 ID 列表，系统会继续：

1. 把 `vector_id` 写回 `chunk.vector_id`
2. 再把 `vector_id` 写回 PostgreSQL 的 `metadata_json`

所以最终效果是：

- PostgreSQL 中知道自己对应哪条向量
- Milvus 中知道自己对应哪个 chunk

这就形成了完整的双向关联。

---

### 9.7 编辑 Chunk 后怎么同步

这一节对应你最关心的“编辑修改后咋同步这些”的问题。

当前逻辑在：

- `backend/app/services/chunk_service.py`

#### 场景 1：只修改 metadata

如果只是修改 `metadata_json`：

1. 后端会先更新 PostgreSQL 中的 `chunk.metadata_json`
2. 如果没有改正文内容，则**当前不会立刻重建 Milvus 那条向量记录**
3. PostgreSQL 中的数据会立即是最新的

这意味着：

- 后台管理页看到的是最新 metadata
- 但 Milvus 中旧 metadata 副本可能还是旧的

所以当前版本里：

- **修改 metadata 主要先影响 PostgreSQL 主数据**
- **Milvus 的 metadata 副本不一定立刻同步**

#### 场景 2：修改正文内容 `content`

如果修改了 Chunk 正文：

1. 先删除旧的 Milvus 向量
2. 更新 PostgreSQL 中的 `content`
3. 重新计算 `token_count`
4. 重新组织 metadata
5. 重新调用 `vector_store.add_texts()`
6. 拿到新的 `vector_id`
7. 回写 PostgreSQL：
   - `vector_id`
   - `metadata_json.vector_id`
   - `manual_edited = True`

所以当前正文编辑是“强同步”的：

- PostgreSQL 更新
- Milvus 重建
- `vector_id` 刷新

#### 场景 3：重建索引

如果你在文档页点击“重建索引”：

1. 查询该文档下所有旧 Chunk
2. 尝试删除旧向量
3. 删除旧 Chunk 记录
4. 重新加载源文档或旧文本
5. 按新策略重新切分
6. 重新写 PostgreSQL
7. 重新写 Milvus

这是当前最彻底的同步方式。

#### 当前版本的一个重要边界

现在系统对“正文编辑”的同步是完整的，但对“仅 metadata 编辑”的同步还不是完全强一致。

也就是说：

- 改 `content`：会同步重建向量和 metadata 副本
- 只改 `metadata_json`：主数据已更新，但 Milvus 副本可能还是旧值

如果后续要做成严格一致，推荐增加一种能力：

- 只要 `metadata_json` 变化，也同步更新或重建 Milvus metadata

这个可以作为下一阶段增强点。

---

### 9.8 当前应该如何理解“谁是准的”

为了避免理解混乱，当前建议按下面规则看：

#### 管理后台场景

以 PostgreSQL 为准：

- 文档列表
- Chunk 管理
- 编辑后的元数据
- 会话历史

#### 向量召回场景

以 Milvus 返回结果为准，但它本质上是 PostgreSQL 元数据的“检索副本”。

#### 出现不一致时

优先相信 PostgreSQL，然后通过：

- 修改正文触发重建
- 或执行文档“重建索引”

把 Milvus 副本重新刷一遍。

---

## 10. 检索逻辑

当前检索实现位于 `backend/app/rag/retriever.py`。

### 10.1 当前策略

1. 优先调用 Milvus 向量检索：
   - `similarity_search_with_score(query, k=top_k)`
2. 如果 Milvus 报错或无结果：
   - 降级到 PostgreSQL `ilike` 模糊匹配

### 10.2 返回结果字段

检索结果统一包含：

- `chunk_id`
- `document_id`
- `filename`
- `file_type`
- `chunk_index`
- `content`
- `score`
- `splitter_name`
- `parser_name`
- `section_type`
- `section_title`
- `page_number`
- `source_path`
- `start_offset`
- `end_offset`

### 10.3 当前实现特点

- 向量优先
- 降级可用
- 前端可视化
- 结果可溯源

---

## 11. Agent 设计

### 11.1 当前使用方式

本项目基于：

- `langchain.agents.create_agent`
- LangGraph 运行时
- PostgreSQL checkpointer / 内存降级 checkpointer

### 11.2 对话能力

当前具备：

- 同步问答
- 流式问答
- 多轮会话
- 会话删除
- 会话历史查询
- 工具调用观测
- 来源片段返回

### 11.3 当前问答链路

为了避免模型完全依赖常识回答，当前在 `ChatService` 中增加了“预检索”机制：

1. 用户发起问题
2. 后端先做一次知识库预检索
3. 预检索到的来源片段先通过 `sources` 事件发给前端
4. 同时把这些片段拼入 Agent 上下文
5. Agent 基于这些片段继续生成回答

这样做的价值：

- 更稳定地使用知识库内容
- 前端更早看到命中的文档
- 调试时能清楚知道“到底检索了什么”

### 11.4 会话记录链路

系统当前的会话记录分成两层：

#### 第 1 层：短期记忆层

用于给 Agent 提供多轮上下文，依赖 LangGraph checkpointer：

- 优先使用 `langgraph-checkpoint-postgres`
- 如果 PostgreSQL checkpointer 初始化失败，则自动降级到 `InMemorySaver`

作用：

- 维护 `thread_id = session_id` 级别的多轮上下文
- 支撑同一会话的连续对话

注意：

- 这层偏运行时上下文
- 重点服务于 Agent 继续推理
- 不直接给前端列表页做数据源

#### 第 2 层：业务历史层

用于前端展示、历史回放、审计和排错，依赖 `query_log` 表：

- 每轮问答结束后由 `ChatService._persist_query_log()` 落库
- 存储字段包括：
  - `session_id`
  - `user_question`
  - `answer`
  - `route`
  - `latency_ms`
  - `source_chunks`

#### 写入链路

1. 前端发送聊天请求
2. 后端 `ChatService.invoke()` 或 `ChatService.stream()` 执行
3. 组装 `ChatRunResult`
4. 调用 `_persist_query_log()`
5. 写入 `query_log` 表

#### 读取链路

##### 会话列表

前端页面：

- `Agent 对话` 左侧会话列表
- `总览看板` 最近会话

后端接口：

- `GET /api/v1/chat/sessions`

服务层逻辑：

- `ChatService.list_sessions()`

实现方式：

1. 在 `query_log` 表中按 `session_id` 分组
2. 统计每个会话的最新 `created_at`
3. 统计 `message_count`
4. 取每个会话最近一条问答作为摘要
5. 返回：
   - `session_id`
   - `latest_question`
   - `latest_answer`
   - `message_count`
   - `updated_at`

##### 会话历史

前端页面：

- `Agent 对话` 中切换某个会话后显示的历史记录

后端接口：

- `GET /api/v1/chat/sessions/{session_id}/history`

服务层逻辑：

- `ChatService.get_session_history()`

实现方式：

1. 按 `session_id` 查询 `query_log`
2. 按 `created_at asc` 升序返回
3. 每条记录转换为 `ChatHistoryItem`
4. `source_chunks` 也会被一起返回给前端

##### 删除会话

前端操作：

- `Agent 对话` 左侧点击删除

后端接口：

- `DELETE /api/v1/chat/sessions/{session_id}`

服务层逻辑：

- `ChatService.clear_session()`

执行内容：

1. 删除 `query_log` 表中该 `session_id` 的历史记录
2. 调用 `clear_thread_memory(session_id)` 清理 Agent 短期记忆
3. 返回：
   - 删除的日志数量
   - memory 是否清理成功

#### 前端读取链路

前端状态管理主要由 `front/rag_front/src/stores/chat.ts` 完成：

1. 页面初始化时调用 `loadSessions()`
2. 首次获取会话列表
3. 用户切换会话时调用 `selectSession()`
4. 进一步触发 `loadHistory(sessionId)`
5. 前端把历史记录转换成 `ChatTurn[]`
6. 页面渲染：
   - 左侧会话列表
   - 中间对话流
   - 右侧执行轨迹与来源片段

所以当前“会话记录”并不是只存在前端本地，而是：

- 运行期上下文：LangGraph checkpointer
- 业务历史回放：PostgreSQL `query_log`
- 前端展示：Pinia `chat` store

这是一个“运行记忆 + 业务日志 + 前端视图状态”三层联动的设计。

---

## 12. 前端页面说明

### 12.1 总览看板

作用：

- 展示文档数、Chunk 数、会话数、后端状态
- 提供快速入口

### 12.2 上传入库

作用：

- 上传文件
- 选择知识库名称
- 选择切分策略
- 触发解析、切分、入向量库
- 查看最近入库结果

### 12.3 文档管理

作用：

- 查看文档列表
- 纯文本快速入库
- 文件上传
- 重建索引
- 跳转查看切分和检索调试

### 12.4 Chunk 管理

作用：

- 查看 Chunk 列表
- 按文档过滤
- 查看元数据
- 编辑 Chunk
- 启用/禁用检索
- 修改后重建对应向量

### 12.5 检索调试

作用：

- 手动输入 query
- 手动设置 top_k
- 直接查看命中结果
- 调试 score、页码、标题、splitter、parser

### 12.6 Agent 对话

作用：

- 发起多轮问答
- 查看流式回复
- 查看工具事件
- 查看来源 Chunk
- 查看命中文档名

---

## 13. 当前前端交互链路

推荐测试顺序：

1. 进入 `上传入库`
2. 上传文档或粘贴文本
3. 成功后跳转到 `Chunk 管理`
4. 在 `Chunk 管理` 查看切分结果
5. 在 `检索调试` 验证召回是否正确
6. 在 `Agent 对话` 发起问题并查看 `sources`

---

## 14. 环境变量

当前系统依赖以下关键环境变量：

| 变量名 | 说明 |
|---|---|
| `DASHSCOPE_API_KEY` | DashScope API Key |
| `MODEL` | 对话模型名 |
| `EMBEDDING_MODEL` | 向量模型名 |
| `MILVUS_URI` / `MILVUS_HOST` / `MILVUS_PORT` | Milvus 连接配置 |
| `MILVUS_COLLECTION` | 知识库集合名 |
| `MILVUS_DIMENSION` | 向量维度 |
| `POSTGRES_DSN` | PostgreSQL DSN |
| `REDIS_URL` | Redis 连接地址 |
| `BOCHA_API_KEY` | Web Search 预留能力 |
| `STORAGE_ROOT` | 文件存储根目录 |
| `UPLOAD_DIR_NAME` | 上传目录名 |
| `MAX_UPLOAD_SIZE_MB` | 文件上传大小限制 |

注意：

- `README` 不记录真实密钥
- 真实配置请放在 `backend/.env`
- 不要把真实密钥提交到仓库

---

## 15. 启动方式

### 15.1 后端

```bash
cd backend
pip install -r requirements.txt
python run.py
```

默认地址：

- `http://127.0.0.1:8000`
- `http://127.0.0.1:8000/api/v1/docs`

### 15.2 前端

```bash
cd front/rag_front
npm install
npm run dev
```

默认地址：

- `http://localhost:5173`

说明：

- 前端本地开发已配置代理到 `127.0.0.1:8000`
- 开发环境下 `/api/v1` 会自动转发到后端

---

## 16. 当前实现特点与边界

### 已具备的优势

- 基础链路闭环完整
- 文档管理、切分、检索、问答都能联通
- 关系库存事实、向量库存索引，职责分离清晰
- 具备较好的溯源能力
- 前端不是演示页，而是有真实业务操作台

### 当前边界

- 还没有用户级权限隔离
- 还没有知识库级权限隔离
- 还没有 Alembic 正式迁移体系
- 检索召回策略仍是第一版，可继续加入 rerank、过滤、query rewrite
- Agent 策略仍以基础 RAG 为主，可继续扩展工具编排和业务决策链

---

## 17. 后续可扩展方向

### 知识管理

- 多知识库隔离
- 标签体系
- 文档版本管理
- 文档状态流转
- 批量导入

### 检索层

- rerank
- hybrid search
- query rewrite
- metadata filter
- 知识库范围限定

### Agent 层

- 更严格的工具调用策略
- SQL / Web Search / Workflow Tool 扩展
- 更完善的记忆管理
- 更强的链路日志和调试面板

### 前端层

- 文档详情页
- 检索命中高亮
- 来源引用定位
- 上传进度与任务状态
- Dashboard 统计图表

---

## 18. 一句话总结

这不是一个只会“上传文本然后问答”的简化 Demo，而是一个已经具备以下能力的基础 RAG 平台：

- 文档解析
- 多策略切分
- 向量化入库
- Chunk 管理
- 检索调试
- Agent 问答
- 前后端联调
- 来源溯源展示
