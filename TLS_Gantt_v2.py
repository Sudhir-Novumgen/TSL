"""
TLS Drug Discovery Gantt Chart - v2
Topia Life Sciences Pvt. Ltd. - Initiation status
Tabs: Project Overview (Gantt) | Capacity Utilization (Monthly + sub-views)
"""
import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import pymysql
import json, os, time
from datetime import date, timedelta, datetime
st.set_page_config(page_title="TLS Drug Discovery", page_icon="🧬",
                   layout="wide", initial_sidebar_state="collapsed")
st.markdown("""<style>
#MainMenu,footer,header{visibility:hidden}
.stApp{background:#0f172a}
[data-testid="stSidebar"],[data-testid="collapsedControl"]{display:none}
.block-container{padding:1rem 1.5rem!important;max-width:100%!important}
[data-testid="stMetric"]{background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.1);
  border-radius:10px;padding:12px 16px!important}
[data-testid="stMetricLabel"]{color:#94a3b8!important;font-size:.7rem!important;
  text-transform:uppercase;letter-spacing:.8px}
[data-testid="stMetricValue"]{color:#f1f5f9!important;font-size:1.4rem!important;font-weight:700}
div[data-testid="metric-container"]{padding:4px}
.stTabs [data-baseweb="tab-list"]{background:rgba(255,255,255,.03);border-radius:10px;padding:4px}
.stTabs [data-baseweb="tab"]{color:#64748b;font-weight:600;border-radius:8px}
.stTabs [aria-selected="true"]{background:rgba(59,130,246,.15)!important;color:#93c5fd!important}
</style>""", unsafe_allow_html=True)
st.markdown("""
<div style="background:linear-gradient(135deg,#1e3a5f,#0f2442,#0c1e3a);
            border-radius:14px;padding:18px 26px;margin-bottom:14px;
            border:1px solid rgba(100,160,255,.15);box-shadow:0 4px 24px rgba(0,0,0,.4)">
  <div style="display:flex;align-items:center;gap:14px">
    <div style="font-size:2.2rem">🧬</div>
    <div>
      <div style="font-size:1.4rem;font-weight:800;color:#f0f8ff;letter-spacing:-.3px">
        Topia Life Sciences - Drug Discovery Dashboard</div>
      <div style="font-size:.75rem;color:#7eb3e8;margin-top:2px">
        Live - pms_v1 - Initiation projects - Project → Template → Group → Parent → Child</div>
    </div>
  </div>
</div>""", unsafe_allow_html=True)
# ── DB ─────────────────────────────────────────────────────────────────────────
_s = st.secrets["db"] if "db" in st.secrets else {}
DB = dict(
    host     = _s.get("host",     "167.71.233.211"),
    user     = _s.get("user",     "POWERBI"),
    password = _s.get("password", "Powerbi@2024"),
    database = _s.get("database", "pms_v1"),
    port     = int(_s.get("port", 3306)),
    connect_timeout=10,
    cursorclass=pymysql.cursors.DictCursor,
)
@st.cache_data(ttl=300)
def load():
    conn = pymysql.connect(**DB)
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT p.project_name, p.project_code,
                       s.status_name AS project_status, c.company_name,
                       pg.project_group_name,
                       get_template_type(ct.project_child_task_id) AS template_type,
                       pt.parent_task_name,
                       ct.project_child_task_name AS child_task_name,
                       ct.plan_start_date, ct.plan_end_date,
                       ct.actual_start_date, ct.actual_end_date,
                       ct.is_template_task, ct.hours, ct.spent_hours,
                       d.department_name,
                       CONCAT(u.first_name,' ',u.last_name) AS user_full_name
                FROM pms_project_child_task_tab ct
                INNER JOIN pms_project_parent_task_tab pt
                    ON pt.project_parent_task_id=ct.project_parent_task_id
                LEFT  JOIN pms_project_group_tab pg
                    ON pg.project_group_id=pt.project_group_id
                INNER JOIN pms_project_tab p ON p.project_id=ct.project_id
                INNER JOIN pms_status_tab s
                    ON s.status_id=p.status_id AND s.status_name='Initiation'
                LEFT  JOIN pms_department_tab d ON d.department_id=ct.department_id
                LEFT  JOIN pms_users_tab u ON u.user_id=ct.user_id
                LEFT  JOIN (SELECT project_id,MIN(company_id) AS company_id
                            FROM pms_project_company_tab GROUP BY project_id) pct
                    ON pct.project_id=p.project_id
                LEFT  JOIN pms_company_tab c ON c.company_id=pct.company_id
                WHERE p.status=1 AND ct.status=1
                  AND c.company_name='Topia Life Sciences Pvt. Ltd.'
                ORDER BY p.project_name,pg.sequence,pt.sequence,ct.sequence
            """)
            rows = cur.fetchall()
    finally:
        conn.close()
    df = pd.DataFrame(rows)
    for c in ["plan_start_date","plan_end_date","actual_start_date","actual_end_date"]:
        df[c] = pd.to_datetime(df[c], errors="coerce")
    df["hours"]       = pd.to_numeric(df["hours"],       errors="coerce").fillna(0)
    df["spent_hours"] = (pd.to_numeric(df["spent_hours"], errors="coerce").fillna(0)/60).round(2)
    df["user_full_name"]     = df["user_full_name"].fillna("Unassigned")
    df["department_name"]    = df["department_name"].fillna("-")
    df["template_type"]      = df["template_type"].fillna("(no type)")
    df["project_group_name"] = df["project_group_name"].fillna("(no group)")
    df["parent_task_name"]   = df["parent_task_name"].fillna("(no parent)")
    return df
@st.cache_data(ttl=300)
def load_weekly_plan():
    today_d = date.today()
    last_mon = today_d - timedelta(days=today_d.weekday() + 7)
    last_sun = last_mon + timedelta(days=6)
    conn = pymysql.connect(**DB)
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    CONCAT(u.first_name,' ',u.last_name)   AS user_full_name,
                    p.project_name,
                    ps.subtask_name,
                    ps.planned_date,
                    ROUND(ps.planned_time / 60.0, 2)       AS planned_hours,
                    ROUND(TIME_TO_SEC(COALESCE(ps.spent_time,'00:00:00')) / 3600.0, 2) AS spent_hours,
                    ps.task_priority,
                    sm.status_label                         AS current_status,
                    d.department_name
                FROM planned_subtasks_main ps
                LEFT JOIN pms_users_tab u  ON u.user_id         = ps.created_by
                LEFT JOIN pms_project_tab p ON p.project_id     = ps.project_id
                LEFT JOIN pms_department_tab d ON d.department_id = ps.department_id
                LEFT JOIN planned_subtask_status_master sm ON sm.status_id = ps.current_status_id
                LEFT JOIN pms_company_tab c ON c.company_id     = ps.company_id
                WHERE ps.is_active = 1
                  AND ps.planned_date BETWEEN %s AND %s
                  AND c.company_name = 'Topia Life Sciences Pvt. Ltd.'
                ORDER BY user_full_name, p.project_name, ps.planned_date
            """, (last_mon, last_sun))
            rows = cur.fetchall()
    finally:
        conn.close()
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    df["planned_hours"] = pd.to_numeric(df["planned_hours"], errors="coerce").fillna(0)
    df["spent_hours"]   = pd.to_numeric(df["spent_hours"],   errors="coerce").fillna(0)
    df["planned_date"]  = pd.to_datetime(df["planned_date"],  errors="coerce")
    df["user_full_name"]   = df["user_full_name"].fillna("Unassigned")
    df["project_name"]     = df["project_name"].fillna("(no project)")
    df["department_name"]  = df["department_name"].fillna("-")
    df["current_status"]   = df["current_status"].fillna("Unknown")
    PRIORITY = {1:"Low", 2:"Medium", 3:"High"}
    df["priority_label"] = df["task_priority"].map(PRIORITY).fillna("Medium")
    return df

