import { api } from '../api.js';
import { can } from '../config.js';
import { errorBox, errorMessage, esc, fmtTime, table, toast } from '../ui.js';

const ACTIONS = {
  'auth.login': '登录',
  'competitor.create': '新建竞品店铺',
  'competitor.update': '修改竞品店铺',
  'sku.create': '新建 SKU',
  'sku.update': '改成本/底价',
  'rule.create': '新建规则',
  'rule.update': '改规则',
  'snapshot.capture': '快照补录',
  'run.create': '发起测算',
  'run.complete': '测算完成',
  'advice.decide': '审批建议',
  'export.advices': '导出建议',
  'export.snapshots': '导出快照',
  'http.mutation': '写请求',
};

function exportCards(isAdmin) {
  const cards = [
    {
      id: 'export-advices',
      title: '跟价建议清单',
      desc: '每条建议的竞品 P10/P25/P50、建议价、价差、毛利、风险与审批结论；同时带券后 1/2/3 件价格与命中组合。',
      path: '/api/exports/advices.csv',
      file: 'pricewatch-advices.csv',
      meta: 'advices.csv',
    },
    {
      id: 'export-snapshots',
      title: '券后价快照',
      desc: '页面价、满减、店铺券、平台券、会员折扣与算法 A 的三档券后单价，用于复核或对账。',
      path: '/api/exports/snapshots.csv',
      file: 'pricewatch-snapshots.csv',
      meta: 'snapshots.csv',
    },
    {
      id: 'export-runs',
      title: '测算运行记录',
      desc: '每次测算的输入快照数、产出建议数、高风险条数与平均价差，作为值班交接凭据。',
      path: '/api/exports/runs.csv',
      file: 'pricewatch-runs.csv',
      meta: 'runs.csv',
    },
  ];
  return `<div class="export-grid" data-testid="export-grid">${cards
    .map(
      (card) => `<article class="export-card ${isAdmin ? '' : 'locked'}">
        <div class="ec-head"><b>${esc(card.title)}</b><span class="mono">${esc(card.meta)}</span></div>
        <p class="muted">${esc(card.desc)}</p>
        <button class="btn ${isAdmin ? 'accent' : 'ghost'}" id="${esc(card.id)}" data-path="${esc(card.path)}" data-file="${esc(card.file)}" ${isAdmin ? '' : 'disabled'}>
          ${isAdmin ? '下载 CSV' : '需要定价主管权限'}
        </button>
      </article>`,
    )
    .join('')}</div>`;
}

export const exportsPage = {
  async render(view, ctx) {
    const isAdmin = can(ctx.user.role, 'export:read');
    let audit = null;
    let auditError = null;
    try {
      audit = await api.get('/api/audit', { limit: 80 });
    } catch (err) {
      auditError = err;
    }
    view.innerHTML = `
      <section class="panel">
        <div class="panel-head">
          <h2>导出清单</h2>
          <span class="meta">UTF-8 BOM · 可直接进 Excel</span>
        </div>
        <div class="panel-body">
          ${exportCards(isAdmin)}
          ${
            isAdmin
              ? ''
              : '<p class="muted tiny">当前角色可以查看页面上的一切价格结论，但导出接口由后端返回 403（真实状态码，不是前端隐藏）。</p>'
          }
        </div>
      </section>

      <section class="panel">
        <div class="panel-head">
          <h2>审计留痕</h2>
          <span class="meta">${audit ? `${audit.total} 条 · 最近 ${audit.items.length} 条` : '需要 admin 权限'}</span>
        </div>
        ${
          audit
            ? table({
                rows: audit.items,
                empty: { title: '还没有审计记录', hint: '登录、审批、导出都会留痕。' },
                columns: [
                  { key: 'created_at', label: '时间', render: (row) => fmtTime(row.created_at) },
                  { key: 'actor_email', label: '操作人', className: 'mono' },
                  { key: 'actor_role', label: '角色' },
                  { key: 'action', label: '动作', render: (row) => esc(ACTIONS[row.action] || row.action_label || row.action) },
                  { key: 'entity', label: '对象', render: (row) => `${esc(row.entity)}${row.entity_id ? ` #${esc(row.entity_id)}` : ''}` },
                  { key: 'layer', label: '层', render: (row) => `<span class="badge">${esc(row.layer)}</span>` },
                  {
                    key: 'detail',
                    label: '详情',
                    render: (row) => `<span class="mono muted ellipsis">${esc(JSON.stringify(row.detail || {}))}</span>`,
                  },
                ],
              })
            : `<div class="panel-body"><div class="empty" data-testid="audit-forbidden">
                <div class="mark">没有审计权限</div>
                <p>${esc(errorMessage(auditError))}。${
                  auditError && auditError.status === 403 ? '这是后端返回的 403，不是前端隐藏入口。' : ''
                }</p>
                <button class="btn ghost" id="retry-audit">重新请求</button>
              </div></div>`
        }
      </section>`;

    view.querySelector('#retry-audit')?.addEventListener('click', () => exportsPage.render(view, ctx));
    view.querySelectorAll('.export-card button[data-path]').forEach((button) => {
      button.addEventListener('click', async () => {
        if (button.disabled) return;
        try {
          await api.download(button.dataset.path, button.dataset.file);
          toast('已开始下载');
          exportsPage.render(view, ctx);
        } catch (err) {
          toast(errorMessage(err), 'err');
        }
      });
    });
  },
};

export default exportsPage;
