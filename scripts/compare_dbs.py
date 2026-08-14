"""迁移对照验证：比较两个数据库的所有表结构与行数"""
import sqlite3
import sys


def table_rows(db_path: str):
    conn = sqlite3.connect(db_path)
    tables = sorted(
        r[0]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
    )
    return {t: conn.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0] for t in tables}


def table_columns(db_path: str):
    conn = sqlite3.connect(db_path)
    tables = sorted(
        r[0]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
    )
    out = {}
    for t in tables:
        cols = conn.execute(f"PRAGMA table_info({t})").fetchall()
        out[t] = [(c[1], c[2], c[3], c[5]) for c in cols]  # name, type, notnull, pk
    return out


if __name__ == "__main__":
    db1, db2 = sys.argv[1], sys.argv[2]
    ok = True

    r1, r2 = table_rows(db1), table_rows(db2)
    if r1 == r2:
        print(f"✅ 行数一致（{len(r1)} 张表）:")
        for t, n in r1.items():
            print(f"   {t}: {n}")
    else:
        ok = False
        print("❌ 行数不一致:")
        for t in sorted(set(r1) | set(r2)):
            if r1.get(t) != r2.get(t):
                print(f"   {t}: python={r1.get(t)} rust={r2.get(t)}")

    c1, c2 = table_columns(db1), table_columns(db2)
    if c1 == c2:
        print("✅ 列结构一致")
    else:
        ok = False
        print("❌ 列结构不一致:")
        for t in sorted(set(c1) | set(c2)):
            if c1.get(t) != c2.get(t):
                print(f"   {t}:\n     python={c1.get(t)}\n     rust  ={c2.get(t)}")

    sys.exit(0 if ok else 1)
