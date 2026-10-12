"use client";

import { useCallback, useEffect, useState } from "react";
import { ApiError, api } from "@/lib/api-client";
import { useAuth } from "@/lib/auth-context";
import { translateError } from "@/lib/errors";
import type { AdminStats, AdminUser, AuditLogItem } from "@/lib/types";

const STATUS_LABEL: Record<string, string> = { pending: "승인 대기", approved: "승인됨", rejected: "거절됨", suspended: "정지됨" };
const STATUS_STYLE: Record<string, string> = {
  pending: "bg-amber-500/20 text-amber-300",
  approved: "bg-emerald-500/20 text-emerald-300",
  rejected: "bg-red-500/20 text-red-300",
  suspended: "bg-white/10 text-white/60",
};
const fmt = (v: string | null) => (v ? new Date(v).toLocaleString("ko-KR") : "-");
const errText = (e: unknown, fallback: string) => (e instanceof ApiError ? translateError(e.code, e.message) : fallback);

export default function AdminPage() {
  const { user, loading: authLoading } = useAuth();
  const [tab, setTab] = useState<"users" | "audit">("users");

  if (authLoading) return <p className="text-sm text-white/50">불러오는 중…</p>;
  if (!user) {
    return (
      <div className="space-y-4">
        <h1 className="text-lg font-semibold">관리자</h1>
        <p className="text-sm text-white/50">로그인이 필요합니다.</p>
        <a href="/login" className="inline-block rounded-md bg-accent text-ink font-medium px-4 py-2 text-sm">로그인</a>
      </div>
    );
  }
  if (!user.is_admin) {
    return (
      <div className="space-y-4">
        <h1 className="text-lg font-semibold">관리자</h1>
        <p className="text-sm text-white/50">관리자만 접근할 수 있습니다.</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-lg font-semibold">관리자</h1>
        <a href="/admin/models" className="text-sm text-accent hover:underline">보이스 모델 관리 →</a>
      </div>
      <Stats />
      <div className="flex gap-1 border-b border-white/10">
        {([["users", "회원 관리"], ["audit", "감사 로그"]] as const).map(([k, label]) => (
          <button key={k} onClick={() => setTab(k)}
            className={`-mb-px border-b-2 px-3 py-2 text-sm ${tab === k ? "border-accent text-white" : "border-transparent text-white/50 hover:text-white"}`}>
            {label}
          </button>
        ))}
      </div>
      {tab === "users" ? <Users meId={user.id} /> : <Audit />}
    </div>
  );
}

function Stats() {
  const [s, setS] = useState<AdminStats | null>(null);
  useEffect(() => {
    api.adminStats().then(setS, () => {});
  }, []);
  if (!s) return null;
  const tiles: [string, number, string?][] = [
    ["승인 대기", s.users.pending],
    ["전체 회원", s.users.total, `승인 ${s.users.by_status.approved ?? 0} · 정지 ${s.users.by_status.suspended ?? 0}`],
    ["오늘 로그인", s.today.logins, `실패 ${s.today.login_failures}`],
    ["최근 7일 가입", s.week_signups],
  ];
  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
      {tiles.map(([label, value, sub], i) => (
        <div key={label} className={`rounded-md border px-3 py-2 ${i === 0 && value ? "border-amber-400/50 bg-amber-500/10" : "border-white/10 bg-panel"}`}>
          <div className="text-xs text-white/50">{label}</div>
          <div className="text-xl font-semibold">{value}</div>
          {sub && <div className="text-xs text-white/40">{sub}</div>}
        </div>
      ))}
    </div>
  );
}

