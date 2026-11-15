"""角色 -> 权限点映射。README 与前端 site/js/config.js 同步。

角色键固定为 admin / analyst / viewer，各项目的展示名与职责不同。
"""
from __future__ import annotations

from src.constants.enums import Role

ROLE_LABELS: dict[str, str] = {
    Role.ADMIN.value: "定价主管",
    Role.ANALYST.value: "价格运营",
    Role.VIEWER.value: "店长只读",
}

ROLE_DUTIES: dict[str, str] = {
    Role.ADMIN.value: "维护竞品/SKU/规则与底价、审批改价、导出、查看审计",
    Role.ANALYST.value: "跑抓价回放、看券后价还原、发起跟价测算",
    Role.VIEWER.value: "只读查看券后价与建议（成本/底价脱敏）",
}

PERMISSIONS: dict[str, set[str]] = {
    Role.ADMIN.value: {
        "competitor:read", "competitor:write",
        "sku:read", "sku:write",
        "rule:read", "rule:write",
        "snapshot:read",
        "run:read", "run:create",
        "advice:read", "advice:decide",
        "export:read", "audit:read", "overview:read",
    },
    Role.ANALYST.value: {
        "competitor:read",
        "sku:read",
        "rule:read",
        "snapshot:read",
        "run:read", "run:create",
        "advice:read",
        "overview:read",
    },
    Role.VIEWER.value: {
        "competitor:read", "sku:read", "rule:read", "snapshot:read",
        "run:read", "advice:read", "overview:read",
    },
}

COMPETITOR_WRITE_ROLES = (Role.ADMIN.value,)
SKU_WRITE_ROLES = (Role.ADMIN.value,)
RULE_WRITE_ROLES = (Role.ADMIN.value,)
RUN_CREATE_ROLES = (Role.ADMIN.value, Role.ANALYST.value)
DECIDE_ROLES = (Role.ADMIN.value,)
EXPORT_ROLES = (Role.ADMIN.value,)
AUDIT_ROLES = (Role.ADMIN.value,)
READ_ROLES = (Role.ADMIN.value, Role.ANALYST.value, Role.VIEWER.value)

# 成本与底价只对这两个角色可见（viewer 走脱敏）
COST_VISIBLE_ROLES = (Role.ADMIN.value, Role.ANALYST.value)


def has_permission(role: str, permission: str) -> bool:
    return permission in PERMISSIONS.get(role, set())


def cost_visible(role: str) -> bool:
    return role in COST_VISIBLE_ROLES
