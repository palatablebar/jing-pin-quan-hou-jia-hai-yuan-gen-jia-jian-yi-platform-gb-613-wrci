/** 价格类共享展示组件：金额、价差、页面价 vs 券后价对照、券组合文案。
 *  被「抓价快照」「跟价建议」「竞品与 SKU」三个页面共用（同一业务组件）。 */
import { esc } from '../ui.js';

export function money(value, { sign = false, currency = '¥' } = {}) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '—';
  const num = Number(value);
  const body = Math.abs(num).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const prefix = num < 0 ? '−' : sign && num > 0 ? '+' : '';
  return `${prefix}${currency}${body}`;
}

export function signedPct(value, digits = 2) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '—';
  const num = Number(value);
  return `${num > 0 ? '+' : num < 0 ? '−' : ''}${Math.abs(num).toFixed(digits)}%`;
}

export function gapTone(value) {
  if (value === null || value === undefined) return 'flat';
  if (value <= -5) return 'down';
  if (value >= 5) return 'up';
  return 'flat';
}

export function couponText(snapshot) {
  const parts = [];
  (snapshot.full_reduction || []).forEach((tier) => parts.push(`满${tier.threshold}减${tier.minus}`));
  if (snapshot.shop_coupon) parts.push(`店铺券满${snapshot.shop_coupon.threshold}减${snapshot.shop_coupon.minus}`);
  if (snapshot.platform_coupon) parts.push(`平台每满${snapshot.platform_coupon.per}减${snapshot.platform_coupon.minus}`);
  if (snapshot.member_discount && Number(snapshot.member_discount) < 1) {
    parts.push(`会员${Math.round(Number(snapshot.member_discount) * 100)}%折`);
  }
  return parts.length ? parts.join(' ＋ ') : '无券（到手价＝页面价）';
}

/** 页面价 → 券后价 对照条：三档件数并排，最优档高亮。 */
export function priceCompare(snapshot, { compact = false } = {}) {
  const tiers = [
    { units: 1, price: snapshot.unit_price_1 },
    { units: 2, price: snapshot.unit_price_2 },
    { units: 3, price: snapshot.unit_price_3 },
  ].filter((tier) => tier.price !== null && tier.price !== undefined);
  const best = snapshot.best_units;
  return `<div class="price-compare ${compact ? 'compact' : ''}">
    <div class="pc-line">
      <span class="pc-label">页面价</span>
      <span class="pc-page money">${esc(money(snapshot.page_price))}</span>
      <span class="pc-arrow">→</span>
      <span class="pc-label">券后到手</span>
      <span class="pc-effective money">${esc(money(snapshot.unit_price_1))}</span>
      <span class="chip">${esc(signedPct(((Number(snapshot.unit_price_1) || 0) / (Number(snapshot.page_price) || 1) - 1) * 100))}</span>
    </div>
    <div class="pc-tiers">
      ${tiers
        .map(
          (tier) => `<span class="pc-tier ${tier.units === best ? 'best' : ''}">
            ${tier.units} 件 <b class="money">${esc(money(tier.price))}</b>${tier.units === best ? '<i>最优</i>' : ''}
          </span>`,
        )
        .join('')}
    </div>
  </div>`;
}

/** 一条建议的核心对照：竞品券后 → 建议价（含价差与风险）。 */
export function adviceCompare(advice) {
  return `<div class="advice-compare">
    <div class="ac-col">
      <span class="ac-label">竞品券后 P25</span>
      <b class="ac-value money">${esc(money(advice.p25))}</b>
      <span class="mono muted">P10 ${esc(money(advice.p10))} · P50 ${esc(money(advice.p50))}</span>
    </div>
    <div class="ac-arrow">→</div>
    <div class="ac-col">
      <span class="ac-label">我方当前价</span>
      <b class="ac-value money">${esc(money(advice.current_price))}</b>
      <span class="mono muted">毛利 ${Number(advice.margin_pct).toFixed(2)}%</span>
    </div>
    <div class="ac-arrow">⇒</div>
    <div class="ac-col accent">
      <span class="ac-label">建议价</span>
      <b class="ac-value money">${esc(money(advice.suggested_price))}</b>
      <span class="gap ${esc(gapTone(advice.gap_pct))}">${esc(signedPct(advice.gap_pct))}</span>
    </div>
  </div>`;
}

export function kpiTag({ label, value, suffix = '', hint = '', tone = '' }) {
  return `<div class="kpi-tag ${esc(tone)}">
    <span class="kt-label">${esc(label)}</span>
    <span class="kt-value money">${esc(value)}<em>${esc(suffix)}</em></span>
    <span class="kt-hint">${esc(hint)}</span>
    <span class="kt-notch" aria-hidden="true"></span>
  </div>`;
}
