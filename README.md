# HyGraph —— AI 知识图谱生成助手

> 输入一个知识主题（比如「Transformer」），AI 自动构建知识图谱；
> 点击节点可以无限延伸子图谱，还能基于图谱内容流式问答。
>
> 犀牛鸟实战 issue #4：Build a vibe-coded application powered by Hy3

![Python](https://img.shields.io/badge/Python-3.11+-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green)
![Hy3](https://img.shields.io/badge/AI-腾讯混元%20Hy3-orange)

---

## 功能演示

```
输入主题 → AI 生成知识图谱（ECharts 力导向图，自动保存到 MySQL）
   ↓
点击任意节点 → AI 延伸该节点的子知识点（自动关联已有节点；再次点击收回，
                收回后再点开恢复原样子节点，不再调用 AI）
   ↓
右侧问答框提问 → AI 基于当前图谱内容流式回答（打字机效果，问答自动入库）
   ↓
历史记录一键加载 → 图谱 + 问答记录完整还原；支持导出 PNG 图片 / JSON 文件
```

**两个端到端 Demo 流程：**

| Demo | 流程 |
|---|---|
| Demo 1 | 输入「Transformer」→ 生成图谱 → 点击「自注意力机制」延伸子图谱 → 拖拽/缩放探索 |
| Demo 2 | 基于已生成的图谱提问「QKV 是怎么计算的？」→ AI 流式回答 → 保存图谱 → 从历史记录重新加载 |

演示视频:【ai知识图谱助手演示】 https://www.bilibili.com/video/BV1pJ3G6MEzX/?share_source=copy_web&vd_source=8af7f8909a145e47ec1a5117ce0c3715
---

## Hy3 在系统中承担的角色

本项目**全程通过 API 调用 Hy3**（OpenAI 兼容协议），不做任何训练 / 微调 / 本地推理。Hy3 承担了全部三个核心智能角色：

| 角色 | 说明 | 调用方式 |
|---|---|---|
| 🏗️ **知识结构化引擎** | 输入主题，输出 5~12 个核心概念节点和它们的关系（严格 JSON） | `response_format={"type":"json_object"}` 强制结构化输出 |
| 🌱 **节点延伸引擎** | 围绕用户点击的节点，生成 3~6 个子知识点，自动避开已有节点 | 同上，Prompt 中传入已有节点 id 列表去重 |
| 💬 **知识问答引擎** | 把当前整张图谱的节点和关系作为上下文，回答用户问题 | `stream=True` 流式输出，配合 SSE 实现打字机效果 |

所有 Prompt 集中在 `backend/app/ai/prompts/`，是配置而不是代码，方便调优。

---

## 技术栈

| 层 | 技术 | 说明 |
|---|---|---|
| 前端 | 原生 HTML + JS + CSS（三文件，零框架） | ECharts 5 力导向图，`fetch + ReadableStream` 读 SSE 流 |
| 后端 | Python + FastAPI | 四层结构：routers → services → ai → db |
| AI | 腾讯混元 Hy3 API | OpenAI 兼容协议，官方 `openai` SDK 调用 |
| 数据库 | MySQL 8 + SQLAlchemy 2.0 (async) + aiomysql | 图谱 / 节点 / 边三张表，启动时自动建库建表 |

## 项目结构

```
hygraph/
├── README.md
├── run.bat                     # Windows 一键启动
├── .env.example                # 环境变量模板
└── backend/
    ├── requirements.txt
    ├── .env                    # 本地配置（不入仓）
    ├── app/
    │   ├── main.py             # FastAPI 入口 + 挂载静态文件
    │   ├── core/config.py      # 配置加载（.env）
    │   ├── schemas/graph.py    # Pydantic 出入参模型
    │   ├── ai/                 # ⭐ Hy3 封装层
    │   │   ├── hy3_client.py   #   单例客户端（JSON 输出 / 普通对话）
    │   │   └── prompts/        #   图谱生成 / 节点延伸 / 问答 Prompt
    │   ├── services/           # 业务编排（调 AI → 解析 → 返回）
    │   ├── routers/            # API 路由（/api/graph/*, /api/chat/ask）
    │   └── db/                 # SQLAlchemy 异步 ORM + DAL
    ├── static/                 # ⭐ 前端三文件
    │   ├── index.html
    │   ├── app.js
    │   └── style.css
    └── scripts/test_hy3.py     # Hy3 连通性测试
```

## 如何运行

**前置条件**：Python 3.11+、本地 MySQL（8.0+，记住 root 密码）、Hy3 API Key

```bash
# 1. 配置环境变量
cd backend
cp ../.env.example .env      # 然后编辑 .env，填入你的 HY3_API_KEY 和 MySQL 密码

# 2. 安装依赖（首次）
python -m venv venv
venv\Scripts\pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple   # Windows（清华镜像更快）
# source venv/bin/activate && pip install -r requirements.txt   # macOS/Linux

# 3. （可选）先验证 Hy3 Key 是否可用
venv\Scripts\python -m scripts.test_hy3

# 4. 启动
venv\Scripts\python -m uvicorn app.main:app --port 8000
```

打开浏览器访问 **http://localhost:8000** 即可使用。

> Windows 用户也可以直接双击项目根目录的 `run.bat`。
> 数据库不用手动建：应用启动时会自动 `CREATE DATABASE IF NOT EXISTS hygraph` 并建表。

## API 一览

| 方法 | 路由 | 说明 |
|---|---|---|
| POST | `/api/graph/generate` | 输入主题，生成知识图谱 |
| POST | `/api/graph/expand` | 点击节点，延伸子图谱（自动与已有节点关联） |
| POST | `/api/chat/ask` | 基于图谱的流式问答（SSE），问答自动入库 |
| GET | `/api/chat/history/{id}` | 查询某图谱的问答历史 |
| POST | `/api/graph/save` | 保存当前图谱到 MySQL（生成后前端会自动调用） |
| PUT | `/api/graph/update/{id}` | 覆盖更新图谱（延伸/收回后前端自动同步） |
| GET | `/api/graph/list` | 历史图谱列表 |
| GET | `/api/graph/load/{id}` | 加载历史图谱（含问答记录） |
| DELETE | `/api/graph/delete/{id}` | 删除历史图谱 |

---

## CodeBuddy 协作记录

本项目部分由 **CodeBuddy / WorkBuddy + Hy3** vibe-coding 协作完成，主要协作内容：

- **整体架构设计**：FastAPI 四层结构（routers / services / ai / db）+ 前端三文件零框架方案
- **前端交互**：ECharts 力导向图配置、节点点击延伸 / 收回的状态管理（`expansionMap`）、SSE 流式问答的 `ReadableStream` 读取与打字机渲染
- **数据库层**：SQLAlchemy 2.0 异步 ORM 模型、DAL 封装、启动时自动建库建表
- **调试修复**：CodeBuddy 定位并修复了前端 JS 引号未转义导致的全局 SyntaxError 等问题，并完成端到端联调测试

---

## License

MIT
