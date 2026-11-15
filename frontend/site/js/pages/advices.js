import { api } from '../api.js';
import { ENUMS, can, optionList, riskTone, statusTone } from '../config.js';
import { drawer, errorBox, errorMessage, esc, field, filterBar, kv, table, toast } from '../ui.js';
import { adviceCompare, couponText, money, signedPct } from '../components/price.js';

const state = { status: '', risk: '', q: '' };

function snapshotBlock(payload) {
  const snapshot = payload.snapshot;
  if (!snapshot) return '<p class="muted">这条建议没有关联快照。</p>';
  return `${kv([
    ['快照日期', esc(snapshot.captured_on)],
    ['页面价', `<span class="money">${money(snapshot.page_price)}</span>`],
    ['券配置', esc(couponText(snapshot))],
    ['券后 1/2/3 件', `<span class="money">${money(snapshot.unit_price_1)} / ${money(snapshot.unit_price_2)} / ${money(snapshot.unit_price_3)}</span>`],
    ['最优件数', snapshot.best_units ? `${snapshot.best_units} 件（${esc(snapshot.note || '')}）` : '—'],
  ])}`;
}

function ruleBlock(payload) {
  const masked = payload.cost_floor === undefined;
  return `${kv([
    ['跟价策略', esc(payload.rule || '—')],
    ['成本底线', masked ? '<span class="masked">脱敏</span>' : `<span class="money">${money(payload.cost_floor)}</span>`],
    ['市价上限', `<span class="money">${money(payload.market_cap)}</span>（P25×1.02 与当前价取小）`],
    ['约束命中', esc(payload.clamped_by || '无（按市价跟随）')],
    ['破底价', payload.breach ? '<span class="badge high">是</span>' : '<span class="badge low">否</span>'],
    ['样本数', `${esc(payload.samples || 0)} 次抓价`],
  ])}
  <ul class="reason-list">${(payload.reasons || []).map((reason) => `<li>${esc(reason)}</li>`).join('')}</ul>`;
}

function decideForm(advice) {
  return `<form id="decide-form" class="form-grid">
    ${field({
      label: '审批结论',
      name: 'status',
      value: 'approved',
      options: [
        { value: 'approved', label: '批准改价' },
        { value: 'rejected', label: '驳回' },
      ],
    })}
    ${field({ label: '核定改价（留空则用建议价）', name: 'approved_price', type: 'number', value: advice.suggested_price, attrs: 'step="0.01" min="0.01"' })}
    ${field({ label: '审批备注（驳回必填）', name: 'note', placeholder: '例如：毛利低于 5%，维持建议价不跟' })}
    <div class="form-error" id="decide-error"></div>
    <button class="btn accent" type="submit">提交审批</button>
  </form>`;
}

function openAdvice(view, ctx, advice) {
  const canDecide = can(ctx.user.role, 'advice:decide');
  const { root, close } = drawer({
    title: advice.sku_name,
    subtitle: `${advice.sku_code} · ${advice.competitor_name || '—'} · ${advice.run_no || ''}`,
    body: `${adviceCompare(advice)}
      ${kv([
        ['风险', `<span class="badge ${riskTone(advice.severity)}">${esc(advice.severity_label)}</span>`],
        ['动作', esc(advice.action_label)],
        ['审批状态', `<span class="badge ${statusTone(advice.status)}">${esc(advice.status_label)}</span>`],
        ['审批人', esc(advice.approver || '—')],
        ['审批备注', esc(advice.decide_note || '—')],
      ])}
      <div class="section-label">算法 B 明细（P25 锚点 / 底价约束）</div>
      ${ruleBlock(advice.payload || {})}
      <div class="section-label">算法 A 明细（这条建议依据的快照）</div>
      ${snapshotBlock(advice.payload || {})}`,
    footer: canDecide
      ? decideForm(advice)
      : '<span class="mono muted">只有定价主管可以审批；价格运营可跑测算，店长只读。</span>',
  });
  root.querySelector('#decide-form')?.addEventListener('submit', async (event) => {
    event.preventDefault();
    const form = event.target;
    try {
      const payload = {
        status: form.status.value,
        note: form.note.value.trim() || null,
      };
      if (form.approved_price.value) payload.approved_price = Number(form.approved_price.value);
      await api.patch(`/api/advices/${advice.id}/decision`, payload);
      toast('审批已记录');
      close();
      await advicesPage.render(view, ctx);
    } catch (err) {
      root.querySelector('#decide-error').textContent = errorMessage(err);
    }
  });
}

