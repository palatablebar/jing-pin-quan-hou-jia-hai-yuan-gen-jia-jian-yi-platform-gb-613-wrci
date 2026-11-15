"""审计动作 -> 中文标签。"""
from __future__ import annotations

ACTIONS: dict[str, str] = {
    "auth.login": "登录",
    "competitor.create": "新建竞品店铺",
    "competitor.update": "修改竞品店铺",
    "sku.create": "新建自有 SKU",
    "sku.update": "修改成本/底价/目标毛利",
    "rule.create": "新建跟价规则",
    "rule.update": "修改跟价规则",
    "snapshot.capture": "抓价快照入库",
    "run.create": "发起抓价测算",
    "run.complete": "测算完成",
    "advice.decide": "审批跟价建议",
    "export.advices": "导出跟价建议",
    "export.snapshots": "导出券后价快照",
    "http.mutation": "写请求",
}