@st.cache_data(ttl=300)
def load_monthly_plan():
    today_d = date.today()
    month_start = today_d.replace(day=1)
    conn = pymysql.connect(**DB)
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    CONCAT(u.first_name,' ',u.last_name)   AS user_full_name,
                    p.project_name,
                    ps.subtask_name,
                    ps.planned_date,
                    ROUND(ps.planned_time / 60.0, 2)       AS planned_hours,
                    ROUND(TIME_TO_SEC(COALESCE(ps.spent_time,'00:00:00')) / 3600.0, 2) AS spent_hours,
                    ps.task_priority,
                    sm.status_label                         AS current_status,
                    d.department_name
                FROM planned_subtasks_main ps
                LEFT JOIN pms_users_tab u  ON u.user_id         = ps.created_by
                LEFT JOIN pms_project_tab p ON p.project_id     = ps.project_id
                LEFT JOIN pms_department_tab d ON d.department_id = ps.department_id
                LEFT JOIN planned_subtask_status_master sm ON sm.status_id = ps.current_status_id
                LEFT JOIN pms_company_tab c ON c.company_id     = ps.company_id
                WHERE ps.is_active = 1
                  AND ps.planned_date BETWEEN %s AND %s
                  AND c.company_name = 'Topia Life Sciences Pvt. Ltd.'
                ORDER BY user_full_name, p.project_name, ps.planned_date
            """, (month_start, today_d))
            rows = cur.fetchall()
    finally:
        conn.close()
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    df["planned_hours"] = pd.to_numeric(df["planned_hours"], errors="coerce").fillna(0)
    df["spent_hours"]   = pd.to_numeric(df["spent_hours"],   errors="coerce").fillna(0)
    df["planned_date"]  = pd.to_datetime(df["planned_date"],  errors="coerce")
    df["user_full_name"]   = df["user_full_name"].fillna("Unassigned")
    df["project_name"]     = df["project_name"].fillna("(no project)")
    df["department_name"]  = df["department_name"].fillna("-")
    df["current_status"]   = df["current_status"].fillna("Unknown")
    PRIORITY = {1:"Low", 2:"Medium", 3:"High"}
    df["priority_label"] = df["task_priority"].map(PRIORITY).fillna("Medium")
    return df
def child_status(r, today):
    if pd.notna(r.actual_end_date): return "done"
    if pd.notna(r.actual_start_date):
        if pd.notna(r.plan_end_date) and r.plan_end_date.date()<today: return "overdue"
        return "active"
    if pd.notna(r.plan_end_date) and r.plan_end_date.date()<today: return "overdue"
    if pd.notna(r.plan_start_date) and r.plan_start_date.date()<today: return "late"
    return "todo"
def agg_pct(sts): return round(sum(1 for s in sts if s=="done")/max(1,len(sts))*100)
def agg_st(sts):
    if not sts: return "todo"
    if all(s=="done" for s in sts): return "done"
    if any(s in ("overdue","late") for s in sts): return "overdue"
    if any(s=="active" for s in sts): return "active"
    return "todo"
def fd(dt): return dt.strftime("%Y-%m-%d") if pd.notna(dt) else None
@st.cache_data
def build_all(today_s):
    today = date.fromisoformat(today_s)
    df = load()
    dates = df.plan_start_date.dropna().dt.date.tolist()+df.plan_end_date.dropna().dt.date.tolist()
    if not dates: return None
    mn=min(dates)-timedelta(days=7); mx=max(dates)+timedelta(days=14); td=(mx-mn).days
    projects=[]
    for pn,pdf in df.groupby("project_name",sort=True):
        templates=[]
        for tn,tdf in pdf.groupby("template_type",sort=False):
            groups=[]
            for gn,gdf in tdf.groupby("project_group_name",sort=False):
                parents=[]
                for ppn,pf in gdf.groupby("parent_task_name",sort=False):
                    children=[]
                    for _,r in pf.iterrows():
                        un=str(r.user_full_name)
                        children.append({"n":str(r.child_task_name),
                            "ps":fd(r.plan_start_date),"pe":fd(r.plan_end_date),
                            "as":fd(r.actual_start_date),"ae":fd(r.actual_end_date),
                            "st":child_status(r,today),"dp":str(r.department_name),
                            "us":None if un in ("Unassigned","None None","") else un})
                    sts=[c["st"] for c in children]
                    ps=sorted(c["ps"] for c in children if c["ps"])
                    pe=sorted(c["pe"] for c in children if c["pe"])
                    pd_=sum(1 for s in sts if s=="done"); pt_=len(sts)
                    parents.append({"n":ppn,"ps":ps[0] if ps else None,"pe":pe[-1] if pe else None,
                                    "pct":round(pd_/max(1,pt_)*100),"st":agg_st(sts),"ch":children,
                                    "_d":pd_,"_t":pt_})
                sts=[p["st"] for p in parents]
                ps=sorted(p["ps"] for p in parents if p["ps"])
                pe=sorted(p["pe"] for p in parents if p["pe"])
                gd_=sum(p["_d"] for p in parents); gt_=sum(p["_t"] for p in parents)
                groups.append({"n":gn,"ps":ps[0] if ps else None,"pe":pe[-1] if pe else None,
                               "pct":round(gd_/max(1,gt_)*100),"st":agg_st(sts),"pa":parents,
                               "_d":gd_,"_t":gt_})
            sts=[g["st"] for g in groups]
            ps=sorted(g["ps"] for g in groups if g["ps"])
            pe=sorted(g["pe"] for g in groups if g["pe"])
            td_=sum(g["_d"] for g in groups); tt_=sum(g["_t"] for g in groups)
            templates.append({"n":tn,"ps":ps[0] if ps else None,"pe":pe[-1] if pe else None,
                              "pct":round(td_/max(1,tt_)*100),"st":agg_st(sts),"gr":groups})
        sts=[t["st"] for t in templates]
        ps=sorted(t["ps"] for t in templates if t["ps"])
        pe=sorted(t["pe"] for t in templates if t["pe"])
        p_sts=pdf.apply(lambda r:child_status(r,today),axis=1)
        p_done=int((p_sts=="done").sum())
        projects.append({"n":pn,"ps":ps[0] if ps else None,"pe":pe[-1] if pe else None,
                         "pct":round(p_done/max(1,len(pdf))*100),"st":agg_st(sts),"tm":templates,
                         "cnt":len(pdf),"done":p_done,
                         "active":int((p_sts=="active").sum()),
                         "overdue":int((p_sts=="overdue").sum()),
                         "todo":int((p_sts=="todo").sum())})
    all_sts=[p["st"] for p in projects]
    return {"mn":str(mn),"mx":str(mx),"td":td,"today":str(today),
            "pct":agg_pct(all_sts),"st":agg_st(all_sts),"pr":projects}
# ── Session / refresh ──────────────────────────────────────────────────────────
if "last_refresh" not in st.session_state:
    st.session_state.last_refresh = time.time()
INTERVALS = {"Off":0,"Every 5 min":300,"Every 15 min":900,"Every 30 min":1800}
rb1,rb2,rb3 = st.columns([5,2,1])
with rb1:
    elapsed_s = int(time.time()-st.session_state.last_refresh)
    now_str   = datetime.now().strftime("%d %b %Y, %H:%M:%S")
    ago = ("just now" if elapsed_s<5 else f"{elapsed_s}s ago" if elapsed_s<60
           else f"{elapsed_s//60}m {elapsed_s%60}s ago")
    st.markdown(
        f"""<div style="background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.08);
            border-radius:8px;padding:8px 14px;display:flex;align-items:center;gap:10px">
            <span style="font-size:1.1rem">🕐</span>
            <div><div style="color:#94a3b8;font-size:.7rem;text-transform:uppercase">Last refreshed</div>
              <div style="color:#e2e8f0;font-size:.82rem;font-weight:600">{now_str}
                <span style="color:#64748b;font-size:.75rem"> ({ago})</span></div></div></div>""",
        unsafe_allow_html=True)
with rb2:
    auto_label = st.selectbox("interval",list(INTERVALS.keys()),
                              key="ars",label_visibility="collapsed")
    auto_secs  = INTERVALS[auto_label]
with rb3:
    if st.button("🔄 Refresh",use_container_width=True,type="primary"):
        st.cache_data.clear(); st.session_state.last_refresh=time.time(); st.rerun()
if auto_secs>0:
    elapsed_now=time.time()-st.session_state.last_refresh
    if elapsed_now>=auto_secs:
        st.cache_data.clear(); st.session_state.last_refresh=time.time(); st.rerun()
    remaining_ms=max(1000,int((auto_secs-elapsed_now)*1000))
    remaining_s=remaining_ms//1000
    components.html(
        f"""<div style="font-size:11px;color:#64748b;text-align:right;padding:2px 4px">
              Auto-refresh in <b id="t" style="color:#3b82f6">{remaining_s}s</b></div>
            <script>let r={remaining_s};
              setInterval(()=>{{document.getElementById('t').textContent=(--r)+'s';}},1000);
              setTimeout(()=>window.parent.location.reload(),{remaining_ms});</script>""",height=22)
st.markdown("<div style='margin-top:8px'></div>",unsafe_allow_html=True)
# ── Load + KPI ─────────────────────────────────────────────────────────────────
df_all = load()
today  = date.today()
df_all["_st"] = df_all.apply(lambda r: child_status(r,today),axis=1)
c1,c2,c3,c4,c5,c6 = st.columns(6)
c1.metric("🏗 Projects",     df_all.project_name.nunique())
c2.metric("📋 Total Tasks",  f"{len(df_all):,}")
c3.metric("✅ Done",          f"{int((df_all._st=='done').sum()):,}")
c4.metric("🔵 In Progress",  f"{int((df_all._st=='active').sum()):,}")
c5.metric("🔴 Overdue",       f"{int((df_all._st=='overdue').sum()):,}")
c6.metric("⬜ To-Do",         f"{int((df_all._st=='todo').sum()):,}")
st.markdown("<div style='margin-top:10px'></div>",unsafe_allow_html=True)
# ── Tabs ────────────────────────────────────────────────────────────────────────
tab1,tab2 = st.tabs(["📅  Project Overview","👥  Capacity Utilization"])
# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 - GANTT
# ══════════════════════════════════════════════════════════════════════════════
with tab1:
    with st.spinner("Rendering Gantt..."):
        data = build_all(str(today))
    if not data:
        st.warning("No plan dates found."); st.stop()
    data_json = json.dumps(data,ensure_ascii=False,default=str)
    n_proj    = len(data["pr"])
    GANTT = f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<style>
:root{{--done:#10b981;--active:#3b82f6;--overdue:#ef4444;--todo:#94a3b8;--border:#e2e8f0}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:'Segoe UI',-apple-system,sans-serif;background:#f8faff}}
.toolbar{{display:flex;align-items:center;gap:10px;padding:10px 14px;background:#fff;
          border-bottom:1px solid var(--border);border-radius:12px 12px 0 0;flex-wrap:wrap}}
.search{{flex:1;min-width:180px;max-width:280px;border:1px solid #cbd5e1;border-radius:8px;
         padding:6px 10px 6px 28px;font-size:12px;
         background:#f8faff url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='13' height='13' viewBox='0 0 24 24' fill='none' stroke='%2394a3b8' stroke-width='2'%3E%3Ccircle cx='11' cy='11' r='8'/%3E%3Cpath d='m21 21-4.35-4.35'/%3E%3C/svg%3E") no-repeat 8px center;
         color:#334155;outline:none}}
.search:focus{{border-color:#3b82f6}}
.btn{{border:1px solid #cbd5e1;border-radius:8px;padding:5px 12px;font-size:11px;font-weight:600;
      cursor:pointer;color:#475569;background:#f8faff;transition:all .15s}}
.btn:hover{{background:#e2e8f0}}
.btn-exp{{border-color:#3b82f630;color:#3b82f6;background:#eff6ff}}
.legend{{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-left:auto}}
.li{{display:flex;align-items:center;gap:4px;font-size:10.5px;color:#64748b}}
.ld{{width:10px;height:10px;border-radius:3px}}
.tl-wrap{{border:1px solid var(--border);border-radius:0 0 12px 12px;overflow:hidden;
          background:#fff;box-shadow:0 4px 20px rgba(0,0,0,.06)}}
.grow{{display:grid;border-bottom:.5px solid #e8eef8;transition:background .12s}}
.grow:last-child{{border-bottom:none}}
.cn{{display:flex;align-items:center;gap:5px;padding:0 10px;
     border-right:1px solid rgba(255,255,255,.1);cursor:pointer;
     user-select:none;overflow:hidden;white-space:nowrap}}
.cn.wrap{{white-space:normal;align-items:flex-start;padding:6px 10px}}
.cnl{{border-right-color:var(--border)!important}}
.cp{{display:flex;align-items:center;justify-content:flex-end;
     padding:0 8px;border-right:1px solid rgba(255,255,255,.1);flex-shrink:0}}
.cpl{{border-right-color:var(--border)!important}}
.cb{{position:relative;overflow:hidden}}
.proj{{background:linear-gradient(90deg,#1e3958,#1a3352)}} .proj:hover{{background:linear-gradient(90deg,#234468,#1e3d60)}}
.tmpl{{background:linear-gradient(90deg,#1d4976,#194270)}} .tmpl:hover{{background:linear-gradient(90deg,#22548a,#1e4d83)}}
.grp{{background:#f0f7ff}} .grp:hover{{background:#e6f2ff}}
.par{{background:#f8faff}} .par:hover{{background:#f0f5ff}}
.child{{background:#fff}}  .child:hover{{background:#f7faff}}
.child.st-done   {{border-left:3px solid var(--done)}}
.child.st-active {{border-left:3px solid var(--active)}}
.child.st-overdue{{border-left:3px solid var(--overdue)}}
.child.st-late   {{border-left:3px solid var(--overdue)}}
.child.st-todo   {{border-left:3px solid #e2e8f0}}
.arr{{font-size:8px;transition:transform .18s ease;display:inline-block;opacity:.65;flex-shrink:0;margin-right:2px}}
.op{{transform:rotate(90deg)}}
.badge{{font-size:9px;border-radius:20px;padding:2px 8px;font-weight:700;white-space:nowrap;flex-shrink:0;letter-spacing:.2px}}
.pbar{{width:32px;height:4px;background:rgba(255,255,255,.15);border-radius:2px;margin-left:4px;flex-shrink:0}}
.pbar-f{{height:100%;border-radius:2px}} .pbar-l{{background:#e8eef8}}
.chip{{font-size:9px;border-radius:10px;padding:1px 6px;font-weight:600;white-space:nowrap;flex-shrink:0}}
.tooltip{{position:fixed;background:#1e293b;color:#e2e8f0;border-radius:8px;padding:8px 12px;
          font-size:11px;line-height:1.6;pointer-events:none;z-index:9999;display:none;
          min-width:210px;box-shadow:0 8px 24px rgba(0,0,0,.35);border:1px solid rgba(255,255,255,.1)}}
.tooltip b{{color:#7dd3fc}}
.no-res{{padding:32px;text-align:center;color:#94a3b8;font-size:13px}}
::-webkit-scrollbar{{width:5px;height:5px}}
::-webkit-scrollbar-thumb{{background:#cbd5e1;border-radius:3px}}
</style></head>
<body>
<div class="toolbar">
  <input class="search" id="srch" placeholder="Search projects..." oninput="render()">
  <button class="btn btn-exp" onclick="expandAll()">Expand All</button>
  <button class="btn" onclick="collapseAll()">Collapse All</button>
  <div class="legend">
    <div class="li"><div class="ld" style="background:var(--done)"></div>Done</div>
    <div class="li"><div class="ld" style="background:var(--active)"></div>In Progress</div>
    <div class="li"><div class="ld" style="background:var(--overdue)"></div>Overdue</div>
    <div class="li"><div class="ld" style="background:var(--todo)"></div>To-Do</div>
    <div class="li"><div class="ld" style="background:#dbeafe;border:1px solid #93c5fd"></div>Plan</div>
    <div class="li"><div class="ld" style="background:#ff6b35;width:3px;border-radius:1px"></div>Today</div>
  </div>
</div>
<div class="tl-wrap"><div id="tl"></div></div>
<div class="tooltip" id="tip"></div>
<script>
const DATA={data_json};
const COLS='380px 56px 1fr';
const SC={{done:'var(--done)',active:'var(--active)',overdue:'var(--overdue)',late:'var(--overdue)',todo:'var(--todo)'}};
const SL={{done:'Done',active:'In Progress',overdue:'Overdue',late:'Not Started (Late)',todo:'To-Do'}};
const SBG={{done:'#d1fae5',active:'#dbeafe',overdue:'#fee2e2',late:'#fee2e2',todo:'#f1f5f9'}};
const STC={{done:'#065f46',active:'#1d4ed8',overdue:'#991b1b',late:'#991b1b',todo:'#475569'}};
function badge(s){{return `<span class="badge" style="background:${{SBG[s]}};color:${{STC[s]}}">${{SL[s]}}</span>`;}}
const REF=new Date(DATA.mn+'T00:00:00');
function doff(s){{if(!s)return null;return Math.round((new Date(s+'T00:00:00')-REF)/86400000);}}
function pc(d){{return(Math.max(0,Math.min(d,DATA.td))/DATA.td*100).toFixed(3)+'%';}}
function bar(s,e){{const a=doff(s),b=doff(e);if(a===null||b===null)return null;return{{L:pc(a),W:pc(Math.max(2,b-a+1))}};}}
function barF(s,e,pct){{const b=bar(s,e);if(!b)return null;const fw=Math.max(2,(doff(e)-doff(s)+1)*pct/100);return{{L:b.L,W:b.W,FW:pc(fw)}};}}
function fmtD(s){{if(!s)return'-';return new Date(s+'T00:00:00').toLocaleDateString('en-GB',{{day:'2-digit',month:'short',year:'numeric'}});}}
const MN=['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
const months=[];let cur=new Date(DATA.mn+'T00:00:00');cur.setDate(1);
const endD=new Date(DATA.mx+'T00:00:00');
while(cur<=endD){{const y=cur.getFullYear(),m=cur.getMonth();
  months.push({{y,m,lbl:MN[m],q:'Q'+Math.ceil((m+1)/3),days:new Date(y,m+1,0).getDate()}});
  cur=new Date(y,m+1,1);}}
const THDR=months.reduce((s,m)=>s+m.days,0);
const moffs=[];let mo2=0;months.forEach(m=>{{moffs.push(mo2);mo2+=m.days;}});
function ph(d){{return(d/THDR*100).toFixed(3)+'%';}}
const yrs={{}},qs={{}};
months.forEach(m=>{{yrs[m.y]=(yrs[m.y]||0)+m.days;const k=m.q+' '+m.y;qs[k]=(qs[k]||0)+m.days;}});
const todayOff=doff(DATA.today);
function gl(dark){{
  let h='',yo=0;
  Object.values(yrs).forEach(d=>{{h+=`<div style="position:absolute;left:${{ph(yo)}};top:0;bottom:0;width:1.5px;background:${{dark?'rgba(255,255,255,.18)':'rgba(99,130,180,.2)'}};pointer-events:none"></div>`;yo+=d;}});
  moffs.forEach((o,i)=>{{if(i>0)h+=`<div style="position:absolute;left:${{ph(o)}};top:0;bottom:0;width:.5px;background:${{dark?'rgba(255,255,255,.06)':'rgba(99,130,180,.07)'}};pointer-events:none"></div>`;}});
  if(todayOff!==null&&todayOff>=0&&todayOff<=DATA.td)
    h+=`<div style="position:absolute;left:${{pc(todayOff)}};top:0;bottom:0;width:2px;background:#ff6b35;z-index:10;pointer-events:none"></div>`;
  return h;
}}
const S={{}};
function kk(...a){{return a.join('_');}}
function isOpen(k,d){{return S[k]===undefined?d:S[k];}}
function expandAll(){{DATA.pr.forEach((_,pi)=>{{S[kk('p',pi)]=true;DATA.pr[pi].tm.forEach((_,ti)=>{{S[kk('p',pi,'t',ti)]=true;DATA.pr[pi].tm[ti].gr.forEach((_,gi)=>{{S[kk('p',pi,'t',ti,'g',gi)]=true;DATA.pr[pi].tm[ti].gr[gi].pa.forEach((_,pai)=>{{S[kk('p',pi,'t',ti,'g',gi,'pa',pai)]=true;}});}});}});}});render();}}
function collapseAll(){{Object.keys(S).forEach(k=>S[k]=false);render();}}
const tip=document.getElementById('tip');
function showTip(e,h){{tip.innerHTML=h;tip.style.display='block';moveTip(e);}}
function moveTip(e){{tip.style.left=Math.min(e.clientX+14,window.innerWidth-220)+'px';tip.style.top=Math.max(0,e.clientY-10)+'px';}}
function hideTip(){{tip.style.display='none';}}
document.addEventListener('mousemove',e=>{{if(tip.style.display!=='none')moveTip(e);}});
function render(){{
  const C=document.getElementById('rows');C.innerHTML='';
  const q=(document.getElementById('srch').value||'').toLowerCase().trim();
  const filtered=DATA.pr.filter(p=>!q||p.n.toLowerCase().includes(q));
  if(!filtered.length){{C.innerHTML='<div class="no-res">No projects match search.</div>';return;}}
  filtered.forEach((proj,_pi)=>{{
    const pi=DATA.pr.indexOf(proj),pk=kk('p',pi),pOpen=isOpen(pk,false);
    const pb=barF(proj.ps,proj.pe,proj.pct);
    const pr=document.createElement('div');
    pr.className='grow proj';pr.style.gridTemplateColumns=COLS;pr.style.minHeight='46px';pr.style.height='auto';
    pr.innerHTML=`
      <div class="cn wrap" style="min-height:46px;font-size:12px;font-weight:700;color:#f0f8ff;gap:7px">
        <span class="arr ${{pOpen?'op':''}}" style="margin-top:3px">&#9654;</span>
        <span style="width:8px;height:8px;border-radius:50%;background:${{SC[proj.st]}};flex-shrink:0;margin-top:3px;box-shadow:0 0 6px ${{SC[proj.st]}}80"></span>
        <span style="flex:1;word-break:break-word;line-height:1.35">${{proj.n}}</span>
        ${{badge(proj.st)}}
        <span class="chip" style="background:rgba(255,255,255,.12);color:#94c8f8">${{proj.tm.length}}T&middot;${{proj.cnt}}</span>
      </div>
      <div class="cp" style="min-height:46px;color:${{SC[proj.st]}};font-size:12px;font-weight:700;flex-direction:column;gap:2px;align-self:stretch">
        <span>${{proj.pct}}%</span>
        <div class="pbar"><div class="pbar-f" style="width:${{proj.pct}}%;background:${{SC[proj.st]}}"></div></div>
      </div>
      <div class="cb" style="min-height:46px;align-self:stretch">
        ${{gl(true)}}
        ${{pb?`<div style="position:absolute;left:${{pb.L}};width:${{pb.W}};top:10px;bottom:10px;border-radius:4px;background:rgba(255,255,255,.12)"></div>
               <div style="position:absolute;left:${{pb.L}};width:${{pb.FW}};top:10px;bottom:10px;border-radius:4px;background:${{SC[proj.st]}};box-shadow:0 0 8px ${{SC[proj.st]}}50"></div>
               <div style="position:absolute;left:${{pb.L}};width:${{pb.W}};top:10px;bottom:10px;display:flex;align-items:center;padding-left:8px;font-size:9px;color:rgba(255,255,255,.75);pointer-events:none">
                 ${{fmtD(proj.ps)}} &rarr; ${{fmtD(proj.pe)}}</div>`:''}};
        ${{todayOff!==null&&todayOff>=0&&todayOff<=DATA.td?`<div style="position:absolute;left:${{pc(todayOff)}};top:0;font-size:8px;background:#ff6b35;color:#fff;padding:1px 3px;border-radius:0 0 3px 3px;z-index:20;transform:translateX(-50%);font-weight:700">Today</div>`:''}};
      </div>`;
    pr.querySelector('.cn').addEventListener('click',()=>{{S[pk]=!pOpen;render();}});
    C.appendChild(pr);if(!pOpen)return;
    proj.tm.forEach((tm,ti)=>{{
      const tk=kk('p',pi,'t',ti),tOpen=isOpen(tk,false),tb=barF(tm.ps,tm.pe,tm.pct);
      const tr=document.createElement('div');
      tr.className='grow tmpl';tr.style.gridTemplateColumns=COLS;tr.style.minHeight='36px';
      tr.innerHTML=`
        <div class="cn" style="min-height:36px;padding-left:20px;font-size:11.5px;font-weight:600;color:#bdd8ff">
          <span class="arr ${{tOpen?'op':''}}">&#9654;</span>
          <span style="flex:1;overflow:hidden;text-overflow:ellipsis" title="${{tm.n}}">${{tm.n}}</span>
          ${{badge(tm.st)}}
          <span class="chip" style="background:rgba(255,255,255,.12);color:#94c8f8">${{tm.gr.length}} grp</span>
        </div>
        <div class="cp" style="min-height:36px;color:${{SC[tm.st]}};font-size:11px;font-weight:700;flex-direction:column;gap:2px">
          <span>${{tm.pct}}%</span>
          <div class="pbar"><div class="pbar-f" style="width:${{tm.pct}}%;background:${{SC[tm.st]}}"></div></div>
        </div>
        <div class="cb" style="min-height:36px">
          ${{gl(true)}}
          ${{tb?`<div style="position:absolute;left:${{tb.L}};width:${{tb.W}};top:7px;bottom:7px;border-radius:4px;background:rgba(255,255,255,.1)"></div>
                 <div style="position:absolute;left:${{tb.L}};width:${{tb.FW}};top:7px;bottom:7px;border-radius:4px;background:${{SC[tm.st]}};opacity:.85"></div>`:''}};
        </div>`;
      tr.querySelector('.cn').addEventListener('click',e=>{{e.stopPropagation();S[tk]=!tOpen;render();}});
      C.appendChild(tr);if(!tOpen)return;
      tm.gr.forEach((gr,gi)=>{{
        const gk=kk('p',pi,'t',ti,'g',gi),gOpen=isOpen(gk,false),gb=barF(gr.ps,gr.pe,gr.pct);
        const gr2=document.createElement('div');
        gr2.className='grow grp';gr2.style.gridTemplateColumns=COLS;gr2.style.minHeight='32px';
        gr2.innerHTML=`
          <div class="cn cnl" style="min-height:32px;padding-left:36px;font-size:11px;font-weight:600;color:#1e40af">
            <span class="arr ${{gOpen?'op':''}}">&#9654;</span>
            <span style="flex:1;overflow:hidden;text-overflow:ellipsis" title="${{gr.n}}">${{gr.n}}</span>
            ${{badge(gr.st)}}
            <span class="chip" style="background:#dbeafe;color:#1d4ed8">${{gr.pa.length}}</span>
          </div>
          <div class="cp cpl" style="min-height:32px;color:${{SC[gr.st]}};font-size:11px;font-weight:700;flex-direction:column;gap:2px">
            <span>${{gr.pct}}%</span>
            <div class="pbar pbar-l"><div class="pbar-f" style="width:${{gr.pct}}%;background:${{SC[gr.st]}}"></div></div>
          </div>
          <div class="cb" style="min-height:32px">
            ${{gl(false)}}
            ${{gb?`<div style="position:absolute;left:${{gb.L}};width:${{gb.W}};top:6px;bottom:6px;border-radius:3px;background:#bfdbfe40"></div>
                   <div style="position:absolute;left:${{gb.L}};width:${{gb.FW}};top:6px;bottom:6px;border-radius:3px;background:${{SC[gr.st]}};opacity:.75"></div>`:''}};
          </div>`;
        gr2.querySelector('.cn').addEventListener('click',e=>{{e.stopPropagation();S[gk]=!gOpen;render();}});
        C.appendChild(gr2);if(!gOpen)return;
        gr.pa.forEach((pa,pai)=>{{
          const ppk=kk('p',pi,'t',ti,'g',gi,'pa',pai),paOpen=isOpen(ppk,false),pb2=barF(pa.ps,pa.pe,pa.pct);
          const par=document.createElement('div');
          par.className='grow par';par.style.gridTemplateColumns=COLS;par.style.minHeight='28px';
          par.innerHTML=`
            <div class="cn cnl" style="min-height:28px;padding-left:52px;font-size:11px;font-weight:600;color:#334155">
              <span class="arr ${{paOpen?'op':''}}">&#9654;</span>
              <span style="flex:1;overflow:hidden;text-overflow:ellipsis" title="${{pa.n}}">${{pa.n}}</span>
              <span class="chip" style="background:#e2e8f0;color:#64748b">${{pa.ch.length}}</span>
            </div>
            <div class="cp cpl" style="min-height:28px;color:${{SC[pa.st]}};font-size:10px;font-weight:700">${{pa.pct}}%</div>
            <div class="cb" style="min-height:28px">
              ${{gl(false)}}
              ${{pb2?`<div style="position:absolute;left:${{pb2.L}};width:${{pb2.W}};top:5px;bottom:5px;border-radius:3px;background:#e8eef8"></div>
                      <div style="position:absolute;left:${{pb2.L}};width:${{pb2.FW}};top:5px;bottom:5px;border-radius:3px;background:${{SC[pa.st]}};opacity:.75"></div>`:''}};
            </div>`;
          par.querySelector('.cn').addEventListener('click',e=>{{e.stopPropagation();S[ppk]=!paOpen;render();}});
          C.appendChild(par);if(!paOpen)return;
          pa.ch.forEach(ch=>{{
            const actEnd=ch.ae||(ch.st==='active'?DATA.today:null);
            const planB=bar(ch.ps,ch.pe),actB=bar(ch.as,actEnd);
            const noUser=!ch.us||ch.us==='Unassigned'||ch.us==='None None';
            const userBadge=noUser
              ?`<span style="font-size:8px;background:#fff7ed;color:#c2410c;border:1px solid #fed7aa;border-radius:10px;padding:1px 7px;white-space:nowrap;flex-shrink:0;font-weight:600">Not Assigned</span>`
              :`<span style="font-size:8px;background:#eff6ff;color:#1d4ed8;border:1px solid #bfdbfe;border-radius:10px;padding:1px 7px;white-space:nowrap;flex-shrink:0">&#128100; ${{ch.us}}</span>`;
            const tipHtml=`<b>${{ch.n}}</b><br><b>Status:</b> ${{SL[ch.st]}}<br>
              <b>User:</b> ${{noUser?'<span style="color:#f97316">Not Assigned</span>':ch.us}}<br>
              <b>Dept:</b> ${{ch.dp}}<br>
              <b>Plan:</b> ${{fmtD(ch.ps)}} &rarr; ${{fmtD(ch.pe)}}<br>
              <b>Actual:</b> ${{fmtD(ch.as)}} &rarr; ${{ch.ae?fmtD(ch.ae):(ch.st==='active'?'<span style="color:#fbbf24">Ongoing</span>':'&mdash;')}}`;
            const row=document.createElement('div');
            row.className=`grow child st-${{ch.st}}`;row.style.gridTemplateColumns=COLS;row.style.minHeight='34px';
            row.innerHTML=`
              <div class="cn cnl" style="min-height:34px;padding-left:68px;font-size:10px;color:#475569;
                   flex-wrap:wrap;row-gap:2px;padding-top:4px;padding-bottom:4px;
                   white-space:normal;align-items:flex-start">
                <span style="flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-weight:500">${{ch.n}}</span>
                <div style="display:flex;align-items:center;gap:4px;width:100%;flex-shrink:0">
                  ${{userBadge}}
                  <span class="badge" style="background:${{SBG[ch.st]}};color:${{STC[ch.st]}};font-size:8px">${{SL[ch.st]}}</span>
                </div>
              </div>
              <div class="cp cpl" style="min-height:34px;font-size:9px;color:${{SC[ch.st]}}"></div>
              <div class="cb" style="min-height:34px">
                ${{gl(false)}}
                ${{planB?`<div style="position:absolute;left:${{planB.L}};width:${{planB.W}};top:8px;bottom:8px;border-radius:3px;background:#dbeafe;border:1px solid #93c5fd"></div>`:''}};
                ${{actB?`<div style="position:absolute;left:${{actB.L}};width:${{actB.W}};top:9px;bottom:9px;border-radius:3px;background:${{SC[ch.st]}};opacity:.82"></div>`:''}};
              </div>`;
            row.addEventListener('mouseenter',e=>showTip(e,tipHtml));
            row.addEventListener('mouseleave',hideTip);
            C.appendChild(row);
          }});
        }});
      }});
    }});
  }});
}}
function buildHeader(){{
  const tl=document.getElementById('tl');
  let yrH='',qH='',mH='';
  Object.entries(yrs).forEach(([y,d])=>{{yrH+=`<div style="flex:none;width:${{ph(d)}};text-align:center;font-size:11px;font-weight:700;color:#e2e8f0;border-right:1px solid rgba(255,255,255,.1);padding:5px 0">${{y}}</div>`;}});
  Object.entries(qs).forEach(([q,d])=>{{qH+=`<div style="flex:none;width:${{ph(d)}};text-align:center;font-size:9px;color:#7eb3e8;border-right:.5px solid rgba(255,255,255,.08);padding:3px 0">${{q}}</div>`;}});
  months.forEach(m=>{{mH+=`<div style="flex:none;width:${{ph(m.days)}};text-align:center;font-size:7.5px;color:#4a7aaa;border-right:.5px solid rgba(255,255,255,.06);padding:2px 0;overflow:hidden">${{m.lbl}}</div>`;}});
  const tdLabel=todayOff!==null&&todayOff>=0&&todayOff<=DATA.td
    ?`<div style="position:absolute;left:${{pc(todayOff)}};top:0;bottom:0;width:2px;background:#ff6b35;z-index:10"></div>
      <div style="position:absolute;left:${{pc(todayOff)}};top:2px;font-size:8px;background:#ff6b35;color:#fff;padding:1px 4px;border-radius:3px;transform:translateX(-50%);font-weight:700;z-index:11;white-space:nowrap">Today</div>`:'';
  tl.innerHTML=`
    <div style="background:#0d1e30">
      <div style="display:grid;grid-template-columns:${{COLS}};border-bottom:1px solid rgba(255,255,255,.1)">
        <div style="border-right:1px solid rgba(255,255,255,.1);height:24px;display:flex;align-items:center;padding:0 10px;font-size:10px;font-weight:600;color:#7eb3e8;text-transform:uppercase;letter-spacing:.5px">Project / Task</div>
        <div style="border-right:1px solid rgba(255,255,255,.1);height:24px;display:flex;align-items:center;justify-content:flex-end;padding:0 8px;font-size:10px;font-weight:600;color:#7eb3e8">Done%</div>
        <div style="position:relative;height:24px">${{tdLabel}}<div style="display:flex;height:100%">${{yrH}}</div></div>
      </div>
      <div style="display:grid;grid-template-columns:${{COLS}};border-bottom:.5px solid rgba(255,255,255,.07)">
        <div style="border-right:1px solid rgba(255,255,255,.08);height:17px"></div>
        <div style="border-right:1px solid rgba(255,255,255,.08);height:17px"></div>
        <div style="display:flex">${{qH}}</div>
      </div>
      <div style="display:grid;grid-template-columns:${{COLS}};border-bottom:1px solid rgba(255,255,255,.12)">
        <div style="border-right:1px solid rgba(255,255,255,.08);height:14px;padding:0 10px;font-size:8px;color:#4a7aaa;display:flex;align-items:center;gap:5px">
          <span style="background:#dbeafe;border:1px solid #93c5fd;border-radius:2px;padding:1px 4px;color:#1d4ed8">Plan</span>
          <span style="background:#10b98122;border:1px solid #10b98166;border-radius:2px;padding:1px 4px;color:#065f46">Actual</span>
        </div>
        <div style="border-right:1px solid rgba(255,255,255,.08);height:14px"></div>
        <div style="display:flex">${{mH}}</div>
      </div>
    </div>
    <div id="rows"></div>`;
}}
try{{
  var _pm=window.parent.postMessage.bind(window.parent);
  window.parent.postMessage=(msg,...rest)=>{{
    if(msg&&(msg.type==='streamlit:setFrameHeight'||(typeof msg==='string'&&msg.includes('setFrameHeight'))))return;
    _pm(msg,...rest);
  }};
}}catch(e){{}}
buildHeader();render();
</script></body></html>"""
    components.html(GANTT, height=max(700,n_proj*48+160), scrolling=True)
    st.markdown(
        f"<div style='text-align:center;color:#64748b;font-size:.72rem;margin-top:6px'>"
        f"Topia Life Sciences - {n_proj} projects - {len(df_all):,} tasks - pms_v1</div>",
        unsafe_allow_html=True)
# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 - CAPACITY UTILIZATION
# ══════════════════════════════════════════════════════════════════════════════
with tab2:
  try:

    cap            = df_all.copy()
    cap["_st"]     = cap.apply(lambda r: child_status(r,today),axis=1)
    cap["is_ua"]   = (cap["user_full_name"]=="Unassigned")|cap["user_full_name"].isna()
    assigned       = cap[~cap["is_ua"]].copy()
    assigned["plan_month"]   = assigned["plan_start_date"].dt.to_period("M")
    assigned["actual_month"] = assigned["actual_start_date"].dt.to_period("M")
    assigned["_adj_spent"]   = assigned.apply(
        lambda r: r.hours if pd.notna(r.actual_start_date) and pd.notna(r.actual_end_date) else r.spent_hours,
        axis=1)
    valid_months = assigned["plan_month"].dropna()
    if len(valid_months) > 0:
        month_range = pd.period_range(valid_months.min(), valid_months.max(), freq="M")
    else:
        month_range = pd.period_range(pd.Period(str(today.year), "M"),
                                      pd.Period(str(today.year), "M"), freq="M")
    # ── Capacity constants: 40h/week → 160h/month per user ───────────────────
    MONTHLY_CAP = 160   # 4 weeks × 40h
    # ── Monthly aggregation ───────────────────────────────────────────────────
    monthly_rows=[]
    for period in month_range:
        planned_df = assigned[assigned["plan_month"]==period]
        spent_df   = assigned[assigned["actual_month"]==period]
        active_u   = int(planned_df["user_full_name"].nunique())
        available  = active_u * MONTHLY_CAP          # each user = 160h that month
        planned_h  = float(planned_df["hours"].sum())
        spent_h    = float(spent_df["_adj_spent"].sum())
        monthly_rows.append({
            "month"    : period.strftime("%b %Y"),
            "year_mo"  : str(period),
            "available": float(available),
            "planned"  : round(planned_h, 1),
            "spent"    : round(spent_h, 1),
            "users"    : active_u,
            "util_pct" : round(spent_h  / available * 100, 1) if available > 0 else 0,
            "plan_pct" : round(planned_h / available * 100, 1) if available > 0 else 0,
        })
    # ── Per-user per-month (each user gets 160h capacity per month) ───────────
    um_planned = (assigned.dropna(subset=["plan_month"])
                  .groupby(["user_full_name","plan_month"])
                  .agg(planned=("hours","sum"), tasks=("child_task_name","count"))
                  .reset_index())
    um_spent   = (assigned.dropna(subset=["actual_month"])
                  .groupby(["user_full_name","actual_month"])["_adj_spent"].sum()
                  .reset_index()
                  .rename(columns={"actual_month":"plan_month","_adj_spent":"spent"}))
    user_mo    = um_planned.merge(um_spent, on=["user_full_name","plan_month"], how="left")
    user_mo["spent"]     = user_mo["spent"].fillna(0).round(1)
    user_mo["planned"]   = user_mo["planned"].round(1)
    user_mo["available"] = MONTHLY_CAP                   # fixed 160h per user per month
    user_mo["util_pct"]  = (user_mo["spent"]   / MONTHLY_CAP * 100).round(1)
    user_mo["plan_pct"]  = (user_mo["planned"] / MONTHLY_CAP * 100).round(1)
    user_mo["month_str"] = user_mo["plan_month"].dt.strftime("%b %Y")
    user_mo              = user_mo.sort_values(["user_full_name","plan_month"])
    # ── Per-user totals: capacity = active months × 160h ─────────────────────
    user_months = (assigned.dropna(subset=["plan_month"])
                   .groupby("user_full_name")["plan_month"].nunique()
                   .reset_index(name="active_months"))
    user_months["capacity"] = user_months["active_months"] * MONTHLY_CAP
    user_cap = (assigned.groupby(["user_full_name","department_name"],sort=False)
                .agg(total_tasks=("_st","count"),allocated=("hours","sum"),
                     spent=("_adj_spent","sum"),
                     done=("_st",lambda x:(x=="done").sum()),
                     active=("_st",lambda x:(x=="active").sum()),
                     overdue=("_st",lambda x:(x=="overdue").sum()),
                     todo=("_st",lambda x:(x=="todo").sum()))
                .reset_index())
    user_cap = user_cap.merge(user_months, on="user_full_name", how="left")
    user_cap["capacity"]   = user_cap["capacity"].fillna(MONTHLY_CAP)  # default 1 month if no plan dates
    user_cap["allocated"]  = user_cap["allocated"].round(1)
    user_cap["spent"]      = user_cap["spent"].round(1)
    user_cap["pending"]    = (user_cap["allocated"]-user_cap["spent"]).clip(lower=0).round(1)
    user_cap["utilization"]= (user_cap["spent"]/user_cap["capacity"].replace(0,float("nan"))*100).fillna(0).round(1)
    user_cap["completion"] = (user_cap["done"]/user_cap["total_tasks"]*100).round(1)
    user_projects = (assigned.groupby("user_full_name")["project_name"]
                    .apply(lambda x:sorted(x.unique().tolist())).to_dict())
    user_cap["projects"] = user_cap["user_full_name"].map(user_projects)
    user_cap = user_cap.sort_values("allocated",ascending=False)
    # ── Dept totals ───────────────────────────────────────────────────────────
    dept_cap = (assigned.groupby("department_name")
                .agg(users=("user_full_name","nunique"),total_tasks=("_st","count"),
                     allocated=("hours","sum"),spent=("_adj_spent","sum"),
                     overdue=("_st",lambda x:(x=="overdue").sum()))
                .reset_index().sort_values("allocated",ascending=False))
    dept_cap["pending"]     = (dept_cap["allocated"]-dept_cap["spent"]).clip(lower=0).round(1)
    dept_cap["utilization"] = (dept_cap["spent"]/dept_cap["allocated"].replace(0,float("nan"))*100).fillna(0).round(1)
    # ── Project × dept ────────────────────────────────────────────────────────
    proj_dept     = (assigned.groupby(["project_name","department_name"])["hours"].sum().reset_index())
    proj_dept_piv = (proj_dept.pivot(index="project_name",columns="department_name",values="hours")
                    .fillna(0).reset_index())
    # ── Colours ───────────────────────────────────────────────────────────────
    PAL        = ["#f97316","#3b82f6","#a855f7","#10b981","#f43f5e","#06b6d4","#eab308","#ec4899","#6366f1","#14b8a6","#84cc16"]
    depts      = dept_cap["department_name"].tolist()
    dept_color = {d:PAL[i%len(PAL)] for i,d in enumerate(depts)}
    # ── Totals ────────────────────────────────────────────────────────────────
    total_cap    = float(user_cap["capacity"].sum())
    total_alloc  = float(user_cap["allocated"].sum())
    total_spent  = float(user_cap["spent"].sum())
    total_pend   = float(user_cap["pending"].sum())
    overall_util = round(total_spent/total_cap*100,1) if total_cap>0 else 0
    over_alloc   = int((user_cap["utilization"]>100).sum())
    under_util   = int((user_cap["utilization"]<65).sum())
    ua_hrs       = float(cap[cap["is_ua"]]["hours"].sum())
    # ── JSON ──────────────────────────────────────────────────────────────────
    monthly_json = json.dumps(monthly_rows, default=str)
    user_mo_json = json.dumps([
        {"user":str(r.user_full_name),"month":str(r.month_str),
         "available":float(r.available),"planned":float(r.planned),
         "spent":float(r.spent),"util_pct":float(r.util_pct),
         "plan_pct":float(r.plan_pct),"tasks":int(r.tasks)}
        for _,r in user_mo.iterrows()], default=str)
    team_json = json.dumps([
        {"name":str(r.user_full_name),"role":str(r.department_name),
         "capacity":float(r.capacity),"allocated":float(r.allocated),
         "spent":float(r.spent),"pending":float(r.pending),
         "utilization":float(r.utilization),"completion":float(r.completion),
         "tasks":int(r.total_tasks),"done":int(r.done),"active":int(r.active),
         "overdue":int(r.overdue),"todo":int(r.todo),
         "projects":r.projects[:3],
         "color":dept_color.get(r.department_name,"#3b82f6")}
        for _,r in user_cap.iterrows()], default=str)
    dept_json = json.dumps([
        {"dept":str(r.department_name),"allocated":float(r.allocated),
         "spent":float(r.spent),"pending":float(r.pending),
         "utilization":float(r.utilization),"users":int(r.users),
         "tasks":int(r.total_tasks),"overdue":int(r.overdue),
         "color":dept_color.get(r.department_name,"#3b82f6")}
        for _,r in dept_cap.iterrows()], default=str)
    proj_cols = [c for c in proj_dept_piv.columns if c!="project_name"]
    proj_json = json.dumps([
        dict({"project":str(r["project_name"])},**{c:float(r[c]) for c in proj_cols})
        for _,r in proj_dept_piv.iterrows()], default=str)
    dept_colors_json = json.dumps(dept_color, default=str)
    # ── Project budget vs spend ───────────────────────────────────────────────
    # When both actual_start and actual_end are filled, treat plan hours as spend
    _pb = df_all.copy()
    _pb["_adj_spent"] = _pb.apply(
        lambda r: r.hours if pd.notna(r.actual_start_date) and pd.notna(r.actual_end_date) else r.spent_hours,
        axis=1)
    proj_budget = (_pb.groupby("project_name")
                   .agg(budget=("hours","sum"), spent=("_adj_spent","sum"),
                        tasks=("child_task_name","count"),
                        done=("_st", lambda x:(x=="done").sum()),
                        assigned=("user_full_name",
                                  lambda x: x[~x.isin(["Unassigned","None None",""])
                                              & x.notna()].nunique()),
                        unassigned=("user_full_name",
                                    lambda x: x[x.isin(["Unassigned","None None",""])
                                                | x.isna()].count()))
                   .reset_index().sort_values("budget",ascending=False))
    proj_budget["balance"] = (proj_budget["budget"]-proj_budget["spent"]).clip(lower=0).round(1)
    proj_budget["budget"]  = proj_budget["budget"].round(1)
    proj_budget["spent"]   = proj_budget["spent"].round(1)
    proj_budget["pct"]     = (proj_budget["spent"]/proj_budget["budget"].replace(0,float("nan"))*100).fillna(0).round(1)
    proj_budget["comp_pct"]= (proj_budget["done"]/proj_budget["tasks"].replace(0,float("nan"))*100).fillna(0).round(1)
    proj_budget_json = json.dumps([
        {"project":str(r.project_name),"budget":float(r.budget),"spent":float(r.spent),
         "balance":float(r.balance),"pct":float(r.pct),"tasks":int(r.tasks),
         "done":int(r.done),"comp_pct":float(r.comp_pct),
         "assigned":int(r.assigned),"unassigned":int(r.unassigned)}
        for _,r in proj_budget.iterrows()], default=str)
    # ── User × Project hours breakdown ───────────────────────────────────────
    user_proj = (assigned.groupby(["user_full_name","project_name"],sort=False)
                 .agg(budget=("hours","sum"), spent=("_adj_spent","sum"),
                      tasks=("child_task_name","count"),
                      done=("_st", lambda x:(x=="done").sum()))
                 .reset_index())
    user_proj["budget"] = user_proj["budget"].round(1)
    user_proj["spent"]  = user_proj["spent"].round(1)
    user_proj["pct"]    = (user_proj["spent"]/user_proj["budget"].replace(0,float("nan"))*100).fillna(0).round(1)
    user_proj = user_proj.sort_values(["user_full_name","budget"],ascending=[True,False])
    user_proj_json = json.dumps([
        {"user":str(r.user_full_name),"project":str(r.project_name),
         "budget":float(r.budget),"spent":float(r.spent),"pct":float(r.pct),
         "tasks":int(r.tasks),"done":int(r.done)}
        for _,r in user_proj.iterrows()], default=str)
    # ── Overdue tasks ─────────────────────────────────────────────────────────
    ov_df = df_all[df_all["_st"].isin(["overdue","late"])].copy()
    ov_df = ov_df.sort_values(["project_name","plan_end_date","plan_start_date"])
    overdue_json = json.dumps([
        {"project" : str(r.project_name),
         "task"    : str(r.child_task_name),
         "dept"    : str(r.department_name),
         "user"    : (None if str(r.user_full_name) in ("Unassigned","None None","")
                      else str(r.user_full_name)),
         "budget"  : float(r.hours),
         "ps"      : r.plan_start_date.strftime("%Y-%m-%d") if pd.notna(r.plan_start_date) else None,
         "pe"      : r.plan_end_date.strftime("%Y-%m-%d")   if pd.notna(r.plan_end_date)   else None,
         "as_"     : r.actual_start_date.strftime("%Y-%m-%d") if pd.notna(r.actual_start_date) else None,
         "st"      : str(r._st)}
        for _,r in ov_df.iterrows()], default=str)
    # ── Last-week planning ────────────────────────────────────────────────────
    _today_w  = today
    _last_mon = _today_w - timedelta(days=_today_w.weekday() + 7)
    _last_sun = _last_mon + timedelta(days=6)
    _week_dates  = [(_last_mon + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7)]
    _week_labels = [(_last_mon + timedelta(days=i)).strftime("%a %d %b")  for i in range(7)]
    _week_label  = f"{_last_mon.strftime('%d %b')} – {_last_sun.strftime('%d %b %Y')}"
    try:
        wp_df = load_weekly_plan()
    except Exception:
        wp_df = pd.DataFrame()
    if not wp_df.empty:
        # pivot: (user, project, subtask, status, priority) → {date: planned_hours}
        _wp_pivot = {}
        for _, r in wp_df.iterrows():
            d = r.planned_date.strftime("%Y-%m-%d") if pd.notna(r.planned_date) else None
            if not d or d not in _week_dates:
                continue
            key = (str(r.user_full_name), str(r.project_name),
                   str(r.subtask_name), str(r.current_status), str(r.priority_label))
            if key not in _wp_pivot:
                _wp_pivot[key] = {dd: 0.0 for dd in _week_dates}
            _wp_pivot[key][d] = round(_wp_pivot[key][d] + float(r.planned_hours), 2)
        weekly_plan_json = json.dumps([
            {"user":k[0],"project":k[1],"subtask":k[2],"status":k[3],"priority":k[4],"hours":v}
            for k,v in _wp_pivot.items()], default=str)
    else:
        weekly_plan_json = "[]"
    weekly_week_label  = json.dumps(_week_label)
    weekly_dates_json  = json.dumps(_week_dates)
    weekly_labels_json = json.dumps(_week_labels)
    # ── Month-to-date planning ────────────────────────────────────────────────
    _month_start = _today_w.replace(day=1)
    _month_dates  = [(_month_start + timedelta(days=i)).strftime("%Y-%m-%d")
                     for i in range((_today_w - _month_start).days + 1)]
    _month_labels = [(_month_start + timedelta(days=i)).strftime("%d %b")
                     for i in range((_today_w - _month_start).days + 1)]
    _month_label  = f"{_month_start.strftime('%d %b')} – {_today_w.strftime('%d %b %Y')}"
    try:
        mp_df = load_monthly_plan()
    except Exception:
        mp_df = pd.DataFrame()
    if not mp_df.empty:
        _mp_pivot = {}
        for _, r in mp_df.iterrows():
            d = r.planned_date.strftime("%Y-%m-%d") if pd.notna(r.planned_date) else None
            if not d or d not in _month_dates:
                continue
            key = (str(r.user_full_name), str(r.project_name),
                   str(r.subtask_name), str(r.current_status), str(r.priority_label))
            if key not in _mp_pivot:
                _mp_pivot[key] = {dd: 0.0 for dd in _month_dates}
            _mp_pivot[key][d] = round(_mp_pivot[key][d] + float(r.planned_hours), 2)
        monthly_plan_json = json.dumps([
            {"user":k[0],"project":k[1],"subtask":k[2],"status":k[3],"priority":k[4],"hours":v}
            for k,v in _mp_pivot.items()], default=str)
    else:
        monthly_plan_json = "[]"
    monthly_plan_label  = json.dumps(_month_label)
    monthly_plan_dates  = json.dumps(_month_dates)
    monthly_plan_labels = json.dumps(_month_labels)
    # Build data payload; escape </ so </script> inside values won't close the tag
    _data_content = (
        "const MONTHLY="    + monthly_json       + ";"
        "const USER_MO="    + user_mo_json        + ";"
        "const TEAM="       + team_json           + ";"
        "const DEPTS="      + dept_json           + ";"
        "const PROJ="       + proj_json           + ";"
        "const DCOLORS="    + dept_colors_json    + ";"
        "const TOTAL_CAP="  + str(round(total_cap,1))    + ";"
        "const TOTAL_ALLOC="+ str(round(total_alloc,1))  + ";"
        "const TOTAL_SPENT="+ str(round(total_spent,1))  + ";"
        "const TOTAL_PEND=" + str(round(total_pend,1))   + ";"
        "const OVERALL="    + str(round(overall_util,1)) + ";"
        "const OVER_ALLOC=" + str(over_alloc)            + ";"
        "const UNDER_UTIL=" + str(under_util)            + ";"
        "const UA_HRS="      + str(round(ua_hrs,1))       + ";"
        "const PROJ_BUDGET="  + proj_budget_json           + ";"
        "const USER_PROJ="    + user_proj_json             + ";"
        "const OVERDUE="      + overdue_json               + ";"
        "const WEEKLY_PLAN="   + weekly_plan_json            + ";"
        "const WEEK_LABEL="    + weekly_week_label           + ";"
        "const WEEK_DATES="    + weekly_dates_json           + ";"
        "const WEEK_LABELS="   + weekly_labels_json          + ";"
        "const MONTHLY_PLAN="  + monthly_plan_json           + ";"
        "const MONTH_LABEL="   + monthly_plan_label          + ";"
        "const MONTH_DATES="   + monthly_plan_dates          + ";"
        "const MONTH_LABELS="  + monthly_plan_labels         + ";"
    )
    _data_script = "<script>" + _data_content.replace("</", "<\\/") + "</script>"
    CAP_HTML = """<!DOCTYPE html><html><head><meta charset="utf-8">
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
html,body{{margin:0;padding:0;background:#080b12;font-family:'Segoe UI',-apple-system,sans-serif;color:#e2e8f0}}
/* chart-box: fixed-height wrapper that constrains Chart.js responsive resize */
.chart-box{{position:relative;width:100%}}
body{{font-family:Segoe UI,-apple-system,sans-serif;color:#e2e8f0}}
.hdr{{background:linear-gradient(135deg,#0f1520,#131929);border-bottom:1px solid #1e2436;padding:20px 28px 0}}
.hdr-top{{display:flex;justify-content:space-between;align-items:flex-end;margin-bottom:16px}}
.hdr-lbl{{font-size:10px;letter-spacing:3px;color:#475569;text-transform:uppercase;margin-bottom:4px}}
.hdr-ttl{{font-size:20px;font-weight:800;color:#f8fafc;letter-spacing:-.5px}}
.hdr-sub{{font-size:10px;color:#475569;margin-top:3px}}
.tabs{{display:flex;gap:2px}}
.tab{{background:transparent;border:none;border-bottom:2px solid transparent;color:#64748b;
      padding:8px 18px;cursor:pointer;font-size:12px;font-weight:400;
      text-transform:capitalize;border-radius:6px 6px 0 0;transition:all .2s;font-family:inherit}}
.tab.active{{background:#1e2d4a;border-bottom-color:#3b82f6;color:#93c5fd;font-weight:700}}
.tab:hover:not(.active){{color:#94a3b8}}
.content{{padding:0}}
.kpi-grid{{display:grid;grid-template-columns:repeat(5,1fr);gap:12px;margin-bottom:22px}}
.kpi{{background:#0f1520;border:1px solid #1e2436;border-radius:12px;padding:14px 18px}}
.kpi-lbl{{font-size:9px;color:#64748b;letter-spacing:1px;text-transform:uppercase;margin-bottom:5px}}
.kpi-val{{font-size:24px;font-weight:900;line-height:1}}
.kpi-sub{{font-size:9px;color:#475569;margin-top:4px}}
.card{{background:#0f1520;border:1px solid #1e2436;border-radius:12px;padding:18px}}
.card-ttl{{font-size:12px;font-weight:700;color:#94a3b8;margin-bottom:14px}}
.two-col{{display:grid;grid-template-columns:1.4fr 1fr;gap:14px;margin-bottom:14px}}
.one-col{{margin-bottom:14px}}
.ubar{{margin-bottom:10px}}
.ubar-hdr{{display:flex;justify-content:space-between;margin-bottom:3px;font-size:11px}}
.ubar-name{{color:#cbd5e1;font-weight:600}}
.ubar-pct{{font-weight:700}}
.ubar-track{{background:#1e2130;border-radius:4px;height:7px;overflow:hidden}}
.ubar-fill{{height:100%;border-radius:4px;transition:width .8s cubic-bezier(.4,0,.2,1)}}
.ubar-foot{{display:flex;justify-content:space-between;font-size:9px;color:#64748b;margin-top:2px}}
.ubar-scroll{{max-height:260px;overflow-y:auto;padding-right:4px}}
.team-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:12px}}
.team-card{{background:#0f1520;border:1px solid #1e2436;border-radius:12px;padding:14px}}
/* Monthly table */
.mo-tbl{{width:100%;border-collapse:collapse;font-size:11px}}
.mo-tbl th{{background:#1e2d4a;color:#7eb3e8;font-weight:600;padding:7px 10px;
            text-align:left;font-size:9px;text-transform:uppercase;letter-spacing:.5px;
            position:sticky;top:0;z-index:1}}
.mo-tbl td{{padding:6px 10px;border-bottom:.5px solid #1e2436;color:#cbd5e1;vertical-align:middle}}
.mo-tbl tr:hover td{{background:#0f1828}}
.bar-cell{{display:flex;align-items:center;gap:6px}}
.bm{{flex:1;height:5px;background:#1e2436;border-radius:3px;overflow:hidden;min-width:40px}}
.bm-f{{height:100%;border-radius:3px}}
/* User monthly pivot */
.um-tbl{{width:100%;border-collapse:collapse;font-size:10px;white-space:nowrap}}
.um-tbl th{{background:#1e2d4a;color:#7eb3e8;padding:6px 8px;font-size:9px;
            text-align:center;position:sticky;top:0;z-index:1;font-weight:600}}
.um-tbl th:first-child{{text-align:left;position:sticky;left:0;z-index:2;background:#1e2d4a}}
.um-tbl td{{padding:4px 6px;border-bottom:.5px solid #1e2436;border-right:.5px solid #1e2436;
            text-align:center;vertical-align:top}}
.um-tbl td:first-child{{text-align:left;font-weight:600;color:#f1f5f9;position:sticky;left:0;
                         background:#0f1520;z-index:1;white-space:nowrap;padding:4px 10px}}
.um-tbl tr:hover td{{background:#0f1828}}
.um-tbl tr:hover td:first-child{{background:#111d2e}}
.cell-avail{{font-size:9px;color:#475569;margin-bottom:2px}}
.cell-bar-row{{display:flex;align-items:center;gap:4px;margin-bottom:2px}}
.cell-val{{font-size:9px;min-width:28px;text-align:right}}
.cell-mini{{flex:1;height:4px;background:#1e2436;border-radius:2px;overflow:hidden;min-width:30px}}
.cell-mini-f{{height:100%;border-radius:2px}}
.cell-util{{font-size:9px;font-weight:700;margin-top:1px}}
</style></head>
<body>
<div style="display:flex;flex-direction:column;min-height:100vh;background:#080b12">
  <div class="hdr">
    <div class="hdr-top">
      <div>
        <div class="hdr-lbl">Drug Discovery - Topia Life Sciences</div>
        <div class="hdr-ttl">Project Capacity &amp; Execution Dashboard</div>
        <div class="hdr-sub">Portfolio health - Team workload - Risk visibility</div>
      </div>
      <div id="main-badge"></div>
    </div>
    <div class="tabs" id="tabs"></div>
  </div>
  <div class="content" id="content" style="flex:1;padding:22px 28px"></div>
</div>
<script>
/* guard: if _data_script failed, define empty fallbacks so the UI still loads */
if(typeof PROJ_BUDGET==='undefined'){{window._dataError=true;}}
const _PB=typeof PROJ_BUDGET!=='undefined'?PROJ_BUDGET:[];
const _OV=typeof OVERDUE!=='undefined'?OVERDUE:[];
const _UP=typeof USER_PROJ!=='undefined'?USER_PROJ:[];
const _WP=typeof WEEKLY_PLAN!=='undefined'?WEEKLY_PLAN:[];
const _MP=typeof MONTHLY_PLAN!=='undefined'?MONTHLY_PLAN:[];
const PAL=['#f97316','#3b82f6','#a855f7','#10b981','#f43f5e','#06b6d4','#eab308','#ec4899'];
let activeTab='portfolio';
const charts={{}};
/* Portfolio completion badge - computed safely */
try{{
  const _totT=_PB.reduce((s,p)=>s+p.tasks,0);
  const _doneT=_PB.reduce((s,p)=>s+p.done,0);
  const _pc2=_totT>0?Math.round(_doneT/_totT*100):0;
  const _c=_pc2>=70?'#10b981':_pc2>=40?'#f97316':'#f43f5e';
  const _mb=document.getElementById('main-badge');
  if(_mb){{
    _mb.style.cssText=`background:${{_c}}22;border:1px solid ${{_c}}55;border-radius:12px;padding:10px 16px;text-align:center`;
    _mb.innerHTML=`<div style="font-size:9px;color:#94a3b8;margin-bottom:2px">Portfolio Completion</div><div style="font-size:26px;font-weight:900;color:${{_c}}">${{_pc2}}%</div><div style="font-size:9px;color:#475569;margin-top:2px">${{_doneT}} / ${{_totT}} tasks</div>`;
  }}
}}catch(e){{console.error('badge error',e);}}
function uc2(pct){{return pct>100?'#f43f5e':pct>=80?'#10b981':pct>=50?'#f97316':'#3b82f6';}}
function fmt(n){{return Number(n).toLocaleString('en-US',{{maximumFractionDigits:0}});}}
function fmtH(n){{return fmt(n)+'h';}}
function destroyChart(id){{if(charts[id]){{charts[id].destroy();delete charts[id];}}}}
function insight(msg,col){{return`<div style="background:${{col}}18;border-left:3px solid ${{col}};border-radius:0 8px 8px 0;padding:8px 14px;margin-bottom:14px;font-size:11px;color:#e2e8f0">${{msg}}</div>`;}}
const TABS=[['portfolio','📊 Portfolio'],['team','👥 Team Load'],['risk','⚠️ At Risk'],['weekly','📅 Last Week Planning'],['monthly','📆 This Month Planning']];
function renderTabs(){{
  document.getElementById('tabs').innerHTML=TABS.map(([id,lbl])=>
    `<button class="tab ${{id===activeTab?'active':''}}" onclick="switchTab('${{id}}')">${{lbl}}</button>`).join('');
}}
function switchTab(t){{activeTab=t;renderTabs();renderContent();}}
renderTabs();
if(window._dataError){{document.getElementById('content').innerHTML='<div style="color:#f43f5e;padding:20px;font-size:13px">⚠ Data failed to load. Check browser console (F12) for errors.</div>';}}

function ubarHTML(name,capacity,spent){{
  const pct=capacity>0?Math.min(Math.round(spent/capacity*100),150):0;
  const color=uc2(pct);
  return`<div class="ubar">
    <div class="ubar-hdr">
      <span class="ubar-name">${{name}}</span>
      <span class="ubar-pct" style="color:${{color}}">${{pct}}%${{pct>100?' ⚠':''}}</span>
    </div>
    <div class="ubar-track"><div class="ubar-fill" style="width:${{Math.min(pct,100)}}%;background:${{color}}"></div></div>
    <div class="ubar-foot"><span>${{fmtH(spent)}} spent</span><span>${{fmtH(capacity)}} capacity</span></div>
  </div>`;
}}
/* ── PORTFOLIO ── */
/* ── PORTFOLIO ── */
function renderPortfolio(){{
  const c=document.getElementById('content');
  const totalBudget  =PROJ_BUDGET.reduce((s,p)=>s+p.budget,0);
  const totalSpent   =PROJ_BUDGET.reduce((s,p)=>s+p.spent,0);
  const totalBal     =PROJ_BUDGET.reduce((s,p)=>s+p.balance,0);
  const overBudget   =PROJ_BUDGET.filter(p=>p.spent>p.budget).length;
  const onTrack      =PROJ_BUDGET.filter(p=>p.comp_pct>=50&&p.spent<=p.budget).length;
  const avgComp      =PROJ_BUDGET.length?Math.round(PROJ_BUDGET.reduce((s,p)=>s+p.comp_pct,0)/PROJ_BUDGET.length):0;
  const spendPct     =totalBudget>0?Math.round(totalSpent/totalBudget*100):0;
  /* ── insight sentence ── */
  const insightMsg=overBudget>0
    ?`<b>${{onTrack}}</b> of <b>${{PROJ_BUDGET.length}}</b> projects on track - <b style="color:#f43f5e">${{overBudget}}</b> over budget - Portfolio is <b>${{spendPct}}%</b> spent with <b>${{avgComp}}%</b> avg completion`
    :`All <b>${{PROJ_BUDGET.length}}</b> projects within budget - Portfolio is <b>${{spendPct}}%</b> spent with <b>${{avgComp}}%</b> avg completion`;
  const insCol=overBudget>0?'#f43f5e':'#10b981';
  const chartH=Math.max(200,PROJ_BUDGET.length*30);
  c.innerHTML=`
    ${{insight(insightMsg,insCol)}}
    <div class="kpi-grid" style="grid-template-columns:repeat(5,1fr);margin-bottom:16px">
      ${{[
        {{l:'Projects',           v:PROJ_BUDGET.length,      s:'in portfolio',          col:'#3b82f6'}},
        {{l:'Total Budget',       v:fmtH(totalBudget),       s:'planned task hours',    col:'#a855f7'}},
        {{l:'Total Spent',        v:fmtH(totalSpent),        s:'actual hours logged',   col:'#10b981'}},
        {{l:'Remaining',          v:fmtH(totalBal),          s:'budget not yet spent',  col:'#f59e0b'}},
        {{l:'Over Budget',        v:overBudget,              s:'projects spent > budget',col:'#f43f5e'}},
      ].map(k=>`<div class="kpi" style="border-top:3px solid ${{k.col}}">
        <div class="kpi-lbl">${{k.l}}</div>
        <div class="kpi-val" style="color:${{k.col}}">${{k.v}}</div>
        <div class="kpi-sub">${{k.s}}</div>
      </div>`).join('')}}
    </div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:14px">
      <div class="card">
        <div class="card-ttl">💰 Budget vs Spent — per Project</div>
        <div class="chart-box" style="height:${{chartH}}px"><canvas id="budgetChart"></canvas></div>
      </div>
      <div class="card">
        <div class="card-ttl">✅ Completion % — per Project</div>
        <div class="chart-box" style="height:${{chartH}}px"><canvas id="compChart"></canvas></div>
      </div>
    </div>
    <div class="card one-col">
      <div class="card-ttl">📋 Project Detail
        <span style="font-size:9px;font-weight:400;color:#64748b;margin-left:8px">Budget - Spend - Balance - Completion - Manpower</span>
      </div>
      <div style="overflow:auto;max-height:440px">
        <table class="mo-tbl">
          <thead><tr>
            <th>Project</th><th>Budget</th><th>Spent</th><th>Balance</th>
            <th>% Used</th><th>Completion</th><th>Assigned</th><th>Unassigned</th>
          </tr></thead>
          <tbody>
            ${{PROJ_BUDGET.map(p=>{{
              const ov=p.spent>p.budget;
              const bCol=p.pct>100?'#f43f5e':p.pct>=80?'#10b981':p.pct>=50?'#f97316':'#3b82f6';
              const cCol=p.comp_pct>=80?'#10b981':p.comp_pct>=40?'#f97316':'#3b82f6';
              const uaPct=p.tasks>0?Math.round(p.unassigned/p.tasks*100):0;
              return`<tr>
                <td style="font-weight:600;color:#f1f5f9;white-space:normal;word-break:break-word;max-width:200px">${{p.project}}</td>
                <td style="color:#a855f7;font-weight:600">${{fmtH(p.budget)}}</td>
                <td style="color:${{bCol}};font-weight:600">${{fmtH(p.spent)}}</td>
                <td>${{ov?`<span style="color:#f43f5e;font-weight:700">▲ ${{fmtH(p.spent-p.budget)}}</span>`:`<span style="color:#10b981">${{fmtH(p.balance)}}</span>`}}</td>
                <td><div class="bar-cell"><span style="min-width:34px;font-weight:700;color:${{bCol}}">${{p.pct}}%</span>
                  <div class="bm"><div class="bm-f" style="width:${{Math.min(p.pct,100)}}%;background:${{bCol}}"></div></div></div></td>
                <td><div class="bar-cell"><span style="min-width:34px;font-weight:700;color:${{cCol}}">${{p.comp_pct}}%</span>
                  <div class="bm"><div class="bm-f" style="width:${{p.comp_pct}}%;background:${{cCol}}"></div></div></div></td>
                <td><span style="background:#1e3a5f;color:#7eb3e8;border-radius:8px;padding:1px 8px;font-size:10px">👤 ${{p.assigned}}</span></td>
                <td>${{p.unassigned>0
                  ?`<span style="color:${{uaPct>50?'#f43f5e':'#f97316'}};font-weight:700">${{p.unassigned}}</span><span style="color:#64748b;font-size:9px"> (${{uaPct}}%)</span>`
                  :'<span style="color:#10b981;font-size:10px">✓ All</span>'}}</td>
              </tr>`;
            }}).join('')}}
          </tbody>
        </table>
      </div>
    </div>`;
  destroyChart('budget');
  charts['budget']=new Chart(document.getElementById('budgetChart'),{{
    type:'bar',
    data:{{
      labels:PROJ_BUDGET.map(p=>p.project.length>26?p.project.slice(0,24)+'…':p.project),
      datasets:[
        {{label:'Budget', data:PROJ_BUDGET.map(p=>p.budget),backgroundColor:'#a855f733',borderColor:'#a855f7',borderWidth:1,borderRadius:3}},
        {{label:'Spent',  data:PROJ_BUDGET.map(p=>p.spent), backgroundColor:PROJ_BUDGET.map(p=>p.spent>p.budget?'#f43f5e99':'#10b98199'),borderRadius:3}},
      ]
    }},
    options:{{
      indexAxis:'y',responsive:true,maintainAspectRatio:false,
      plugins:{{legend:{{labels:{{color:'#94a3b8',font:{{size:10}}}}}},
                tooltip:{{backgroundColor:'#0f1117',borderColor:'#2a2d3a',borderWidth:1,titleColor:'#f8fafc',bodyColor:'#e2e8f0',
                          callbacks:{{label:ctx=>`${{ctx.dataset.label}}: ${{ctx.parsed.x.toFixed(0)}}h`}}}}}},
      scales:{{x:{{ticks:{{color:'#64748b',font:{{size:10}},callback:v=>v+'h'}},grid:{{color:'#1e2436'}}}},
               y:{{ticks:{{color:'#94a3b8',font:{{size:9}}}},grid:{{display:false}}}}}}
    }}
  }});
  destroyChart('comp');
  charts['comp']=new Chart(document.getElementById('compChart'),{{
    type:'bar',
    data:{{
      labels:PROJ_BUDGET.map(p=>p.project.length>26?p.project.slice(0,24)+'…':p.project),
      datasets:[{{
        label:'Completion %',
        data:PROJ_BUDGET.map(p=>p.comp_pct),
        backgroundColor:PROJ_BUDGET.map(p=>p.comp_pct>=80?'#10b98199':p.comp_pct>=40?'#f9731699':'#3b82f699'),
        borderRadius:3
      }}]
    }},
    options:{{
      indexAxis:'y',responsive:true,maintainAspectRatio:false,
      plugins:{{legend:{{display:false}},
                tooltip:{{backgroundColor:'#0f1117',borderColor:'#2a2d3a',borderWidth:1,titleColor:'#f8fafc',bodyColor:'#e2e8f0',
                          callbacks:{{label:ctx=>`${{ctx.parsed.x.toFixed(1)}}% complete`}}}}}},
      scales:{{x:{{ticks:{{color:'#64748b',font:{{size:10}},callback:v=>v+'%'}},grid:{{color:'#1e2436'}},max:100}},
               y:{{ticks:{{color:'#94a3b8',font:{{size:9}}}},grid:{{display:false}}}}}}
    }}
  }});
}}
/* ── TEAM LOAD ── */
function renderTeam(){{
  const c=document.getElementById('content');
  const users=[...new Set(USER_PROJ.map(r=>r.user))];
  const byUser={{}};
  USER_PROJ.forEach(r=>{{(byUser[r.user]=byUser[r.user]||[]).push(r);}});
  const userTotals=users.map(u=>{{
    const rows=byUser[u];
    const bud=rows.reduce((s,r)=>s+r.budget,0);
    const spnt=rows.reduce((s,r)=>s+r.spent,0);
    const tasks=rows.reduce((s,r)=>s+r.tasks,0);
    const done=rows.reduce((s,r)=>s+r.done,0);
    return{{user:u,budget:bud,spent:spnt,tasks,done,
            pct:bud>0?Math.round(spnt/bud*100):0,
            comp:tasks>0?Math.round(done/tasks*100):0,projects:rows.length}};
  }}).sort((a,b)=>b.budget-a.budget);
  const totalUsers=userTotals.length;
  const totalBudget=userTotals.reduce((s,u)=>s+u.budget,0);
  const totalSpent=userTotals.reduce((s,u)=>s+u.spent,0);
  const highLoad=userTotals.filter(u=>u.pct>=80).length;
  const avgPct=totalUsers?Math.round(userTotals.reduce((s,u)=>s+u.pct,0)/totalUsers):0;
  const insMsg=highLoad>0
    ?`<b>${{highLoad}}</b> of <b>${{totalUsers}}</b> team members at ≥80% spend rate - Team assigned <b>${{fmtH(totalBudget)}}</b>, spent <b>${{fmtH(totalSpent)}}</b>`
    :`<b>${{totalUsers}}</b> active team members - Average spend rate <b>${{avgPct}}%</b> - Total assigned <b>${{fmtH(totalBudget)}}</b>`;
  const chartH=Math.max(200,userTotals.length*32);
  c.innerHTML=`
    ${{insight(insMsg,highLoad>0?'#f97316':'#10b981')}}
    <div class="kpi-grid" style="grid-template-columns:repeat(4,1fr);margin-bottom:16px">
      ${{[
        {{l:'Team Members',      v:totalUsers,      s:'with assigned tasks',      col:'#3b82f6'}},
        {{l:'Total Assigned Hrs',v:fmtH(totalBudget),s:'across all projects',     col:'#a855f7'}},
        {{l:'Total Spent Hrs',   v:fmtH(totalSpent), s:'actual hours logged',     col:'#10b981'}},
        {{l:'High Load (≥80%)',  v:highLoad,         s:'members at high spend rate',col:'#f97316'}},
      ].map(k=>`<div class="kpi" style="border-top:3px solid ${{k.col}}">
        <div class="kpi-lbl">${{k.l}}</div>
        <div class="kpi-val" style="color:${{k.col}}">${{k.v}}</div>
        <div class="kpi-sub">${{k.s}}</div>
      </div>`).join('')}}
    </div>
    <div class="card one-col">
      <div class="card-ttl">👥 Team Detail
        <span style="font-size:9px;font-weight:400;color:#64748b;margin-left:8px">Click a row to expand project breakdown</span>
      </div>
      <div style="overflow:auto;max-height:420px">
        <table class="mo-tbl">
          <thead><tr>
            <th>User / Project</th><th>Assigned Hrs</th>
            <th>Spent Hrs</th><th>Spend Rate</th><th>Tasks</th><th>Completion</th>
          </tr></thead>
          <tbody id="upBody"></tbody>
        </table>
      </div>
    </div>`;
  const tbody=document.getElementById('upBody');
  const expanded={{}};
  function colr(pct){{return pct>100?'#f43f5e':pct>=80?'#10b981':pct>=50?'#f97316':'#3b82f6';}}
  function cColr(pct){{return pct>=80?'#10b981':pct>=40?'#f97316':'#3b82f6';}}
  function buildRows(){{
    let html='';
    userTotals.forEach(ut=>{{
      const isOpen=!!expanded[ut.user];
      const uc_=colr(ut.pct); const cc=cColr(ut.comp);
      html+=`<tr style="cursor:pointer;background:#1e2d4a" onclick="toggleUser('${{ut.user.replace(/'/g,"\\'")}}')">
        <td style="font-weight:700;color:#93c5fd;padding-left:10px">
          <span style="margin-right:6px;font-size:9px;opacity:.7">${{isOpen?'▼':'▶'}}</span>👤 ${{ut.user}}
          <span style="background:rgba(255,255,255,.1);border-radius:8px;padding:1px 6px;font-size:9px;margin-left:6px;color:#7eb3e8">${{ut.projects}} proj</span>
        </td>
        <td style="color:#a855f7;font-weight:700">${{fmtH(ut.budget)}}</td>
        <td style="color:${{uc_}};font-weight:700">${{fmtH(ut.spent)}}</td>
        <td><div class="bar-cell"><span style="min-width:34px;font-weight:700;color:${{uc_}}">${{ut.pct}}%</span>
          <div class="bm"><div class="bm-f" style="width:${{Math.min(ut.pct,100)}}%;background:${{uc_}}"></div></div></div></td>
        <td style="color:#94a3b8">${{ut.done}}/${{ut.tasks}}</td>
        <td><div class="bar-cell"><span style="min-width:34px;font-weight:700;color:${{cc}}">${{ut.comp}}%</span>
          <div class="bm"><div class="bm-f" style="width:${{ut.comp}}%;background:${{cc}}"></div></div></div></td>
      </tr>`;
      if(isOpen){{
        byUser[ut.user].forEach(r=>{{
          const rc=colr(r.pct); const rComp=r.tasks>0?Math.round(r.done/r.tasks*100):0;
          html+=`<tr style="background:#0f1520">
            <td style="padding-left:36px;color:#cbd5e1;font-size:10px;white-space:normal;word-break:break-word;max-width:200px">↳ ${{r.project}}</td>
            <td style="color:#a855f7">${{fmtH(r.budget)}}</td>
            <td style="color:${{rc}}">${{fmtH(r.spent)}}</td>
            <td><div class="bar-cell"><span style="min-width:34px;font-weight:600;color:${{rc}}">${{r.pct}}%</span>
              <div class="bm"><div class="bm-f" style="width:${{Math.min(r.pct,100)}}%;background:${{rc}}"></div></div></div></td>
            <td style="color:#94a3b8">${{r.done}}/${{r.tasks}}</td>
            <td><div class="bar-cell"><span style="min-width:34px;font-weight:600;color:${{cColr(rComp)}}">${{rComp}}%</span>
              <div class="bm"><div class="bm-f" style="width:${{rComp}}%;background:${{cColr(rComp)}}"></div></div></div></td>
          </tr>`;
        }});
      }}
    }});
    tbody.innerHTML=html;
  }}
  window.toggleUser=function(u){{expanded[u]=!expanded[u];buildRows();}};
  buildRows();
}}
/* ── AT RISK ── */
function renderRisk(){{
  const c=document.getElementById('content');
  const today=new Date();
  function fmtD(s){{if(!s)return'—';return new Date(s+'T00:00:00').toLocaleDateString('en-GB',{{day:'2-digit',month:'short',year:'numeric'}});}}
  function daysLate(s){{if(!s)return null;const d=Math.floor((today-new Date(s+'T00:00:00'))/86400000);return d>0?d:null;}}
  const projects=[...new Set(OVERDUE.map(r=>r.project))];
  const byProj={{}};
  OVERDUE.forEach(r=>{{(byProj[r.project]=byProj[r.project]||[]).push(r);}});
  const totalTasks =OVERDUE.length;
  const totalBudget=OVERDUE.reduce((s,r)=>s+r.budget,0);
  const unassigned =OVERDUE.filter(r=>!r.user).length;
  const lateOnly   =OVERDUE.filter(r=>r.st==='late').length;
  const started    =OVERDUE.filter(r=>r.st==='overdue').length;
  /* sort projects by overdue count desc for chart */
  const projStats=projects.map(p=>{{
    const rows=byProj[p];
    return{{proj:p,count:rows.length,budget:rows.reduce((s,r)=>s+r.budget,0),
            late:rows.filter(r=>r.st==='late').length,
            started:rows.filter(r=>r.st==='overdue').length}};
  }}).sort((a,b)=>b.count-a.count);
  const insMsg=totalTasks===0
    ?'🎉 No overdue tasks — all projects are on schedule!'
    :`<b style="color:#f43f5e">${{totalTasks}}</b> tasks overdue across <b>${{projects.length}}</b> projects - <b>${{fmtH(totalBudget)}}</b> of budget at risk - <b>${{unassigned}}</b> unassigned overdue tasks need immediate owner`;
  const chartH=Math.max(180,projStats.length*32);
  c.innerHTML=`
    ${{insight(insMsg,'#f43f5e')}}
    <div class="kpi-grid" style="grid-template-columns:repeat(4,1fr);margin-bottom:16px">
      ${{[
        {{l:'Overdue Tasks',      v:totalTasks,         s:'need immediate action',      col:'#f43f5e'}},
        {{l:'Budget at Risk',     v:fmtH(totalBudget),  s:'hours planned but stalled',  col:'#f97316'}},
        {{l:'Not Started Late',   v:lateOnly,           s:'past start date, not begun', col:'#eab308'}},
        {{l:'No Owner Assigned',  v:unassigned,         s:'unassigned overdue tasks',   col:'#a855f7'}},
      ].map(k=>`<div class="kpi" style="border-top:3px solid ${{k.col}}">
        <div class="kpi-lbl">${{k.l}}</div>
        <div class="kpi-val" style="color:${{k.col}}">${{k.v}}</div>
        <div class="kpi-sub">${{k.s}}</div>
      </div>`).join('')}}
    </div>
    <div class="card one-col">
      <div class="card-ttl">⚠️ Overdue Task Detail
        <span style="font-size:9px;font-weight:400;color:#64748b;margin-left:8px">
          Click project to expand - <span style="color:#eab308">■</span> Not Started &nbsp;<span style="color:#f43f5e">■</span> In Progress Overdue</span>
      </div>
      <div style="overflow:auto;max-height:500px">
        <table class="mo-tbl" id="ovTable">
          <thead><tr>
            <th style="min-width:180px">Project / Task</th><th>Status</th><th>Department</th>
            <th>Owner</th><th>Budget Hrs</th><th>Plan Start</th><th>Plan End</th><th>Days Late</th>
          </tr></thead>
          <tbody id="ovBody"></tbody>
        </table>
      </div>
    </div>`;
  const tbody=document.getElementById('ovBody');
  const expanded={{}};
  function buildRows(){{
    let html='';
    projStats.forEach(({{proj}})=>{{
      const rows=byProj[proj];
      const isOpen=!!expanded[proj];
      const ps=projStats.find(p=>p.proj===proj);
      html+=`<tr style="cursor:pointer;background:#1e2d4a" onclick="toggleOvProj('${{proj.replace(/'/g,"\\'")}}')">
        <td colspan="8" style="font-weight:700;color:#f1f5f9;padding:8px 12px">
          <span style="margin-right:6px;font-size:9px;opacity:.7">${{isOpen?'▼':'▶'}}</span>${{proj}}
          <span style="margin-left:8px;background:#fee2e2;color:#991b1b;border-radius:8px;padding:1px 7px;font-size:9px;font-weight:700">${{rows.length}} overdue</span>
          ${{ps.late?`<span style="margin-left:4px;background:#fef9c3;color:#854d0e;border-radius:8px;padding:1px 7px;font-size:9px">${{ps.late}} not started</span>`:''}};
          ${{ps.started?`<span style="margin-left:4px;background:#fee2e2;color:#991b1b;border-radius:8px;padding:1px 7px;font-size:9px">${{ps.started}} in progress</span>`:''}};
          <span style="margin-left:8px;color:#f97316;font-size:10px;font-weight:600">${{fmtH(ps.budget)}}</span>
        </td>
      </tr>`;
      if(isOpen){{
        rows.forEach(r=>{{
          const isLate=r.st==='late';
          const dl=daysLate(r.pe)||(isLate?daysLate(r.ps):null);
          const stCol=isLate?'#eab308':'#f43f5e';
          html+=`<tr style="background:#0f1520;border-left:3px solid ${{stCol}}">
            <td style="padding-left:28px;color:#e2e8f0;font-size:10px;white-space:normal;word-break:break-word;max-width:220px">↳ ${{r.task}}</td>
            <td><span style="background:${{isLate?'#fef9c3':'#fee2e2'}};color:${{isLate?'#854d0e':'#991b1b'}};
                       border-radius:8px;padding:2px 8px;font-size:9px;font-weight:700;white-space:nowrap">
              ${{isLate?'Not Started':'Overdue'}}</span></td>
            <td style="color:#64748b;font-size:10px">${{r.dept}}</td>
            <td>${{r.user
              ?`<span style="background:#eff6ff;color:#1d4ed8;border-radius:8px;padding:1px 7px;font-size:9px">👤 ${{r.user}}</span>`
              :'<span style="background:#fff7ed;color:#c2410c;border-radius:8px;padding:1px 7px;font-size:9px;font-weight:600">Not Assigned</span>'}}</td>
            <td style="color:#f97316;font-weight:600">${{fmtH(r.budget)}}</td>
            <td style="color:#94a3b8;font-size:10px">${{fmtD(r.ps)}}</td>
            <td style="color:#f43f5e;font-size:10px">${{fmtD(r.pe)}}</td>
            <td style="font-weight:700;color:${{dl>30?'#f43f5e':dl>7?'#f97316':'#eab308'}}">${{dl?dl+'d':'—'}}</td>
          </tr>`;
        }});
      }}
    }});
    tbody.innerHTML=html;
  }}
  window.toggleOvProj=function(p){{expanded[p]=!expanded[p];buildRows();}};
  buildRows();
}}
/* ── LAST WEEK PLANNING ── */
function renderWeeklyPlan(){{
  const c=document.getElementById('content');
  if(!WEEKLY_PLAN.length){{
    c.innerHTML=`<div style="padding:40px;text-align:center;color:#64748b;font-size:13px">
      No planning data found for last week (${{WEEK_LABEL}}).</div>`;
    return;
  }}
  const PRIO_COL={{'High':'#f43f5e','Medium':'#f97316','Low':'#3b82f6'}};
  /* summary numbers */
  const totalPlanned=WEEKLY_PLAN.reduce((s,r)=>s+Object.values(r.hours).reduce((a,b)=>a+b,0),0);
  const totalUsers  =[...new Set(WEEKLY_PLAN.map(r=>r.user))].length;
  const totalProjs  =[...new Set(WEEKLY_PLAN.map(r=>r.project))].length;
  const totalRows   =WEEKLY_PLAN.length;
  /* build table HTML */
  const NCOLS=WEEK_DATES.length; /* 7 */
  const colspan=NCOLS+4; /* user | project | subtask | 7 days | total | status */
  /* group: user → project → rows */
  const userOrder=[...new Set(WEEKLY_PLAN.map(r=>r.user))];
  let tBody='';
  userOrder.forEach(user=>{{
    const uRows=WEEKLY_PLAN.filter(r=>r.user===user);
    const uTotal=uRows.reduce((s,r)=>s+Object.values(r.hours).reduce((a,b)=>a+b,0),0);
    const uProjs=[...new Set(uRows.map(r=>r.project))].length;
    /* user header row */
    tBody+=`<tr style="background:#1e2d4a">
      <td colspan="${{colspan}}" style="font-weight:700;color:#93c5fd;padding:8px 12px;font-size:11px">
        👤 ${{user}}
        <span style="margin-left:8px;background:rgba(255,255,255,.1);border-radius:8px;padding:1px 6px;font-size:9px;color:#7eb3e8">${{uRows.length}} subtasks - ${{uProjs}} projects</span>
        <span style="margin-left:10px;color:#a855f7;font-size:10px;font-weight:700">${{uTotal.toFixed(1)}}h total</span>
      </td>
    </tr>`;
    /* group by project */
    const projOrder=[...new Set(uRows.map(r=>r.project))];
    projOrder.forEach(proj=>{{
      const pRows=uRows.filter(r=>r.project===proj);
      const pTotal=pRows.reduce((s,r)=>s+Object.values(r.hours).reduce((a,b)=>a+b,0),0);
      /* project sub-header */
      tBody+=`<tr style="background:#0f1828">
        <td colspan="${{colspan}}" style="padding:5px 12px 5px 28px;font-weight:600;color:#bdd8ff;font-size:10px">
          📁 ${{proj}}
          <span style="margin-left:8px;color:#a855f7;font-size:9px">${{pTotal.toFixed(1)}}h</span>
        </td>
      </tr>`;
      /* subtask rows */
      pRows.forEach(r=>{{
        const rowTotal=Object.values(r.hours).reduce((a,b)=>a+b,0);
        const pCol=PRIO_COL[r.priority]||'#64748b';
        const dayCells=WEEK_DATES.map(d=>{{
          const h=r.hours[d]||0;
          if(!h)return`<td style="text-align:center;color:#2a3447;font-size:10px">—</td>`;
          const bg=h>=4?'#1e3a5f':h>=2?'#1a3352':'#152a42';
          return`<td style="text-align:center;font-weight:700;color:#7eb3e8;font-size:10px;background:${{bg}}">${{h.toFixed(1)}}h</td>`;
        }}).join('');
        tBody+=`<tr style="background:#0f1520;border-left:3px solid ${{pCol}}">
          <td style="padding-left:44px;color:#e2e8f0;font-size:10px;white-space:normal;word-break:break-word;max-width:220px">
            ${{r.subtask}}
          </td>
          <td style="white-space:nowrap;padding:0 8px">
            <span style="background:${{pCol}}22;color:${{pCol}};border-radius:8px;padding:1px 6px;font-size:9px;font-weight:700">${{r.priority}}</span>
          </td>
          ${{dayCells}}
          <td style="text-align:center;font-weight:700;color:#a855f7;font-size:10px">${{rowTotal.toFixed(1)}}h</td>
          <td style="white-space:nowrap;padding:0 8px">
            <span style="background:#1e2436;color:#94a3b8;border-radius:8px;padding:1px 7px;font-size:9px">${{r.status}}</span>
          </td>
        </tr>`;
      }});
    }});
  }});
  /* day-total footer row */
  const dayTotals=WEEK_DATES.map(d=>WEEKLY_PLAN.reduce((s,r)=>s+(r.hours[d]||0),0));
  const footCells=dayTotals.map(t=>
    `<td style="text-align:center;font-weight:700;color:#f1f5f9;font-size:10px;background:#1e2d4a;border-top:1px solid #2a3d5a">${{t>0?t.toFixed(1)+'h':''}}</td>`
  ).join('');
  c.innerHTML=`
    ${{insight(`Week: <b>${{WEEK_LABEL}}</b> &nbsp;-&nbsp; <b>${{totalUsers}}</b> team members &nbsp;-&nbsp; <b>${{totalRows}}</b> subtasks &nbsp;-&nbsp; <b>${{totalProjs}}</b> projects &nbsp;-&nbsp; <b>${{totalPlanned.toFixed(1)}}h</b> total planned`,'#3b82f6')}}
    <div class="card one-col">
      <div class="card-ttl">📅 Last Week Planning — ${{WEEK_LABEL}}</div>
      <div style="overflow:auto;max-height:680px">
        <table class="mo-tbl" style="table-layout:auto;min-width:900px">
          <thead>
            <tr>
              <th style="min-width:200px;text-align:left">Subtask</th>
              <th style="min-width:70px">Priority</th>
              ${{WEEK_LABELS.map(l=>`<th style="text-align:center;min-width:70px;white-space:nowrap">${{l}}</th>`).join('')}}
              <th style="text-align:center;min-width:60px">Total</th>
              <th style="min-width:100px">Status</th>
            </tr>
          </thead>
          <tbody>
            ${{tBody}}
            <tr>
              <td colspan="2" style="font-weight:700;color:#7eb3e8;font-size:10px;background:#1e2d4a;border-top:1px solid #2a3d5a;padding:6px 12px">Daily Total</td>
              ${{footCells}}
              <td style="text-align:center;font-weight:700;color:#a855f7;font-size:10px;background:#1e2d4a;border-top:1px solid #2a3d5a">${{totalPlanned.toFixed(1)}}h</td>
              <td style="background:#1e2d4a;border-top:1px solid #2a3d5a"></td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>`;
}}
/* ── THIS MONTH PLANNING ── */
function renderMonthlyPlan(){{
  const c=document.getElementById('content');
  const DATA=_MP;
  const DATES=typeof MONTH_DATES!=='undefined'?MONTH_DATES:[];
  const LABELS=typeof MONTH_LABELS!=='undefined'?MONTH_LABELS:[];
  const LABEL=typeof MONTH_LABEL!=='undefined'?MONTH_LABEL:'';
  if(!DATA.length){{
    c.innerHTML=`<div style="padding:40px;text-align:center;color:#64748b;font-size:13px">
      No planning data found for this month (${{LABEL}}).</div>`;
    return;
  }}
  const PRIO_COL={{'High':'#f43f5e','Medium':'#f97316','Low':'#3b82f6'}};
  const totalPlanned=DATA.reduce((s,r)=>s+Object.values(r.hours).reduce((a,b)=>a+b,0),0);
  const totalUsers  =[...new Set(DATA.map(r=>r.user))].length;
  const totalProjs  =[...new Set(DATA.map(r=>r.project))].length;
  const totalRows   =DATA.length;
  const userOrder=[...new Set(DATA.map(r=>r.user))];
  let tBody='';
  userOrder.forEach(user=>{{
    const uRows=DATA.filter(r=>r.user===user);
    const uTotal=uRows.reduce((s,r)=>s+Object.values(r.hours).reduce((a,b)=>a+b,0),0);
    const uProjs=[...new Set(uRows.map(r=>r.project))].length;
    tBody+=`<tr style="background:#1e2d4a">
      <td colspan="${{DATES.length+4}}" style="font-weight:700;color:#93c5fd;padding:8px 12px;font-size:11px">
        👤 ${{user}}
        <span style="margin-left:8px;background:rgba(255,255,255,.1);border-radius:8px;padding:1px 6px;font-size:9px;color:#7eb3e8">${{uRows.length}} subtasks - ${{uProjs}} projects</span>
        <span style="margin-left:10px;color:#a855f7;font-size:10px;font-weight:700">${{uTotal.toFixed(1)}}h total</span>
      </td>
    </tr>`;
    const projOrder=[...new Set(uRows.map(r=>r.project))];
    projOrder.forEach(proj=>{{
      const pRows=uRows.filter(r=>r.project===proj);
      const pTotal=pRows.reduce((s,r)=>s+Object.values(r.hours).reduce((a,b)=>a+b,0),0);
      tBody+=`<tr style="background:#0f1828">
        <td colspan="${{DATES.length+4}}" style="padding:5px 12px 5px 28px;font-weight:600;color:#bdd8ff;font-size:10px">
          📁 ${{proj}}
          <span style="margin-left:8px;color:#a855f7;font-size:9px">${{pTotal.toFixed(1)}}h</span>
        </td>
      </tr>`;
      pRows.forEach(r=>{{
        const rowTotal=Object.values(r.hours).reduce((a,b)=>a+b,0);
        const pCol=PRIO_COL[r.priority]||'#64748b';
        const dayCells=DATES.map(d=>{{
          const h=r.hours[d]||0;
          if(!h)return`<td style="text-align:center;color:#2a3447;font-size:9px">-</td>`;
          const bg=h>=4?'#1e3a5f':h>=2?'#1a3352':'#152a42';
          return`<td style="text-align:center;font-weight:700;color:#7eb3e8;font-size:9px;background:${{bg}}">${{h.toFixed(1)}}</td>`;
        }}).join('');
        tBody+=`<tr style="background:#0f1520;border-left:3px solid ${{pCol}}">
          <td style="padding-left:44px;color:#e2e8f0;font-size:10px;white-space:normal;word-break:break-word;max-width:220px">${{r.subtask}}</td>
          <td style="white-space:nowrap;padding:0 8px">
            <span style="background:${{pCol}}22;color:${{pCol}};border-radius:8px;padding:1px 6px;font-size:9px;font-weight:700">${{r.priority}}</span>
          </td>
          ${{dayCells}}
          <td style="text-align:center;font-weight:700;color:#a855f7;font-size:9px">${{rowTotal.toFixed(1)}}h</td>
          <td style="white-space:nowrap;padding:0 8px">
            <span style="background:#1e2436;color:#94a3b8;border-radius:8px;padding:1px 7px;font-size:9px">${{r.status}}</span>
          </td>
        </tr>`;
      }});
    }});
  }});
  const dayTotals=DATES.map(d=>DATA.reduce((s,r)=>s+(r.hours[d]||0),0));
  const footCells=dayTotals.map(t=>
    `<td style="text-align:center;font-weight:700;color:#f1f5f9;font-size:9px;background:#1e2d4a;border-top:1px solid #2a3d5a">${{t>0?t.toFixed(1):''}}</td>`
  ).join('');
  c.innerHTML=`
    ${{insight(`Month: <b>${{LABEL}}</b> &nbsp;·&nbsp; <b>${{totalUsers}}</b> team members &nbsp;·&nbsp; <b>${{totalRows}}</b> subtasks &nbsp;·&nbsp; <b>${{totalProjs}}</b> projects &nbsp;·&nbsp; <b>${{totalPlanned.toFixed(1)}}h</b> total planned`,'#06b6d4')}}
    <div class="card one-col">
      <div class="card-ttl">📆 This Month Planning — ${{LABEL}}</div>
      <div style="overflow:auto;max-height:680px">
        <table class="mo-tbl" style="table-layout:auto;min-width:900px">
          <thead>
            <tr>
              <th style="min-width:200px;text-align:left">Subtask</th>
              <th style="min-width:70px">Priority</th>
              ${{LABELS.map((l,i)=>{{
                const isToday=(DATES[i]===new Date().toISOString().slice(0,10));
                return`<th style="text-align:center;min-width:52px;white-space:nowrap;font-size:8px;${{isToday?'color:#3b82f6;font-weight:800;border-bottom:2px solid #3b82f6':''}} ">${{l}}</th>`;
              }}).join('')}}
              <th style="text-align:center;min-width:55px">Total</th>
              <th style="min-width:90px">Status</th>
            </tr>
          </thead>
          <tbody>
            ${{tBody}}
            <tr>
              <td colspan="2" style="font-weight:700;color:#7eb3e8;font-size:10px;background:#1e2d4a;border-top:1px solid #2a3d5a;padding:6px 12px">Daily Total</td>
              ${{footCells}}
              <td style="text-align:center;font-weight:700;color:#a855f7;font-size:9px;background:#1e2d4a;border-top:1px solid #2a3d5a">${{totalPlanned.toFixed(1)}}h</td>
              <td style="background:#1e2d4a;border-top:1px solid #2a3d5a"></td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>`;
}}
function renderContent(){{
  Object.keys(charts).forEach(id=>{{charts[id].destroy();delete charts[id];}});
  if(activeTab==='portfolio')   renderPortfolio();
  else if(activeTab==='team')   renderTeam();
  else if(activeTab==='risk')   renderRisk();
  else if(activeTab==='weekly') renderWeeklyPlan();
  else if(activeTab==='monthly')renderMonthlyPlan();
}}
renderContent();
</script>
</body></html>"""
    # Unescape template braces FIRST (only affects CAP_HTML, not the JSON data)
    # then inject _data_script which already has proper single-brace JSON
    CAP_HTML_FINAL = CAP_HTML.replace("{{", "{").replace("}}", "}").replace(
        "</head>", _data_script + "\n</head>"
    )

    components.html(CAP_HTML_FINAL, height=2400, scrolling=True)
  except Exception as _e:
    st.error(f"Capacity Utilization error: {_e}")
    import traceback
    st.code(traceback.format_exc())
