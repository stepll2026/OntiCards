"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useRouter } from "next-nprogress-bar";
import { useEffect, useMemo, useState } from "react";
import { message } from "antd";
import {
  LayoutDashboard,
  Database,
  Search,
  MessageSquare,
  Settings,
  HelpCircle,
  Bell,
  LogOut,
  Loader2,
  ChevronLeft,
  ChevronRight,
  Activity,
  Coins,
  BookOpen,
  Shield,
} from "lucide-react";
import ChangelogModal from "@/components/changelogModal/ChangelogModal";
import HelpModal from "@/components/helpModal/HelpModal";
import { getChangelog } from "@/api/changeLog";
import { logout } from "@/api/user";
import type { ChangelogItem } from "@/context/homeContext";
import { DataSourceProvider, UserInfoProvider, useUserInfo, resetGlobalUserInfo } from "@/hooks";
import { subscribeChangelogChanges } from "@/hooks/useDataSources";

type RecentActivity = {
  title: string;
  status: string;
  ts: number;
  path?: string;
};

export default function NewLayout({
                                    children,
                                    params,
                                  }: {
  children: React.ReactNode;
  params: { lng: string };
}) {
  const { lng } = params;
  const router = useRouter();
  const pathname = usePathname();

  // 检查是否是登录页面
  const isLoginPage = pathname?.endsWith('/login');

  const [showChangelog, setShowChangelog] = useState(false);
  const [showHelp, setShowHelp] = useState(false);
  const { userInfo, loading: userLoading } = useUserInfo();
  const [loggingOut, setLoggingOut] = useState(false);

  const [changelogList, setChangelogList] = useState<ChangelogItem[]>([]);
  const [changelogLoading, setChangelogLoading] = useState(false);
  const [hasUnreadChangelog, setHasUnreadChangelog] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  const getRecentSessionKey = (userId: string) => `recentActivitiesSession_${userId}`;
  const getRecentListKey = (userId: string) => `recentActivities_${userId}`;

  const ensureRecentSession = (userId: string) => {
    try {
      const sk = getRecentSessionKey(userId);
      if (!window.sessionStorage.getItem(sk)) {
        window.sessionStorage.setItem(sk, String(Date.now()));
        window.sessionStorage.setItem(getRecentListKey(userId), JSON.stringify([]));
      }
    } catch {
      // ignore
    }
  };

  const pushRecentActivity = (userId: string, activity: RecentActivity) => {
    try {
      ensureRecentSession(userId);
      const key = getRecentListKey(userId);
      const raw = window.sessionStorage.getItem(key);
      const arr: RecentActivity[] = raw ? JSON.parse(raw) : [];
      const next = [activity, ...arr].slice(0, 3);
      window.sessionStorage.setItem(key, JSON.stringify(next));
    } catch {
      // ignore
    }
  };

  const getRouteTitle = (p: string | null) => {
    if (!p) return "";
    // 去掉 /{lng} 前缀
    const short = p.replace(/^\/[^/]+/, "");
    if (short === "/overview") return "";
    if (short.startsWith("/workspaces")) return "浏览数据源";
    if (short.startsWith("/ask")) return "开始问数";
    if (short.startsWith("/settings")) return "进入系统与账户";
    if (short.startsWith("/governance")) return "进入数据质检";
    if (short.startsWith("/changelog")) return "查看更新日志";
    if (short.startsWith("/explore")) return "进入探索";
    if (short.startsWith("/monitoring")) return "进入监控中心";
    if (short.startsWith("/cost-config")) return "进入成本管理";
    if (short.startsWith("/business-terms")) return "业务术语库";
    return "";
  };

  // 判断当前是否处于“系统与账户”路径，用于阻止重复点击触发进度条
  const settingsHref = '/settings'
  const isOnSettingsPage =
    pathname === settingsHref || (pathname?.startsWith(settingsHref + '/') ?? false);

  useEffect(() => {
    // 登录页面不需要检查登录状态
    if (isLoginPage) {
      return;
    }

    // 简单的登录态校验：无 token 则回登录页
    const token = window.localStorage.getItem("console_token");

    if (!token) {
      router.push(`/${lng}/login`);
      return;
    }

    // 用户信息由 UserInfoProvider 自动获取，这里只需要检查 token
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lng, isLoginPage]);

  useEffect(() => {
    if (!userInfo?.id) return;

    ensureRecentSession(userInfo.id);

    const fetchChangelog = async () => {
      setChangelogLoading(true);
      try {
        const response = await getChangelog();
        if (response && response.code === 200 && response.data) {
          const publicLogs = (response.data as ChangelogItem[]).filter(
            (item) => item.status === "public",
          );
          setChangelogList(publicLogs);

          if (publicLogs.length > 0) {
            const latestVersion = publicLogs[0].version;
            const storageKey = `lastReadChangelogVersion_${userInfo.id}`;
            const lastReadVersion = localStorage.getItem(storageKey);
            setHasUnreadChangelog(latestVersion !== lastReadVersion);
          }
        }
      } catch (error) {
        console.error("获取版本更新日志失败:", error);
      } finally {
        setChangelogLoading(false);
      }
    };

    fetchChangelog();
  }, [userInfo?.id]);

  // 订阅 changelog 变更事件（当在其他页面新增/编辑 changelog 时）
  useEffect(() => {
    const unsubscribe = subscribeChangelogChanges(() => {
      if (userInfo?.id) {
        const fetchChangelog = async () => {
          setChangelogLoading(true);
          try {
            const response = await getChangelog();
            if (response && response.code === 200 && response.data) {
              const publicLogs = (response.data as ChangelogItem[]).filter(
                (item) => item.status === "public",
              );
              setChangelogList(publicLogs);

              if (publicLogs.length > 0) {
                const latestVersion = publicLogs[0].version;
                const storageKey = `lastReadChangelogVersion_${userInfo.id}`;
                const lastReadVersion = localStorage.getItem(storageKey);
                setHasUnreadChangelog(latestVersion !== lastReadVersion);
              }
            }
          } catch (error) {
            console.error("获取版本更新日志失败:", error);
          } finally {
            setChangelogLoading(false);
          }
        };
        fetchChangelog();
      }
    });

    return () => {
      unsubscribe();
    };
  }, [userInfo?.id]);

  useEffect(() => {
    if (isLoginPage) return;
    if (!userInfo?.id) return;
    const title = getRouteTitle(pathname);
    if (!title) return;
    pushRecentActivity(userInfo.id, { title, status: "访问", ts: Date.now(), path: pathname || undefined });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pathname, userInfo?.id, isLoginPage]);

  const markChangelogAsRead = () => {
    if (changelogList.length > 0 && userInfo?.id) {
      const latestVersion = changelogList[0].version;
      const storageKey = `lastReadChangelogVersion_${userInfo.id}`;
      localStorage.setItem(storageKey, latestVersion);
      setHasUnreadChangelog(false);
    }
  };

  const handleLogout = async () => {
    // 显示加载状态，防止重复点击
    if (loggingOut) return;
    setLoggingOut(true);

    // 先显示"正在退出"消息
    message.loading({ content: '正在退出...', key: 'logout', duration: 0 });

    try {
      await logout();
    } catch {
      // ignore
    } finally {
      try {
        if (userInfo?.id) {
          window.sessionStorage.removeItem(getRecentSessionKey(userInfo.id));
          window.sessionStorage.removeItem(getRecentListKey(userInfo.id));
        }
      } catch {
        // ignore
      }
      window.localStorage.removeItem("console_token");
      window.localStorage.removeItem("userInfo");
      window.sessionStorage.removeItem("datasource_session_id");
      document.cookie = "console_token=; path=/; max-age=0";

      // 重置全局用户信息状态，确保新登录用户数据正确
      resetGlobalUserInfo();

      // 关闭loading消息，显示成功
      message.success({ content: '退出成功', key: 'logout', duration: 2 });
      setLoggingOut(false);

      // 跳转登录页，next-nprogress-bar 会自动处理进度条
      router.push(`/${lng}/login`);
    }
  };

  // 登录页面直接渲染，不需要侧边栏和顶部栏
  if (isLoginPage) {
    return (
      <div className="min-h-screen" style={{ backgroundColor: 'rgb(var(--theme-bg-secondary))' }}>
        {children}
      </div>
    );
  }

  // 主题样式
  const themeStyles = {
    backgroundColor: 'rgb(var(--theme-bg-secondary))',
  };

  return (
    <UserInfoProvider>
      <DataSourceProvider>
        <div style={{ display: 'flex', flexDirection: 'row', minHeight: '100vh' }}>
          {/* Sidebar */}
          <aside
            style={{
              display: 'flex',
              flexDirection: 'column',
              flexShrink: 0,
              position: 'fixed',
              top: 0,
              left: 0,
              height: '100vh',
              transition: 'width 300ms ease-in-out',
              width: sidebarCollapsed ? 72 : 260,
              backgroundColor: 'rgb(var(--theme-bg-secondary))',
              borderRightColor: 'rgb(var(--theme-border))',
              zIndex: 40,
            }}
          >
            {/* Logo + 收起/展开按钮 */}
            <div className="flex items-center justify-between px-4 py-4 h-[60px] box-border" style={{ flexShrink: 0 }}>
              <div
                className="transition-all duration-300 ease-in-out overflow-hidden flex items-center"
                style={{
                  maxWidth: sidebarCollapsed ? 0 : '200px',
                  opacity: sidebarCollapsed ? 0 : 1,
                }}
              >
                <img
                  src="/statics/new_logo_final.png"
                  alt="OntiCards"
                  className="block h-9 w-auto object-contain"
                  draggable={false}
                />
              </div>
              <button
                onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
                className="flex items-center justify-center w-8 h-8 hover:transition-colors flex-shrink-0"
                style={{
                  borderRadius: '8px',
                  color: 'rgb(var(--theme-text-secondary))',
                }}
                title={sidebarCollapsed ? '展开菜单' : '收起菜单'}
                aria-label={sidebarCollapsed ? '展开菜单' : '收起菜单'}
              >
                {sidebarCollapsed ? (
                  <ChevronRight className="w-4 h-4" />
                ) : (
                  <ChevronLeft className="w-4 h-4" />
                )}
              </button>
            </div>

            <nav className="px-3" style={{ flex: 1, overflowY: 'auto' }}>
              <div className="space-y-1">
                <SideLink href="/overview" label="概览" icon={<LayoutDashboard className="w-4 h-4" />} collapsed={sidebarCollapsed} />
                <SideLink href="/workspaces" label="工作空间" icon={<Database className="w-4 h-4" />} collapsed={sidebarCollapsed} />
                <SideLink href="/business-terms" label="业务术语" icon={<BookOpen className="w-4 h-4" />} collapsed={sidebarCollapsed} />
                <SideLink href="/governance" label="数据质检" icon={<Shield className="w-4 h-4" />} collapsed={sidebarCollapsed} />
                <SideLink href="/monitoring" label="监控中心" icon={<Activity className="w-4 h-4" />} collapsed={sidebarCollapsed} />
                <SideLink href="/cost-config" label="成本管理" icon={<Coins className="w-4 h-4" />} collapsed={sidebarCollapsed} />
                {/* <SideLink href="/explore" label="探索" icon={<Search className="w-4 h-4" />} collapsed={sidebarCollapsed} />
              <SideLink href="/ask" label="智能问数" icon={<MessageSquare className="w-4 h-4" />} collapsed={sidebarCollapsed} /> */}
              </div>
            </nav>

            <div className="p-3" style={{ borderTopColor: 'rgb(var(--theme-border))', flexShrink: 0 }}>
              <div className="space-y-2">
                <Link
                  href="/settings"
                  data-prevent-nprogress={isOnSettingsPage ? "true" : undefined}
                  className="flex items-center text-sm transition-all duration-200 px-4 py-2.5"
                  style={{ color: 'rgb(var(--theme-text-secondary))' }}
                  title={sidebarCollapsed ? '系统与账户' : undefined}
                >
                  <Settings className="w-4 h-4 flex-shrink-0" />
                  <span
                    className="whitespace-nowrap transition-all duration-300 ease-in-out overflow-hidden"
                    style={{
                      maxWidth: sidebarCollapsed ? 0 : '200px',
                      opacity: sidebarCollapsed ? 0 : 1,
                      marginLeft: sidebarCollapsed ? 0 : '12px',
                    }}
                  >
                  系统与账户
                </span>
                </Link>
                <button
                  onClick={() => setShowHelp(true)}
                  className="w-full flex items-center text-sm transition-all duration-200 px-4 py-2.5"
                  style={{ color: 'rgb(var(--theme-text-secondary))' }}
                  title={sidebarCollapsed ? '帮助' : undefined}
                >
                  <HelpCircle className="w-4 h-4 flex-shrink-0" />
                  <span
                    className="whitespace-nowrap transition-all duration-300 ease-in-out overflow-hidden"
                    style={{
                      maxWidth: sidebarCollapsed ? 0 : '200px',
                      opacity: sidebarCollapsed ? 0 : 1,
                      marginLeft: sidebarCollapsed ? 0 : '12px',
                    }}
                  >
                  帮助
                </span>
                </button>
              </div>
            </div>

          </aside>

          {/* Main - 内容区宽度不变，仅随侧边栏收缩整体左移 */}
          <main
            style={{
              display: 'flex',
              flexDirection: 'column',
              flex: 1,
              minWidth: 0,
              marginLeft: sidebarCollapsed ? 72 : 260,
              transition: 'margin-left 300ms ease-in-out',
              background: 'linear-gradient(to bottom, rgb(var(--theme-bg-secondary)), rgb(var(--theme-bg)))',
            }}
          >
            <div className="mx-auto w-full max-w-[1060px] xl:max-w-[1340px] 2xl:max-w-[1540px] px-6 lg:px-10 xl:px-20 py-4 lg:py-6" style={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column' }}>
              <div className="flex items-center justify-end gap-2" style={{ flexShrink: 0 }}>
                <button
                  onClick={() => setShowChangelog(true)}
                  className="relative grid h-9 w-9 place-items-center rounded-xl transition-colors"
                  style={{ color: 'rgb(var(--theme-text-secondary))' }}
                  aria-label="通知与公告"
                  title="通知与公告"
                >
                  <Bell className="w-5 h-5" />
                  {hasUnreadChangelog && (
                    <span className="absolute right-1 top-1 bg-red-500" style={{ width: 8, height: 8, borderRadius: '50%' }} />
                  )}
                </button>
                <button
                  onClick={handleLogout}
                  disabled={loggingOut}
                  className="grid h-9 w-9 place-items-center rounded-xl transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                  style={{ color: 'rgb(var(--theme-text-secondary))' }}
                  aria-label="退出登录"
                  title={loggingOut ? '正在退出...' : '退出登录'}
                >
                  {loggingOut ? (
                    <Loader2 className="w-5 h-5 animate-spin" />
                  ) : (
                    <LogOut className="w-5 h-5" />
                  )}
                </button>
              </div>
              <div style={{ flex: 1, minHeight: 0, marginTop: 8 }}>
                {children}
              </div>
            </div>
          </main>
        </div>

        {/* 版本更新日志弹窗（通知公告） */}
        <ChangelogModal
          visible={showChangelog}
          onClose={() => setShowChangelog(false)}
          changelogList={changelogList}
          loading={changelogLoading}
          onOpen={markChangelogAsRead}
        />

        {/* 帮助文档弹窗 */}
        <HelpModal visible={showHelp} onClose={() => setShowHelp(false)} />
      </DataSourceProvider>
    </UserInfoProvider>
  );
}

function SideLink({
                    href,
                    label,
                    icon,
                    collapsed,
                  }: {
  href: string;
  label: string;
  icon?: React.ReactNode;
  collapsed?: boolean;
}) {
  const pathname = usePathname();
  // 不再添加语言前缀，路由保持干净
  const fullHref = href;
  const active =
    pathname === fullHref || pathname?.startsWith(fullHref + "/");

  return (
    <Link
      href={fullHref}
      title={collapsed ? label : undefined}
      data-prevent-nprogress={active ? "true" : undefined}
      className={[
        "flex items-center text-sm transition-all duration-200 px-4 py-3",
        active
          ? "font-medium"
          : "",
      ].join(" ")}
      style={{
        borderRadius: '12px',
        color: active ? 'rgb(var(--theme-primary))' : 'rgb(var(--theme-text-secondary))',
      }}
    >
      <span className="flex-shrink-0">{icon}</span>
      <span
        className="whitespace-nowrap transition-all duration-300 ease-in-out overflow-hidden"
        style={{
          maxWidth: collapsed ? 0 : '200px',
          opacity: collapsed ? 0 : 1,
          marginLeft: collapsed ? 0 : '12px',
        }}
      >
        {label}
      </span>
    </Link>
  );
}
