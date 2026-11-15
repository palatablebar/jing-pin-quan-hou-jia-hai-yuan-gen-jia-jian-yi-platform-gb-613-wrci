import { api } from '../api.js';
import { BRAND } from '../config.js';
import { barList, emptyState, errorBox, errorMessage, fmtDate, fmtTime, trendChart } from '../ui.js';
import { kpiTag, money, signedPct, gapTone } from '../components/price.js';

function topRiskList(items) {
  if (!items.length) return emptyState({ title: '没有待审批的风险项', hint: '今天的竞品价都在规则区间内。' });
  return `<ol class="risk-list">${items
    .map(
      (item) => `<li>
        <div class="rl-main">
          <b>${item.sku_name}</b>
          <span class="mono muted">${item.sku_code} · ${item.category_label}</span>
        </div>
        <div class="rl-price">
          <span class="rl-cur money">${money(item.current_price)}</span>
          <span class="rl-arrow">→</span>
          <span class="rl-sug money">${money(item.suggested_price)}</span>
          <span class="gap ${gapTone(item.gap_pct)}">${signedPct(item.gap_pct)}</span>
          <span class="badge ${item.risk === 'high' ? 'high' : item.risk === 'medium' ? 'medium' : 'low'}">${item.risk_label}</span>
        </div>
      </li>`,
    )
    .join('')}</ol>`;
}

export const overviewPage = {
  async render(view, ctx) {
    view.innerHTML = '<div class="empty"><div class="mark">正在拉取今日价签…</div></div>';
    let data;
    try {
      data = await api.get('/api/overview');
    } catch (err) {
      view.innerHTML = errorBox(errorMessage(err));
      view.querySelector('#retry-btn')?.addEventListener('click', () => overviewPage.render(view, ctx));
      return;
    }
    const latest = data.latest_run;
    view.innerHTML = `
      <section class="overview-head">
        <div class="oh-copy">
          <div class="eyebrow">TODAY · ${data.latest_capture_on || '—'}</div>
          <h2>今天要跟到哪一档？</h2>
          <p class="muted">${BRAND.subtitle} 待审批 ${data.pending_total} 条，其中高风险 ${data.high_risk_total} 条；平均价差 ${signedPct(data.avg_gap_pct)}，平均券后折扣 ${Number(data.avg_discount_pct).toFixed(2)}%。</p>
        </div>
        <div class="oh-status">
          <span class="dot ${data.worker_alive ? 'ok' : 'bad'}"></span>
          <span class="mono">${data.worker_alive ? 'worker 心跳在岗' : 'worker 心跳超时'}</span>
          <span class="mono muted">最近运行 ${latest ? latest.run_no : '—'}</span>
        </div>
      </section>

      <section class="kpi-grid" data-testid="overview-kpis">
        ${kpiTag({ label: '竞品店铺', value: data.competitors_total, suffix: '家', hint: '抖音 / 天猫 / 京东 / 拼多多 / 小红书 / 微店' })}
        ${kpiTag({ label: '自有 SKU', value: data.skus_total, suffix: '个', hint: '带成本、底价与目标毛利' })}
        ${kpiTag({ label: '抓价快照', value: data.snapshots_total, suffix: '条', hint: `近 3 天，含券配置` })}
        ${kpiTag({ label: '待审批建议', value: data.pending_total, suffix: '条', hint: `累计 ${data.advices_total} 条`, tone: 'accent' })}
        ${kpiTag({ label: '高风险', value: data.high_risk_total, suffix: '条', hint: '破底价或毛利 < 5%', tone: data.high_risk_total ? 'danger' : '' })}
        ${kpiTag({ label: '平均价差', value: signedPct(data.avg_gap_pct), suffix: '', hint: `平均建议毛利 ${Number(data.avg_margin_pct).toFixed(2)}%`, tone: 'zinc' })}
      </section>

      <div class="grid-2">
        <section class="panel">
          <div class="panel-head"><h2>先处理这几条</h2><span class="meta">pending · 按风险与价差排序</span></div>
          <div class="panel-body">${topRiskList(data.top_risk)}</div>
        </section>
        <section class="panel">
          <div class="panel-head"><h2>类目平均价差</h2><span class="meta">gap%</span></div>
          <div class="panel-body">
            ${
              data.category_gap.length
                ? `<div class="bars">${data.category_gap
                    .map(
                      (item) => `<div class="bar-row">
                        <span>${item.label}</span>
                        <div class="bar-track"><div class="bar-fill ${item.avg_gap_pct < -10 ? 'danger' : ''}" style="width:${Math.min(100, Math.abs(item.avg_gap_pct) * 4)}%"></div></div>
                        <span class="mono">${signedPct(item.avg_gap_pct)}</span>
                      </div>`,
                    )
                    .join('')}</div>
                    <p class="muted tiny" style="margin:10px 0 0">条长按 |价差|×4 排版，红色为降幅超过 10% 的类目。</p>`
                : emptyState({ title: '还没有待审批建议', hint: '去「抓价快照」看看今天的采集结果。' })
            }
          </div>
        </section>
      </div>

      <div class="grid-2">
        <section class="panel">
          <div class="panel-head"><h2>风险与审批结构</h2><span class="meta">risk / status</span></div>
          <div class="panel-body two-col">
            <div>
              <div class="section-label">风险等级（待审批）</div>
              ${barList(data.risk)}
            </div>
            <div>
              <div class="section-label">审批状态（累计）</div>
              ${barList(data.status, 'ok')}
            </div>
          </div>
        </section>
        <section class="panel">
          <div class="panel-head"><h2>最近一次测算</h2><span class="meta">latest run</span></div>
          <div class="panel-body">
            ${
              latest
                ? `<dl class="kv">
                    <dt>运行号</dt><dd class="mono">${latest.run_no}</dd>
                    <dt>快照日期</dt><dd>${fmtDate(latest.captured_on)}</dd>
                    <dt>状态</dt><dd><span class="badge ${latest.status === 'success' ? 'ok' : 'warn'}">${latest.status_label}</span></dd>
                    <dt>输入/产出</dt><dd class="mono">${latest.input_count} 快照 → ${latest.output_count} 条建议</dd>
                    <dt>开始</dt><dd>${fmtTime(latest.started_at)}</dd>
                  </dl>
                  <div class="section-label" style="margin-top:14px">近 7 天新增建议</div>
                  ${trendChart(data.trend)}`
                : emptyState({ title: '还没有测算运行', hint: '先在「抓价快照」页发起一次测算。' })
            }
          </div>
        </section>
      </div>`;
  },
};

export default overviewPage;
