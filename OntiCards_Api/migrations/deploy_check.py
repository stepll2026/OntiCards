# -*- coding: utf-8 -*-
"""
上线前自检（deploy check）

用途
----
在把代码部署到线上之前，先在本地跑一遍这个脚本。
它只做**只读检查**，不修改任何文件、不碰数据库结构。

它拦的是这几类「上线才会炸」的事故：
  1. init.sql 第 45 行的种子版本 != 迁移链 head
     → 全新装库会重放历史迁移，报 relation already exists
  2. 迁移链出现多个 head（并行开发没 merge）
     → upgrade 直接报 Multiple heads
  3. down_revision 指向不存在的版本（迁移文件被删/改名）
     → Can't locate revision
  4. 存在空迁移（upgrade/downgrade 都是 pass）
     → 说明 `flask db migrate` 什么都没检测到，这次变更漏写了
  5. 三线（init.sql / 模型 / 数据库）不一致
     → 本地就已经漂移了，上线必然对不齐

用法
----
    python migrations/deploy_check.py

    退出码 0 = 全部通过，可以部署
    退出码 1 = 有阻塞项，禁止部署

说明
----
第 3 项「三线一致」依赖 scripts/three_way_check.py 的解析能力。
找不到该脚本时，该项会标记为 SKIP 而不是 FAIL —— 但会明确提示，
避免你以为检查过了其实没检查。
"""
import glob
import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VERSIONS = os.path.join(ROOT, "migrations", "versions")
INIT_SQL = os.path.join(ROOT, "init.sql")

if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
if os.path.join(ROOT, "scripts") not in sys.path:
    sys.path.insert(0, os.path.join(ROOT, "scripts"))

PASS, FAIL, WARN, SKIP = "PASS", "FAIL", "WARN", "SKIP"

results = []          # [(状态, 检查项, 说明)]


def add(status, name, detail=""):
    results.append((status, name, detail))


def _read(path):
    with io.open(path, encoding="utf-8") as f:
        return f.read()


# ---------------------------------------------------------------- 1. 收集迁移链
def collect_revisions():
    """返回 {revision: {"file":..., "down":..., "upgrade_body":..., "downgrade_body":...}}"""
    revs = {}
    for path in sorted(glob.glob(os.path.join(VERSIONS, "*.py"))):
        if os.path.basename(path).startswith("__"):
            continue
        body = _read(path)

        mr = re.search(r"^revision\s*=\s*['\"]([^'\"]+)", body, re.M)
        if not mr:
            add(FAIL, "迁移文件格式",
                "%s 缺少 revision 声明" % os.path.basename(path))
            continue

        md = re.search(r"^down_revision\s*=\s*(?:['\"]([^'\"]+)['\"]|None)", body, re.M)
        down = md.group(1) if (md and md.group(1)) else None

        def _func_body(fname):
            m = re.search(r"^def\s+%s\s*\([^)]*\):(.*?)(?=^def\s|\Z)" % fname,
                          body, re.M | re.S)
            return m.group(1) if m else ""

        revs[mr.group(1)] = {
            "file": os.path.basename(path),
            "down": down,
            "upgrade_body": _func_body("upgrade"),
            "downgrade_body": _func_body("downgrade"),
        }
    return revs


