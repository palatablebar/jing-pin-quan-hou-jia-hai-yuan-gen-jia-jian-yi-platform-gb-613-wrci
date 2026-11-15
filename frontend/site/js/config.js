/**
 * 项目品牌、导航、角色权限与共享枚举（前端唯一定义处）。
 * 后端对应：backend/src/constants/{roles,enums}.py；README 列出全部出现位置。
 */
export const BRAND = {
  short: 'pricewatch',
  title: '竞品券后价还原与跟价建议台',
  org: '泊岸家居 · 电商定价组',
  edition: 'PRICE TAG · 2026',
  subtitle: '页面价不是到手价：先把券算成券后价，再决定跟到哪一档。',
  loginLead:
    '竞品页面价 299、店铺券 20、满 300 减 40 还不触发——到手价是多少、凑两件划不划算、跟到哪一档不破底价，都要能算给人看。',
  loginPoints: [
    ['01', '抓价快照保留页面价与券配置，券后价在服务端还原，不靠心算。'],
    ['02', '跟价建议按规则算：P25 锚点、成本底线、底价硬约束，逐条给理由。'],
    ['03', '审批留痕、导出可复查，吵架时能指回是哪一天哪一条快照。'],
  ],
};

export const NAV = [
  { to: '#/overview', no: '01', label: '总览', permission: 'overview:read' },
  { to: '#/catalog', no: '02', label: '竞品与 SKU', permission: 'sku:read' },
  { to: '#/snapshots', no: '03', label: '抓价快照', permission: 'snapshot:read' },
  { to: '#/advices', no: '04', label: '跟价建议', permission: 'advice:read' },
  { to: '#/exports', no: '05', label: '导出与审计', permission: 'overview:read' },
];

export const ROLE_LABELS = {
  admin: '定价主管',
  analyst: '价格运营',
  viewer: '店长只读',
};

export const PERMISSIONS = {
  admin: [
    'overview:read',
    'competitor:read', 'competitor:write',
    'sku:read', 'sku:write',
    'rule:read', 'rule:write',
    'snapshot:read',
    'run:read', 'run:create',
    'advice:read', 'advice:decide',
    'export:read', 'audit:read',
  ],
  analyst: ['overview:read', 'competitor:read', 'sku:read', 'rule:read', 'snapshot:read', 'run:read', 'run:create', 'advice:read'],
  viewer: ['overview:read', 'competitor:read', 'sku:read', 'rule:read', 'snapshot:read', 'run:read', 'advice:read'],
};

/* 共享枚举：与 backend/src/constants/enums.py 同步（README「共享枚举出现位置」） */
export const ENUMS = {
  platform: {
    douyin: '抖音小店',
    taobao: '天猫 / 淘宝',
    jd: '京东',
    pdd: '拼多多',
    xhs: '小红书',
    weidian: '微店',
  },
  category: {
    sofa: '沙发',
    table: '桌几',
    bed: '床具',
    cabinet: '柜类',
    decor: '软装',
  },
  strategy: {
    guarded: '有底线跟价',
    aggressive: '抢量紧跟',
    hold: '只守不降',
  },
  risk: {
    high: '高风险',
    medium: '中风险',
    low: '低风险',
  },
  adviceStatus: {
    pending: '待审批',
    approved: '已批改价',
    rejected: '已驳回',
  },
  action: {
    follow: '跟价下调',
    hold: '维持不动',
    raise: '回调上行',
  },
  runStatus: {
    queued: '排队中',
    running: '执行中',
    success: '成功',
    partial: '部分成功',
    failed: '失败',
  },
  trigger: {
    manual: '手动',
    schedule: '定时',
    seed: '初始化',
  },
};

export function can(role, permission) {
  return (PERMISSIONS[role] || []).includes(permission);
}

export function riskTone(risk) {
  return { high: 'high', medium: 'medium', low: 'low' }[risk] || 'info';
}

export function statusTone(status) {
  return { pending: 'pending warn', approved: 'ok', rejected: 'danger' }[status] || 'info';
}

export function optionList(dict, withAll = '全部') {
  const items = Object.entries(dict).map(([value, label]) => ({ value, label }));
  return withAll ? [{ value: '', label: withAll }, ...items] : items;
}
