import { api } from '../api.js';
import { ENUMS, can, optionList } from '../config.js';
import { drawer, errorBox, errorMessage, esc, field, filterBar, fmtTime, kv, table, toast } from '../ui.js';
import { money, priceCompare } from '../components/price.js';

const state = { q: '', category: '', competitorId: '' };

function competitorStrip(items) {
  return `<div class="competitor-strip" data-testid="competitor-strip">${items
    .map(
      (item) => `<button class="comp-card" data-comp="${item.id}" type="button">
        <span class="cc-platform">${esc(item.platform_label)}</span>
        <b>${esc(item.name)}</b>
        <span class="cc-meta mono">${esc(item.code)} · ${item.sku_count} 个 SKU</span>
        <span class="cc-foot">${item.enabled ? '在盯' : '已停用'} · 最近抓价 ${fmtTime(item.last_captured_at)}</span>
      </button>`,
    )
    .join('')}</div>`;
}

function openSku(view, ctx, sku) {
  const editable = can(ctx.user.role, 'sku:write');
  const snapshot = sku.latest_snapshot;
  const advice = sku.latest_advice;
  const { root, close } = drawer({
    title: sku.name,
    subtitle: `${sku.sku_code} · ${sku.category_label} · 对标 ${sku.competitor_name || '—'}`,
    body: `${kv([
      ['我方当前价', `<span class="money">${money(sku.current_price)}</span>`],
      ['成本', sku.cost_masked ? '<span class="masked">脱敏（只读角色）</span>' : `<span class="money">${money(sku.cost)}</span>`],
      ['底价', sku.cost_masked ? '<span class="masked">脱敏（只读角色）</span>' : `<span class="money">${money(sku.floor_price)}</span>`],
      ['目标毛利', `${Number(sku.target_margin_pct).toFixed(2)}%`],
      ['竞品货号', `<span class="mono">${esc(sku.competitor_item_id || '—')}</span>`],
      ['库存', esc(sku.stock)],
      ['备注', esc(sku.note || '—')],
    ])}
    <div class="section-label">最近一次抓价（算法 A：券后价还原）</div>
    ${
      snapshot
        ? `${priceCompare(snapshot)}
           <p class="muted tiny">${esc(snapshot.note || '')}</p>`
        : '<p class="muted">这个 SKU 还没有抓价快照。</p>'
    }
    <div class="section-label">最近一条跟价建议（算法 B）</div>
    ${
      advice
        ? `${kv([
            ['建议价', `<span class="money">${money(advice.suggested_price)}</span>`],
            ['价差', `${Number(advice.gap_pct).toFixed(2)}%`],
            ['建议毛利', `${Number(advice.margin_pct).toFixed(2)}%`],
            ['风险', esc(advice.severity_label)],
            ['状态', esc(advice.status_label)],
          ])}
          <p class="muted tiny">${esc(advice.reason || advice.summary || '')}</p>`
        : '<p class="muted">还没有跟价建议，先跑一次测算。</p>'
    }`,
    footer: editable
      ? `<form id="sku-form" class="form-grid">
          ${field({ label: '成本', name: 'cost', type: 'number', value: sku.cost ?? '', attrs: 'step="0.01" min="0"' })}
          ${field({ label: '底价', name: 'floor_price', type: 'number', value: sku.floor_price ?? '', attrs: 'step="0.01" min="0"' })}
          ${field({ label: '当前价', name: 'current_price', type: 'number', value: sku.current_price, attrs: 'step="0.01" min="0.01"' })}
          ${field({ label: '目标毛利 %', name: 'target_margin_pct', type: 'number', value: sku.target_margin_pct, attrs: 'step="0.5" min="0"' })}
          <div class="form-error" id="sku-error"></div>
          <button class="btn accent" type="submit">保存价格口径</button>
        </form>`
      : '<span class="mono muted">只读角色可查看，不能改成本与底价</span>',
  });
  root.querySelector('#sku-form')?.addEventListener('submit', async (event) => {
    event.preventDefault();
    const form = event.target;
    try {
      await api.patch(`/api/skus/${sku.id}`, {
        cost: Number(form.cost.value),
        floor_price: Number(form.floor_price.value),
        current_price: Number(form.current_price.value),
        target_margin_pct: Number(form.target_margin_pct.value),
      });
      toast('价格口径已保存（下次测算生效）');
      close();
      await catalogPage.render(view, ctx);
    } catch (err) {
      root.querySelector('#sku-error').textContent = errorMessage(err);
    }
  });
}

