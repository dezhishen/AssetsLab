/* API layer over the AssetsLab workflow HTTP API (lan_preview_server.py).
   The server wraps most workflow responses in a {ok, stdout} envelope where
   stdout is JSON (exactly like `--json`); template/definition/motion endpoints
   return plain JSON. This helper unwraps both. */

async function raw(path, opts = {}) {
  const res = await fetch(path, opts)
  const wrap = await res.json().catch(() => ({}))
  if (wrap.ok === false) throw new Error(wrap.error || wrap.stderr || JSON.stringify(wrap))
  if (wrap.stdout !== undefined) {
    try { return JSON.parse(wrap.stdout) }
    catch (e) { throw new Error(wrap.stdout) }
  }
  return wrap
}

const json = (body) => ({ method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })

export const workflowApi = {
  // instances
  list: () => raw('/api/workflow/list'),
  status: (id) => raw(`/api/workflow/instances/${encodeURIComponent(id)}`),
  next: (id) => raw(`/api/workflow/instances/${encodeURIComponent(id)}/next`),
  create: (payload) => raw('/api/workflow/instances', json(payload)),
  setBody: (id, body) => raw(`/api/workflow/instances/${encodeURIComponent(id)}/body`, json({ body })),
  deleteInstance: (id, payload = {}) => raw(`/api/workflow/instances/${encodeURIComponent(id)}`, {
    method: 'DELETE',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  }),
  // exported artifacts
  artifacts: () => raw('/api/artifacts'),
  instanceArtifacts: (id) => raw(`/api/workflow/instances/${encodeURIComponent(id)}/artifacts`),
  deleteArtifacts: (id) => raw(`/api/artifacts/${encodeURIComponent(id)}`, { method: 'DELETE' }),
  // actions
  run: (id, actionId, payload = {}) =>
    raw(`/api/workflow/instances/${encodeURIComponent(id)}/actions/${encodeURIComponent(actionId)}/run`, json(payload)),
  // catalog
  templates: () => raw('/api/workflow/templates'),
  bodyTemplates: () => raw('/api/workflow/body-templates'),
  definitions: () => raw('/api/workflow/definitions'),
  definition: (id) => raw(`/api/workflow/definitions/${encodeURIComponent(id)}`),
  // motion studio
  motions: () => raw('/api/motions'),
  renderMotion: (id, body) => raw(`/api/motions/${encodeURIComponent(id)}/render`, json(body)),
}

export function urlFromPath(p) {
  const i = String(p).indexOf('/run/')
  return i >= 0 ? String(p).slice(i) : null
}

export const PHASE_LABEL = {
  skeleton: '骨架流水线', test: '测试', capture: '捕获', export: '导出制品',
}
export const STATUS_LABEL = {
  pending: '待办', running: '运行中', passed: '已通过', failed: '失败', skipped: '跳过',
}
