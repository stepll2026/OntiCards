"""
 @File: 草稿.py
 @Description: SSO 限流测试脚本（连续 70 次访问 /sso/login，预期前 60 次返回 200/400，
              第 61 次起返回 429 直到限流窗口结束）
 @Author: 韩小豪 849631113@qq.com
 @Create: 2026-01-15 17:31
"""

import sys
import time
import requests

BASE_URL = "http://localhost:9000"
SSO_URL = f"{BASE_URL}/sso/login?token=fake"
HEALTH_URL = f"{BASE_URL}/health"
TOTAL_REQUESTS = 70
PER_IP_LIMIT = 60  # .env 中 SSO_RATE_LIMIT_PER_IP 的默认值


def color(code: int) -> str:
    """根据 HTTP 状态码返回彩色字符串（Windows PowerShell 也兼容）。"""
    if code == 429:
        return f"\033[91m{code}\033[0m"   # 红
    if 200 <= code < 300:
        return f"\033[92m{code}\033[0m"   # 绿
    if 400 <= code < 500:
        return f"\033[93m{code}\033[0m"   # 黄
    return f"\033[91m{code}\033[0m"       # 红


def main() -> int:
    # 1. 先确认服务在线
    print(f"[step1] 健康检查 {HEALTH_URL}")
    try:
        h = requests.get(HEALTH_URL, timeout=5).json()
        print(f"        -> {h}")
    except Exception as e:
        print(f"        ✗ 服务未启动或不可达: {e}")
        return 1

    # 2. 探测 1 次，确认 SSO 端点本身可达，并记录基准耗时
    print(f"\n[step2] 单次探测 {SSO_URL}")
    r = requests.get(SSO_URL, timeout=10)
    print(f"        -> {r.status_code}  body={r.text[:120]}")

    # 3. 连发 TOTAL_REQUESTS 次，统计状态码分布
    print(f"\n[step3] 连续打 {TOTAL_REQUESTS} 次（同 IP，间隔 50ms）")
    codes: list[int] = []
    first_429_at: int | None = None
    session = requests.Session()
    t0 = time.time()
    for i in range(1, TOTAL_REQUESTS + 1):
        try:
            resp = session.get(SSO_URL, timeout=10)
            code = resp.status_code
        except Exception as e:
            print(f"        请求 {i:>2} 失败: {e}")
            continue
        codes.append(code)
        if code == 429 and first_429_at is None:
            first_429_at = i
            # 把 429 响应体里的 Retry-After 也打印出来
            ra = resp.headers.get("Retry-After")
            print(f"        ★ 第 {i} 次触发限流！Retry-After={ra}s  body={resp.text[:120]}")
        # 每 10 次打印一次进度
        if i % 10 == 0 or code == 429:
            print(f"        {i:>2}/{TOTAL_REQUESTS}  {color(code)}")
        time.sleep(0.05)
    elapsed = time.time() - t0

    # 4. 汇总
    dist: dict[int, int] = {}
    for c in codes:
        dist[c] = dist.get(c, 0) + 1
    print(f"\n[result] 总耗时 {elapsed:.2f}s  共发出 {len(codes)} 个请求")
    print(f"[result] 状态码分布:")
    for c in sorted(dist.keys()):
        print(f"        {c}: {dist[c]} 次")

    # 5. 断言
    # 注意：step2 那一次探测会消耗 1 个名额，所以首条 429 的位置应当在
    #   PER_IP_LIMIT + 1 附近（step2 1 次 + 连发 PER_IP_LIMIT 次 = 第 1 次被拒）
    # 用户体感上 60 次还是稳的，1 次探测 + 60 次连发 = 61 次，第 61 次被拒。
    print(f"\n[assert] 期望: 累计请求数 ≤ {PER_IP_LIMIT} 时不出现 429，"
          f"第 {PER_IP_LIMIT + 1} 次（step2 + 连发 = {PER_IP_LIMIT + 1}）开始出现 429")
    ok = True
    if first_429_at is None:
        print(f"        ✗ 全部 {len(codes)} 次都没有触发 429 —— 限流可能没生效！")
        ok = False
    else:
        # 容忍度：±2，因为脚本里 step2 那次探测也会占一个名额
        if first_429_at < PER_IP_LIMIT or first_429_at > PER_IP_LIMIT + 2:
            print(f"        ✗ 第 {first_429_at} 次就触发了 429，阈值应在 "
                  f"[{PER_IP_LIMIT}, {PER_IP_LIMIT + 2}] 区间内")
            ok = False
        else:
            print(f"        ✓ 第 {first_429_at} 次触发 429（区间 [{PER_IP_LIMIT}, "
                  f"{PER_IP_LIMIT + 2}]，符合预期）")
        if dist.get(429, 0) == 0:
            print(f"        ✗ 没有统计到 429 计数异常")
            ok = False

    return 0 if ok else 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n[abort] 用户中断")
        sys.exit(130)