export const advicesPage = {
  async render(view, ctx) {
    let data;
    try {
      data = await api.get('/api/advices', { status: state.status, risk: state.risk, q: state.q, limit: 60 });
    } catch (err) {
      view.innerHTML = errorBox(errorMessage(err));
      view.querySelector('#retry-btn')?.addEventListener('click', () => advicesPage.render(view, ctx));
      return;
    }
    const pendingBlocked = can(ctx.user.role, 'advice:decide') ? '' : '<span class="badge info">只读视图</span>';
    view.innerHTML = `
      <section class="panel">
        <div class="panel-head">
          <h2>跟价建议与审批</h2>
          <div class="head-actions">
            <span class="meta">${data.total} 条</span>
            ${pendingBlocked}
          </div>
        </div>
        <div class="panel-body">
          ${filterBar('advice-filters', [
            field({ label: '搜索', name: 'q', value: state.q, placeholder: 'SKU / 标题' }),
            field({ label: '风险', name: 'risk', value: state.risk, options: optionList(ENUMS.risk) }),
            field({ label: '审批状态', name: 'status', value: state.status, options: optionList(ENUMS.adviceStatus) }),
          ])}
        </div>
        ${table({
          rows: data.items,
          empty: { title: '没有匹配的建议', hint: '换个筛选，或去「抓价快照」重跑一次测算。' },
          columns: [
            {
              key: 'sku_name',
              label: 'SKU / 规则',
              render: (row) =>
                `<b>${esc(row.sku_name)}</b><div class="mono muted">${esc(row.sku_code)} · ${esc(row.rule_code)}</div>`,
            },
            { key: 'p25', label: '竞品 P25', className: 'num money', render: (row) => money(row.p25) },
            { key: 'current_price', label: '当前价', className: 'num money', render: (row) => money(row.current_price) },
            {
              key: 'suggested_price',
              label: '建议价',
              className: 'num',
              render: (row) => `<b class="money">${money(row.suggested_price)}</b><div class="mono ${row.gap_pct < 0 ? 'neg' : 'pos'}">${signedPct(row.gap_pct)}</div>`,
            },
            { key: 'margin_pct', label: '建议毛利', className: 'num', render: (row) => `${Number(row.margin_pct).toFixed(2)}%` },
            { key: 'severity', label: '风险', render: (row) => `<span class="badge ${riskTone(row.severity)}">${esc(row.severity_label)}</span>` },
            { key: 'status', label: '审批', render: (row) => `<span class="badge ${statusTone(row.status)}">${esc(row.status_label)}</span>` },
          ],
        })}
      </section>`;

    const filters = view.querySelector('#advice-filters');
    filters?.addEventListener('change', () => {
      state.q = filters.querySelector('[name=q]').value.trim();
      state.risk = filters.querySelector('[name=risk]').value;
      state.status = filters.querySelector('[name=status]').value;
      advicesPage.render(view, ctx);
    });
    filters?.querySelector('[name=q]')?.addEventListener('keydown', (event) => {
      if (event.key === 'Enter') {
        state.q = event.target.value.trim();
        advicesPage.render(view, ctx);
      }
    });
    view.querySelectorAll('table.data tbody tr').forEach((row) => {
      row.addEventListener('click', () => {
        const item = data.items.find((entry) => String(entry.id) === row.dataset.id);
        if (item) openAdvice(view, ctx, item);
      });
    });
  },
};

export default advicesPage;