def check_chain(revs):
    """校验迁移链，返回 (head, head)；出错时返回 (None, None)。"""
    if not revs:
        add(FAIL, "迁移链", "migrations/versions/ 下没有任何迁移文件")
        return None, None

    # 从每个节点沿 down_revision 遍历，覆盖与 head 不连通的环。
    # 已完成的路径无需重复访问；使用迭代避免长链触发递归深度限制。
    visited = set()
    for start in revs:
        path = set()
        current = start
        while current in revs and current not in visited:
            if current in path:
                add(FAIL, "迁移链环检测",
                    "存在循环引用，涉及版本：%s" % current)
                return None, None
            path.add(current)
            current = revs[current]["down"]
        visited.update(path)

    # ---- 单一 head
    downs = {v["down"] for v in revs.values() if v["down"]}
    heads = sorted(r for r in revs if r not in downs)

    if len(heads) == 0:
        add(FAIL, "迁移链 head", "没有找到 head，所有 revision 都被人引用，存在环")
        return None, None
    if len(heads) > 1:
        add(FAIL, "迁移链 head",
            "存在多个 head：%s —— 并行开发造成分叉，需要 "
            "`flask db merge -m merge %s`" % (", ".join(heads), " ".join(heads)))
        return None, heads[0]
    add(PASS, "迁移链 head", "唯一 head：%s" % heads[0])
    head = heads[0]

    # ---- 3. 孤儿 down_revision
    missing = sorted({v["down"] for v in revs.values()
                      if v["down"] and v["down"] not in revs})
    if missing:
        add(FAIL, "迁移链完整性",
            "以下 down_revision 指向不存在的版本：%s —— "
            "对应迁移文件可能被删除了" % ", ".join(missing))
    else:
        add(PASS, "迁移链完整性", "%d 个版本，引用关系闭合" % len(revs))

    return head, head


# ---------------------------------------------------------------- 4. 种子版本
def get_seed():
    if not os.path.exists(INIT_SQL):
        add(FAIL, "init.sql 存在性", "找不到 %s" % INIT_SQL)
        return None
    sql = _read(INIT_SQL)
    m = re.search(
        r"INSERT\s+INTO\s+\"?public\"?\.\"?alembic_version\"?[^;]*?"
        r"SELECT\s+'([^']+)'", sql, re.I | re.S)
    return m.group(1) if m else None


def check_seed(head):
    seed = get_seed()
    if seed is None:
        add(FAIL, "init.sql 种子版本",
            "init.sql 里找不到 alembic_version 的 INSERT ... SELECT")
        return
    if head is None:
        add(SKIP, "init.sql 种子版本", "head 未知，无法比对（种子=%s）" % seed)
        return
    if seed != head:
        add(FAIL, "init.sql 种子版本",
            "种子是 %s，但 head 是 %s —— 全新装库后跑 upgrade 会重放历史迁移，"
            "报 relation already exists。请把 init.sql 第 45 行改成 '%s'"
            % (seed, head, head))
    else:
        add(PASS, "init.sql 种子版本", "种子 = head = %s" % seed)


# ---------------------------------------------------------------- 5. 空迁移
def check_empty_migrations(revs):
    """空 upgrade() 的检查。

    例外：baseline 迁移（down_revision 为 None 的第一条）天生就是空的，
    它只负责「认账」，结构由 init.sql 保证 —— 不参与本项检查。
    """
    empties = []
    for rev, info in revs.items():
        if info["down"] is None:            # baseline，跳过
            continue
        up = re.sub(r"#.*", "", info["upgrade_body"]).strip()
        up = re.sub(r"['\"]{3}.*?['\"]{3}", "", up, flags=re.S).strip()
        up = re.sub(r"# ###.*?###", "", up, flags=re.S).strip()
        if up in ("", "pass", "...") or re.fullmatch(r"(pass\s*)+", up):
            empties.append(info["file"])

    if empties:
        add(WARN, "空迁移检查",
            "以下迁移的 upgrade() 是空的：%s —— 如果本意是改表结构，"
            "说明 `flask db migrate` 什么都没检测到，这次变更漏写了迁移"
            % ", ".join(empties))
    else:
        add(PASS, "空迁移检查",
            "无空迁移（baseline 除外，共 %d 条业务迁移）"
            % max(0, len(revs) - sum(1 for v in revs.values() if v["down"] is None)))