function openCompetitorForm(view, ctx) {
  const { root, close } = drawer({
    title: '登记竞品店铺',
    subtitle: '登记后即可挂 SKU 与跑抓价',
    body: `<form id="comp-form" class="form-grid">
      ${field({ label: '编码（小写字母/数字/横线）', name: 'code', placeholder: 'tb-xinye' })}
      ${field({ label: '店铺名', name: 'name', placeholder: '天猫 · 新叶家居旗舰店' })}
      ${field({ label: '平台', name: 'platform', value: 'taobao', options: optionList(ENUMS.platform, null) })}
      ${field({ label: '店铺地址', name: 'shop_url', placeholder: 'https://shop.example/xinye' })}
      ${field({ label: '区域', name: 'region', value: '华东' })}
      ${field({ label: '备注', name: 'note', placeholder: '改价节奏、券的类型' })}
      <div class="form-error" id="comp-error"></div>
      <button class="btn accent" type="submit">保存</button>
    </form>`,
  });
  root.querySelector('#comp-form').addEventListener('submit', async (event) => {
    event.preventDefault();
    const form = event.target;
    try {
      await api.post('/api/competitors', {
        code: form.code.value.trim(),
        name: form.name.value.trim(),
        platform: form.platform.value,
        shop_url: form.shop_url.value.trim() || null,
        region: form.region.value.trim() || null,
        note: form.note.value.trim() || null,
        capture_config: { replay: `fixture/${form.code.value.trim()}`, cron: '0 9,21 * * *' },
      });
      toast('竞品店铺已登记');
      close();
      await catalogPage.render(view, ctx);
    } catch (err) {
      root.querySelector('#comp-error').textContent =
        err.code === 'CONFLICT' ? '这个编码已被占用（409）' : errorMessage(err);
    }
  });
}

export const catalogPage = {
  async render(view, ctx) {
    let competitors;
    let skus;
    try {
      [competitors, skus] = await Promise.all([
        api.get('/api/competitors', { limit: 20 }),
        api.get('/api/skus', {
          q: state.q,
          category: state.category,
          competitor_id: state.competitorId,
          limit: 60,
        }),
      ]);
    } catch (err) {
      view.innerHTML = errorBox(errorMessage(err));
      view.querySelector('#retry-btn')?.addEventListener('click', () => catalogPage.render(view, ctx));
      return;
    }
    view.innerHTML = `
      <section class="panel">
        <div class="panel-head">
          <h2>竞品店铺</h2>
          <div class="head-actions">
            <span class="meta">${competitors.total} 家 · 点击筛选该店 SKU</span>
            ${can(ctx.user.role, 'competitor:write') ? '<button class="btn sm accent" id="new-comp">登记竞品</button>' : ''}
          </div>
        </div>
        <div class="panel-body">${competitorStrip(competitors.items)}</div>
      </section>

      <section class="panel">
        <div class="panel-head">
          <h2>自有 SKU 与价格口径</h2>
          <span class="meta">${skus.total} 个${state.competitorId ? ' · 已按店铺筛选' : ''}</span>
        </div>
        <div class="panel-body">
          ${filterBar('sku-filters', [
            field({ label: '搜索', name: 'q', value: state.q, placeholder: 'SKU 名称 / 编码' }),
            field({ label: '类目', name: 'category', value: state.category, options: optionList(ENUMS.category) }),
            field({
              label: '竞品店铺',
              name: 'competitor_id',
              value: state.competitorId,
              options: [{ value: '', label: '全部' }, ...competitors.items.map((item) => ({ value: item.id, label: item.name }))],
            }),
          ])}
        </div>
        ${table({
          rows: skus.items,
          empty: { title: '没有匹配的 SKU', hint: '清空筛选，或去登记新的 SKU。' },
          columns: [
            {
              key: 'name',
              label: 'SKU',
              render: (row) => `<b>${esc(row.name)}</b><div class="mono muted">${esc(row.sku_code)} · ${esc(row.category_label)}</div>`,
            },
            { key: 'competitor_name', label: '对标竞品', render: (row) => esc(row.competitor_name || '—') },
            { key: 'current_price', label: '当前价', className: 'num money', render: (row) => money(row.current_price) },
            {
              key: 'cost',
              label: '成本 / 底价',
              className: 'num',
              render: (row) =>
                row.cost_masked
                  ? '<span class="masked">脱敏</span>'
                  : `<span class="money">${money(row.cost)}</span><div class="mono muted">底价 ${money(row.floor_price)}</div>`,
            },
            { key: 'target_margin_pct', label: '目标毛利', className: 'num', render: (row) => `${Number(row.target_margin_pct).toFixed(2)}%` },
            { key: 'stock', label: '库存', className: 'num' },
          ],
        })}
      </section>`;

    const filters = view.querySelector('#sku-filters');
    filters?.addEventListener('change', () => {
      state.q = filters.querySelector('[name=q]').value.trim();
      state.category = filters.querySelector('[name=category]').value;
      state.competitorId = filters.querySelector('[name=competitor_id]').value;
      catalogPage.render(view, ctx);
    });
    filters?.querySelector('[name=q]')?.addEventListener('keydown', (event) => {
      if (event.key === 'Enter') {
        state.q = event.target.value.trim();
        catalogPage.render(view, ctx);
      }
    });
    view.querySelectorAll('.comp-card').forEach((card) => {
      card.addEventListener('click', () => {
        const id = card.dataset.comp;
        state.competitorId = String(state.competitorId) === String(id) ? '' : id;
        catalogPage.render(view, ctx);
      });
    });
    view.querySelectorAll('table.data tbody tr').forEach((row) => {
      row.addEventListener('click', () => {
        const item = skus.items.find((entry) => String(entry.id) === row.dataset.id);
        if (item) openSku(view, ctx, item);
      });
    });
    view.querySelector('#new-comp')?.addEventListener('click', () => openCompetitorForm(view, ctx));
  },
};

export default catalogPage;
