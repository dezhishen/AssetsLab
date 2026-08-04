# AssetsLab 工作流前端

Vue 3 + Element Plus + Tailwind CSS + Vite（pnpm）工程化的工作流控制台与流程向导。
构建产物由 Python 预览服务（`workflow/tools/lan_preview_server.py`）静态 serve。

## 开发

```bash
pnpm install          # 安装依赖（首次）
pnpm dev              # 本地开发（Vite dev server，/api、/run 代理到 :8765）
```

## 构建

```bash
pnpm build            # 产物输出到 dist/
```

`lan_preview_server.py` 启动时优先 serve `workflow/web/dist`（Vue 制品），
回退到 `--directory`（默认 <repo>/dist）。`/api/*`、`/run/*` 与 `/dist/*` 保留。

## 页面

| 路由 | 说明 |
|---|---|
| `#/console` | 控制台：实例管理、新建实例（定义 + 参数模板 + 体型模板）、动作预览台 |
| `#/wizard?id=<workflow_id>` | 分步流程向导（上一步/下一步、调参、运行） |

## 数据流

前端通过 `workflowApi`（`src/api.js`）调用 `/api/workflow/*`，由 Python 服务端
进程内驱动同一 SDK（与 CLI 平级，二者互不依赖）。
