import { api } from '../api.js';
import { session } from '../store.js';
import { BRAND } from '../config.js';
import { errorMessage, esc, toast } from '../ui.js';

export const loginPage = {
  async render(root, ctx) {
    root.className = 'login-host';
    root.innerHTML = `
      <div class="login-print">
        <section class="print-stage">
          <div class="eyebrow">${esc(BRAND.edition)} · 价签打印机</div>
          <h1>页面价不是<br /><em>到手价</em></h1>
          <p class="tagline">${esc(BRAND.loginLead)}</p>

          <div class="printer" aria-hidden="true">
            <div class="printer-body">
              <span class="printer-led"></span>
              <b>PW-320</b>
              <span class="printer-meta">thermal · 58mm</span>
            </div>
            <div class="printer-slot"></div>
            <div class="ticket-strip">
              <article class="ticket">
                <header><b>泊岸家居</b><span>样例价签</span></header>
                <div class="ticket-price">
                  <span>券后到手</span>
                  <b>¥279.00</b>
                  <em>凑 2 件 ¥244.00</em>
                </div>
                <dl>
                  <div><dt>页面价</dt><dd>¥299.00</dd></div>
                  <div><dt>满300减40</dt><dd>未触发（n=1）</dd></div>
                  <div><dt>店铺券</dt><dd>−¥20.00</dd></div>
                  <div><dt>平台券</dt><dd>每满300减50</dd></div>
                </dl>
                <div class="barcode" aria-hidden="true"></div>
                <footer>PB-SOFA-001 · 验收样例</footer>
              </article>
              <article class="ticket ghost">
                <header><b>跟价建议</b><span>守护底价</span></header>
                <div class="ticket-price small">
                  <span>建议价</span>
                  <b>¥284.58</b>
                  <em>毛利 32.74%</em>
                </div>
                <footer>竞品 P25 ¥279.00 · 不破底价 ¥239.25</footer>
              </article>
            </div>
          </div>

          <div class="print-points">
            ${BRAND.loginPoints
              .map(([no, text]) => `<div class="print-point"><i>${esc(no)}</i><span>${esc(text)}</span></div>`)
              .join('')}
          </div>
        </section>

        <section class="login-form-wrap">
          <form class="login-card" id="login-form" novalidate>
            <div>
              <div class="brand">${esc(BRAND.title)}</div>
              <div class="sub">内部账号登录。三个演示账号权限不同：主管可审批与导出，运营可跑测算，店长只读且成本脱敏。</div>
            </div>
            <div class="field">
              <label for="email">邮箱</label>
              <input id="email" name="email" type="email" autocomplete="username" value="admin@${esc(BRAND.short)}.io" required />
            </div>
            <div class="field">
              <label for="password">密码</label>
              <input id="password" name="password" type="password" autocomplete="current-password" value="Demo@2026" required />
            </div>
            <div class="form-error" id="login-error" role="alert"></div>
            <button class="btn accent" id="login-submit" type="submit">打印今天的价签</button>
            <div class="login-hint">
              演示账号（密码 <code>Demo@2026</code>）：<br />
              <code>admin@${esc(BRAND.short)}.io</code> 定价主管 · <code>analyst@${esc(BRAND.short)}.io</code> 价格运营 ·
              <code>viewer@${esc(BRAND.short)}.io</code> 店长只读
            </div>
          </form>
        </section>
      </div>`;

    const form = root.querySelector('#login-form');
    const errorNode = root.querySelector('#login-error');
    const submit = root.querySelector('#login-submit');
    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      errorNode.textContent = '';
      submit.disabled = true;
      submit.textContent = '正在核对账号…';
      try {
        const result = await api.post('/api/auth/login', {
          email: form.email.value.trim(),
          password: form.password.value,
        });
        session.set(result.access_token, result.user);
        toast(`欢迎回来，${result.user.display_name}`);
        location.hash = '#/overview';
        await ctx.reload();
      } catch (err) {
        errorNode.textContent = err.code === 'AUTH_INVALID' ? '账号或密码不正确' : errorMessage(err);
      } finally {
        submit.disabled = false;
        submit.textContent = '打印今天的价签';
      }
    });
  },
};

export default loginPage;