function Users({ meId }: { meId: string }) {
  const [status, setStatus] = useState("pending");
  const [q, setQ] = useState("");
  const [query, setQuery] = useState("");
  const [users, setUsers] = useState<AdminUser[] | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    api.adminListUsers(status, query).then(setUsers, (e) => setMsg({ ok: false, text: errText(e, "목록을 불러오지 못했습니다.") }));
  }, [status, query]);
  useEffect(load, [load]);

  async function act(fn: () => Promise<unknown>, okText?: string) {
    setBusy(true);
    setMsg(null);
    try {
      await fn();
      if (okText) setMsg({ ok: true, text: okText });
      setSelected(new Set());
      load();
    } catch (e) {
      setMsg({ ok: false, text: errText(e, "처리하지 못했습니다.") });
    } finally {
      setBusy(false);
    }
  }

  const pendingIds = users?.filter((u) => u.status === "pending").map((u) => u.id) ?? [];
  const toggle = (id: string) =>
    setSelected((s) => {
      const n = new Set(s);
      if (n.has(id)) n.delete(id);
      else n.add(id);
      return n;
    });
  const btn = "rounded-md px-3 py-1 text-xs border border-white/15 hover:border-white/40 disabled:opacity-50";

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        {[["", "전체"], ...Object.entries(STATUS_LABEL)].map(([k, label]) => (
          <button key={k} onClick={() => setStatus(k)}
            className={`rounded-full px-3 py-1 text-xs ${status === k ? "bg-accent text-ink" : "bg-white/10 text-white/70 hover:bg-white/20"}`}>
            {label}
          </button>
        ))}
        <form className="ml-auto" onSubmit={(e) => { e.preventDefault(); setQuery(q.trim()); }}>
          <input placeholder="아이디·이름 검색 (Enter)" value={q} onChange={(e) => setQ(e.target.value)}
            className="w-48 rounded-md bg-panel border border-white/10 px-2 py-1 text-sm outline-none focus:border-accent" />
        </form>
      </div>

      {pendingIds.length > 0 && (
        <div className="flex flex-wrap items-center gap-3 rounded-md bg-amber-500/10 px-3 py-2 text-sm">
          <label className="flex items-center gap-2">
            <input type="checkbox" checked={pendingIds.every((id) => selected.has(id))}
              onChange={(e) => setSelected(e.target.checked ? new Set(pendingIds) : new Set())} />
            승인 대기 전체 선택
          </label>
          <button className={btn} disabled={!selected.size || busy}
            onClick={() => act(() => api.adminBulkApprove([...selected]), `${selected.size}명을 승인했습니다.`)}>
            선택한 {selected.size}명 승인
          </button>
        </div>
      )}

      {msg && <p className={`text-sm break-all ${msg.ok ? "text-emerald-300" : "text-red-400"}`}>{msg.text}</p>}
      {users === null ? <p className="text-sm text-white/50">불러오는 중…</p> : users.length === 0 ? (
        <p className="text-sm text-white/50">회원이 없습니다.</p>
      ) : (
        <ul className="divide-y divide-white/10 rounded-md border border-white/10">
          {users.map((u) => (
            <li key={u.id} className={`flex flex-col sm:flex-row sm:items-center gap-2 px-3 py-3 ${u.status === "pending" ? "bg-amber-500/5" : ""}`}>
              <div className="flex min-w-0 flex-1 gap-2">
                {u.status === "pending" && (
                  <input type="checkbox" className="mt-1" checked={selected.has(u.id)} onChange={() => toggle(u.id)} aria-label={`${u.username} 선택`} />
                )}
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2 text-sm">
                    <span className="font-medium break-all">{u.username}</span>
                    {u.name && <span className="text-white/50">{u.name}</span>}
                    {u.is_admin && <span className="text-xs text-accent">관리자</span>}
                    <span className={`rounded-full px-2 py-0.5 text-xs ${STATUS_STYLE[u.status]}`}>{STATUS_LABEL[u.status]}</span>
                  </div>
                  {u.signup_note && <p className="text-xs text-white/60 whitespace-pre-wrap">메모: {u.signup_note}</p>}
                  {u.reject_reason && <p className="text-xs text-red-300">거절 사유: {u.reject_reason}</p>}
                  <p className="text-xs text-white/40">가입 {fmt(u.created_at)} · 최근 로그인 {fmt(u.last_login_at)}</p>
                </div>
              </div>
              {u.id !== meId && (
                <div className="flex flex-wrap gap-1">
                  {(u.status === "pending" || u.status === "rejected") && (
                    <button className={btn} disabled={busy} onClick={() => act(() => api.adminApprove(u.id), `${u.username} 승인`)}>승인</button>
                  )}
                  {u.status === "pending" && (
                    <button className={btn} disabled={busy} onClick={() => {
                      const reason = window.prompt(`${u.username}의 가입을 거절합니다. 사유 (선택, 로그인할 때 회원에게 표시됨)`);
                      if (reason !== null) act(() => api.adminReject(u.id, reason), `${u.username} 거절`);
                    }}>거절</button>
                  )}
                  {u.status === "approved" && !u.is_admin && (
                    <button className={btn} disabled={busy} onClick={() =>
                      window.confirm(`${u.username}을(를) 정지할까요? 바로 로그아웃됩니다.`) && act(() => api.adminSuspend(u.id), `${u.username} 정지`)}>정지</button>
                  )}
                  {u.status === "suspended" && (
                    <button className={btn} disabled={busy} onClick={() => act(() => api.adminUnsuspend(u.id), `${u.username} 정지 해제`)}>정지 해제</button>
                  )}
                  {!u.password_managed && (
                    <button className={btn} disabled={busy} onClick={() => {
                      if (!window.confirm(`${u.username}의 임시 비밀번호를 발급할까요? 기존 비밀번호와 로그인은 무효가 됩니다.`)) return;
                      act(async () => {
                        const { temp_password } = await api.adminTempPassword(u.id);
                        setMsg({ ok: true, text: `임시 비밀번호: ${temp_password} (지금 한 번만 표시됩니다. 회원에게 전달하세요.)` });
                      });
                    }}>임시 비번</button>
                  )}
                  {!u.password_managed && (
                    <button className={`${btn} text-red-300`} disabled={busy} onClick={() =>
                      window.confirm(`"${u.username}" 계정을 삭제할까요? 되돌릴 수 없습니다.`) && act(() => api.adminDeleteUser(u.id), `${u.username} 삭제`)}>삭제</button>
                  )}
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

const AUDIT_FILTERS: [string, string][] = [["", "전체"], ["user.", "회원"], ["login.", "로그인"], ["admin.", "관리자 조치"]];

function Audit() {
  const [action, setAction] = useState("");
  const [items, setItems] = useState<AuditLogItem[] | null>(null);
  useEffect(() => {
    setItems(null);
    api.adminAuditLogs(action).then((r) => setItems(r.items), () => setItems([]));
  }, [action]);
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-2">
        {AUDIT_FILTERS.map(([k, label]) => (
          <button key={k} onClick={() => setAction(k)}
            className={`rounded-full px-3 py-1 text-xs ${action === k ? "bg-accent text-ink" : "bg-white/10 text-white/70 hover:bg-white/20"}`}>
            {label}
          </button>
        ))}
      </div>
      {items === null ? <p className="text-sm text-white/50">불러오는 중…</p> : items.length === 0 ? <p className="text-sm text-white/50">기록이 없습니다.</p> : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[640px] text-xs">
            <thead className="text-white/50"><tr><th className="text-left p-2">일시</th><th className="text-left p-2">동작</th><th className="text-left p-2">수행자</th><th className="text-left p-2">내용</th><th className="text-left p-2">IP</th></tr></thead>
            <tbody>
              {items.map((a) => (
                <tr key={a.id} className="border-t border-white/10 align-top">
                  <td className="p-2 whitespace-nowrap">{fmt(a.created_at)}</td>
                  <td className="p-2 font-mono">{a.action}</td>
                  <td className="p-2">{a.actor_username ?? "-"}</td>
                  <td className="p-2 font-mono break-all">{a.detail ? JSON.stringify(a.detail) : ""}</td>
                  <td className="p-2">{a.ip}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