# ---------------------------------------------------------------- 6. 三线一致
def check_three_way():
    try:
        import three_way_check as chk
    except Exception as exc:                        # noqa: BLE001
        add(SKIP, "三线一致性",
            "无法导入 scripts/three_way_check.py（%s），该项未检查。" % exc)
        return

    try:
        i_t, i_cc, i_tc, i_ix, i_uc, i_fk, i_pk = chk.parse_init_sql()
        m_t, m_cc, m_tc, m_ix, m_uc, m_fk, m_pk = chk.load_models()
        d_t, d_cc, d_tc, d_ix, d_uc, d_fk, d_pk = chk.load_db()
    except Exception as exc:                        # noqa: BLE001
        add(FAIL, "三线一致性", "读取三方数据源失败：%s" % exc)
        return

    # 只比 init.sql ∩ 模型 的表（未纳管的表本就不该参与）
    in_scope = set(i_t) & set(m_t)

    problems = []
    for t in sorted(in_scope):
        ic, mc, dc = i_t.get(t, {}), m_t.get(t, {}), d_t.get(t, {})
        for col in set(ic) | set(mc) | set(dc):
            if col not in ic or col not in mc or col not in dc:
                problems.append("%s.%s 列存在性不一致" % (t, col))
                continue
            if chk.norm_type(ic[col]) != chk.norm_type(mc[col]):
                problems.append("%s.%s 类型不一致" % (t, col))
            if chk.norm_type(ic[col]) != chk.norm_type(dc[col]):
                problems.append("%s.%s 库里类型不一致" % (t, col))

    if problems:
        add(FAIL, "三线一致性",
            "%d 处结构不一致（只列前 5 条）：%s"
            % (len(problems), "；".join(problems[:5])))
    else:
        add(PASS, "三线一致性",
            "范围内 %d 张表的列结构一致（明细请跑 scripts/three_way_check.py）"
            % len(in_scope))


# ---------------------------------------------------------------- 7. 数据库版本
def check_db_version(head):
    if head is None:
        add(SKIP, "本地库版本", "head 未知")
        return
    try:
        from app import app
        from extensions.ext_database import db
        with app.app_context():
            row = db.session.execute(
                db.text("SELECT version_num FROM alembic_version")).fetchone()
            current = row[0] if row else None
            db.session.rollback()
    except Exception as exc:                        # noqa: BLE001
        add(SKIP, "本地库版本", "连不上数据库（%s）" % exc)
        return

    if current is None:
        add(WARN, "本地库版本",
            "库中没有版本记录 —— 可能是全新库，先跑 flask db upgrade")
    elif current != head:
        add(FAIL, "本地库版本",
            "库里是 %s，但 head 是 %s —— 说明这条迁移你本地都没跑过，"
            "必须先 flask db upgrade 并在本地验证" % (current, head))
    else:
        add(PASS, "本地库版本", "库 = head = %s" % current)


# ---------------------------------------------------------------- 输出
BADGE = {PASS: "[通过]", FAIL: "[阻塞]", WARN: "[提醒]", SKIP: "[跳过]"}


def main():
    print("=" * 66)
    print("上线前自检 —— 只读检查，不修改任何东西")
    print("=" * 66)

    revs = collect_revisions()
    head, _ = check_chain(revs)

    check_seed(head)
    check_empty_migrations(revs)
    check_db_version(head)
    check_three_way()

    print()
    for status, name, detail in results:
        print("%s %s" % (BADGE[status], name))
        if detail:
            for line in str(detail).split("\n"):
                print("        %s" % line)
        print()

    fails = [r for r in results if r[0] == FAIL]
    warns = [r for r in results if r[0] == WARN]
    skips = [r for r in results if r[0] == SKIP]

    print("=" * 66)
    print("阻塞 %d | 提醒 %d | 跳过 %d | 通过 %d"
          % (len(fails), len(warns), len(skips),
             len([r for r in results if r[0] == PASS])))
    print("=" * 66)

    if fails:
        print("结论：禁止部署。先解决上面的阻塞项。")
        return 1
    if warns:
        print("结论：可以部署，但请确认上面的提醒项都不是问题。")
        return 0
    print("结论：可以部署。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
