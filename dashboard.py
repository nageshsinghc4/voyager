"""
dashboard.py  —  Voyager | AI-Powered Trip Planner
Launch:  panel serve dashboard.py --show
"""
from __future__ import annotations

import hashlib as _hashlib
import html as _html
import json as _json
import os, sys, threading, traceback
import urllib.parse as _uparse
import urllib.request as _urllib_req
from datetime import date, timedelta

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import panel as pn
import param
from dotenv import load_dotenv
load_dotenv()

from trip_planner import plan_trip
from trip_planner.chat import ChatSession

# ── CSS ───────────────────────────────────────────────────────────────────────
CSS = """
*,*::before,*::after{box-sizing:border-box}
body{font-family:'Inter','Segoe UI',system-ui,sans-serif;background:#f1f5f9}

/* ── SIDEBAR (light theme) ─────────────────────────────────────────────── */
.sidebar-panel{
  background:#ffffff!important;
  border-right:1px solid #e2e8f0;
  padding:24px 18px 28px;
  min-height:100vh;
  box-shadow:2px 0 12px rgba(0,0,0,.05)
}
.sidebar-panel .bk-input-group label,.sidebar-panel label{
  color:#475569!important;font-size:11px!important;font-weight:700!important;
  text-transform:uppercase!important;letter-spacing:.6px!important
}
.sidebar-panel .bk-input{
  background:#f8fafc!important;border:1.5px solid #e2e8f0!important;
  color:#1e293b!important;border-radius:8px!important;font-size:14px!important
}
.sidebar-panel .bk-input:focus{
  border-color:#3aa7e8!important;box-shadow:0 0 0 3px rgba(58,167,232,.15)!important
}
.sidebar-panel .bk-btn-group .bk-btn{
  background:#f1f5f9!important;border:1.5px solid #e2e8f0!important;
  color:#475569!important;border-radius:7px!important;
  font-size:12px!important;font-weight:600!important;padding:6px 10px!important
}
.sidebar-panel .bk-btn-group .bk-btn.bk-active{
  background:#f0f8fe!important;border-color:#3aa7e8!important;color:#2b8bbf!important
}
.sidebar-panel .bk-checkbox-group label,.sidebar-panel .bk-checkboxgroup label{
  color:#374151!important;font-size:13px!important;font-weight:400!important;
  text-transform:none!important;letter-spacing:0!important
}

/* ── brand ─────────────────────────────────────────────────────────────── */
.brand-area{
  display:flex;align-items:center;gap:14px;
  margin-bottom:14px;padding:4px 0
}
.brand-gif{
  width:68px;height:68px;object-fit:contain;flex-shrink:0;
  filter:drop-shadow(0 4px 12px rgba(58,167,232,.28))
}
.brand-text{display:flex;flex-direction:column;gap:2px}
.brand-name{font-size:22px;font-weight:900;color:#1e293b;letter-spacing:-.6px;line-height:1.1}
.brand-tag{font-size:12px;color:#64748b;line-height:1.4;margin:0}

/* sidebar section dividers */
.sidebar-sect{
  font-size:10px;font-weight:700;color:#94a3b8;
  text-transform:uppercase;letter-spacing:.8px;
  margin:16px 0 6px;padding-bottom:5px;
  border-bottom:1px solid #f1f5f9
}

/* ── plan button ───────────────────────────────────────────────────────── */
.plan-btn button{
  background:linear-gradient(135deg,#3aa7e8,#2b8bbf)!important;
  color:#fff!important;border:none!important;border-radius:10px!important;
  font-size:15px!important;font-weight:700!important;padding:13px 0!important;
  width:100%!important;cursor:pointer!important;letter-spacing:.2px!important;
  transition:all .2s!important
}
.plan-btn button:hover{
  background:linear-gradient(135deg,#2b8bbf,#1e6e9e)!important;
  transform:translateY(-1px)!important;
  box-shadow:0 6px 18px rgba(58,167,232,.4)!important
}
.plan-btn button:disabled{
  background:#cbd5e1!important;transform:none!important;box-shadow:none!important
}

/* ── budget display ────────────────────────────────────────────────────── */
.budget-box{
  background:#f0f8fe;border:1px solid #9dd0ef;
  border-radius:10px;padding:10px 14px;
  display:flex;justify-content:space-between;align-items:center;margin-bottom:8px
}
.budget-box-lbl{font-size:11px;color:#64748b;text-transform:uppercase;
                 letter-spacing:.5px;font-weight:600}
.budget-box-val{font-size:24px;font-weight:800;color:#2b8bbf}

/* ── validation error ──────────────────────────────────────────────────── */
.val-err{
  background:#fef2f2;border:1px solid #fecaca;border-radius:8px;
  padding:8px 12px;font-size:13px;color:#dc2626;margin-bottom:8px
}

/* ── trip hero (compact + animated plane) ───────────────────────────────── */
.trip-hero{
  background:linear-gradient(135deg,#1e6e9e 0%,#2b8bbf 55%,#3aa7e8 100%);
  border-radius:16px;padding:14px 26px 13px;margin-bottom:20px;
  position:relative;overflow:hidden
}
.hero-bg-c1{
  position:absolute;top:-55px;right:-55px;
  width:180px;height:180px;background:rgba(255,255,255,.06);border-radius:50%;pointer-events:none
}
.hero-bg-c2{
  position:absolute;bottom:-35px;left:-35px;
  width:120px;height:120px;background:rgba(255,255,255,.04);border-radius:50%;pointer-events:none
}
.hero-route{
  display:flex;align-items:center;gap:10px;margin-bottom:8px;position:relative;z-index:1
}
.hero-city{flex-shrink:0;min-width:72px}
.hero-city.dst{text-align:right;min-width:90px}
.hero-city-lbl{
  font-size:9px;font-weight:700;color:rgba(255,255,255,.45);
  text-transform:uppercase;letter-spacing:1px;margin-bottom:1px
}
.hero-city-name{font-size:17px;font-weight:800;color:#fff;line-height:1.1;white-space:nowrap}
.hero-city-name.big{font-size:22px}
.hero-track{flex:1;position:relative;height:26px;display:flex;align-items:center}
.hero-track-line{
  width:100%;height:1.5px;background:rgba(255,255,255,.2);border-radius:1px;position:relative
}
.hero-track-line::before,.hero-track-line::after{
  content:'';position:absolute;top:-3px;
  width:7px;height:7px;border-radius:50%;background:rgba(255,255,255,.35)
}
.hero-track-line::before{left:0}
.hero-track-line::after{right:0}
.hero-plane-anim{
  position:absolute;top:50%;left:-4px;transform:translateY(-65%);
  font-size:26px;animation:plane-fly 5s ease-in-out infinite;
  color:#fff!important;
  filter:drop-shadow(0 2px 8px rgba(255,255,255,.5));white-space:nowrap
}
@keyframes plane-fly{
  0%  {left:-4px;opacity:0}
  6%  {opacity:1}
  92% {opacity:1}
  100%{left:calc(100% - 20px);opacity:0}
}
.hero-dates-badge{
  font-size:12px;color:rgba(255,255,255,.68);
  margin-bottom:8px;position:relative;z-index:1;display:block
}
.hero-pill{
  display:inline-flex;align-items:center;gap:5px;
  background:rgba(255,255,255,.11);border:1px solid rgba(255,255,255,.18);
  border-radius:999px;padding:4px 10px;font-size:11.5px;color:#d0ebf8;
  margin:0 5px 5px 0;position:relative;z-index:1
}

/* ── kpi cards ──────────────────────────────────────────────────────────── */
.kpi-row{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:20px}
.kpi-card{
  border-radius:18px;padding:16px 18px 14px;flex:1;min-width:120px;
  background:#fff;
  box-shadow:0 2px 12px rgba(0,0,0,.07),0 1px 3px rgba(0,0,0,.04);
  border:1px solid #f0f4f8;
  position:relative;overflow:hidden;
  transition:transform .15s,box-shadow .15s
}
.kpi-card:hover{transform:translateY(-2px);box-shadow:0 6px 20px rgba(0,0,0,.1)}
.kpi-card::after{
  content:'';position:absolute;top:-22px;right:-22px;
  width:78px;height:78px;border-radius:50%;
  background:var(--kc,#3aa7e8);opacity:.1;pointer-events:none
}
.kpi-badge{
  width:34px;height:34px;border-radius:10px;
  background:var(--kc,#3aa7e8);
  display:flex;align-items:center;justify-content:center;margin-bottom:11px
}
.kpi-v{font-size:22px;font-weight:800;color:#0f172a;line-height:1.1}
.kpi-l{
  font-size:10px;font-weight:700;color:var(--kc,#3aa7e8);
  text-transform:uppercase;letter-spacing:.8px;margin-top:5px
}

/* ── section cards ──────────────────────────────────────────────────────── */
.sec-card{
  background:#fff;border-radius:14px;padding:20px 22px;margin-bottom:16px;
  box-shadow:0 1px 3px rgba(0,0,0,.06),0 4px 12px rgba(0,0,0,.04);
  border:1px solid #f1f5f9
}
.sec-title{
  font-size:15px;font-weight:700;color:#1e293b;
  display:flex;align-items:center;gap:8px;
  margin-bottom:16px;padding-bottom:10px;border-bottom:2px solid #e2e8f0
}
.cnt-pill{
  background:#f1f5f9;color:#64748b;font-size:11px;
  font-weight:600;padding:2px 8px;border-radius:999px
}

/* ── weather ────────────────────────────────────────────────────────────── */
.wx-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(120px,1fr));gap:10px;margin-top:12px}
.wx-day{
  background:linear-gradient(135deg,#f0f8fe,#f0fdf4);border-radius:12px;
  padding:14px;text-align:center;border:1px solid #e2e8f0
}
.wx-icon{font-size:26px;margin-bottom:6px}
.wx-lbl{font-size:10px;color:#64748b;font-weight:700;text-transform:uppercase;letter-spacing:.5px}
.wx-cond{font-size:11px;color:#475569;margin:3px 0}
.wx-temp{font-size:13px;font-weight:700;color:#1e293b}

/* ── hotel cards ────────────────────────────────────────────────────────── */
.hotel-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:14px}
.hotel-card{
  border-radius:12px;overflow:hidden;
  border:1px solid #f1f5f9;background:#fff;
  box-shadow:0 1px 3px rgba(0,0,0,.05);display:flex;flex-direction:column
}
.hotel-card.bv{border:2px solid #22c55e}
.hotel-card-body{padding:14px 16px;flex:1;display:flex;flex-direction:column}
.h-name{font-size:14px;font-weight:700;color:#1e293b}
.h-price{font-size:22px;font-weight:800;color:#3aa7e8;display:inline}
.h-price span{font-size:13px;font-weight:400;color:#64748b}
.chip{
  display:inline-block;background:#f8fafc;border:1px solid #e2e8f0;
  color:#475569;border-radius:6px;padding:1px 7px;font-size:11px;margin:2px 2px 2px 0
}
.rbar{background:#e2e8f0;border-radius:999px;height:5px;overflow:hidden;margin-top:8px}
.rbar-fill{height:5px;border-radius:999px;background:linear-gradient(90deg,#3aa7e8,#2b8bbf)}

/* ── activity cards ─────────────────────────────────────────────────────── */
.act-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(270px,1fr));gap:12px}
.act-card{
  background:#fff;border-radius:12px;padding:16px;
  box-shadow:0 1px 3px rgba(0,0,0,.05);border:1px solid #f1f5f9
}
.act-name{font-size:13px;font-weight:700;color:#1e293b;line-height:1.3;margin-bottom:6px}
.act-meta{font-size:12px;color:#64748b}
.badge{display:inline-block;padding:3px 9px;border-radius:999px;font-size:11px;font-weight:600}

/* ── event cards ────────────────────────────────────────────────────────── */
.evt-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:14px}
.evt-card{
  background:#fff;border-radius:14px;padding:18px;
  box-shadow:0 1px 4px rgba(0,0,0,.06),0 4px 14px rgba(0,0,0,.04);
  border:1px solid #f1f5f9;position:relative;overflow:hidden
}
.evt-card::before{
  content:'';position:absolute;top:0;left:0;right:0;height:3px;
  background:linear-gradient(90deg,#3aa7e8,#2b8bbf)
}
.evt-name{font-size:14px;font-weight:700;color:#1e293b;line-height:1.4;margin-bottom:6px}
.evt-venue{font-size:12px;color:#64748b;margin-bottom:10px}
.evt-pills{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:10px}
.evt-pill{
  display:inline-flex;align-items:center;gap:4px;
  background:#f8fafc;border:1px solid #e2e8f0;
  border-radius:999px;padding:3px 10px;font-size:11px;color:#475569
}
.evt-pill.price{background:#f0fdf4;border-color:#bbf7d0;color:#166534}
.evt-desc{font-size:12px;color:#94a3b8;line-height:1.4;margin-bottom:12px}
.evt-hotels{border-top:1px dashed #e2e8f0;padding-top:10px;margin-top:4px}
.evt-hotel-lbl{
  font-size:10px;font-weight:700;color:#3aa7e8;
  text-transform:uppercase;letter-spacing:.5px;margin-bottom:6px
}
.evt-hotel-chip{
  display:inline-flex;align-items:center;gap:4px;
  background:#f0f8fe;border:1px solid #9dd0ef;
  border-radius:6px;padding:2px 8px;font-size:12px;
  color:#1e6e9e;margin:2px 3px 2px 0;font-weight:500
}
.evt-link,.book-link{
  display:inline-flex;align-items:center;gap:5px;margin-top:10px;padding:6px 14px;
  background:linear-gradient(135deg,#3aa7e8,#2b8bbf);color:#fff!important;
  border-radius:8px;font-size:12px;font-weight:700;text-decoration:none!important;
  transition:opacity .15s,transform .15s
}
.evt-link:hover,.book-link:hover{opacity:.88;transform:translateY(-1px)}
.evt-empty{
  text-align:center;padding:48px 24px;
  display:flex;flex-direction:column;align-items:center;gap:10px
}
.evt-empty-icon{font-size:48px}
.evt-empty-title{font-size:16px;font-weight:700;color:#1e293b}
.evt-empty-sub{font-size:13px;color:#94a3b8;max-width:300px;line-height:1.5}

/* ── itinerary ──────────────────────────────────────────────────────────── */
.day-card{
  background:#fff;border-radius:14px;overflow:hidden;
  margin-bottom:14px;
  box-shadow:0 1px 3px rgba(0,0,0,.06),0 4px 12px rgba(0,0,0,.04);
  border:1px solid #f1f5f9
}
.day-hdr{
  background:linear-gradient(135deg,#1e6e9e,#2b8bbf);
  padding:14px 20px;display:flex;align-items:center;justify-content:space-between
}
.day-num{font-size:11px;font-weight:700;color:#bfe0f6;text-transform:uppercase;letter-spacing:.5px}
.day-dt{font-size:15px;font-weight:600;color:#fff}
.day-body{padding:18px 20px}
.ts{display:grid;grid-template-columns:80px 1fr;gap:10px;margin-bottom:12px;align-items:start}
.ts-lbl{text-align:center}
.ts-icon{font-size:18px}
.ts-name{font-size:9px;font-weight:700;text-transform:uppercase;letter-spacing:.5px;color:#94a3b8;margin-top:2px}
.ts-body{background:#f8fafc;border-radius:10px;padding:10px 13px;font-size:13px;color:#374151;line-height:1.5}
.dining-row{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-top:14px;padding-top:12px;border-top:1px dashed #e2e8f0}
.dining-item{background:#fff7ed;border-radius:8px;padding:8px 10px;font-size:12px;color:#92400e}
.dining-meal{font-size:9px;font-weight:700;text-transform:uppercase;letter-spacing:.5px;margin-bottom:2px}
.notes{
  background:#f0f8fe;border-left:3px solid #3aa7e8;
  border-radius:0 8px 8px 0;padding:8px 12px;
  margin-top:12px;font-size:12px;color:#1e6e9e;line-height:1.5
}

/* ── info tab ───────────────────────────────────────────────────────────── */
.tip-item{display:flex;gap:10px;padding:8px 0;border-bottom:1px solid #f8fafc;font-size:13px;color:#374151;line-height:1.5}
.tip-item:last-child{border-bottom:none}
.tip-dot{width:6px;height:6px;border-radius:50%;background:#3aa7e8;flex-shrink:0;margin-top:6px}
.pack-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:0 16px}
.pack-cat{
  grid-column:1/-1;
  font-size:11px;font-weight:700;color:#3aa7e8;text-transform:uppercase;
  letter-spacing:.5px;margin:14px 0 4px;padding-bottom:4px;
  border-bottom:1px solid #e2e8f0
}
.pack-cat:first-child{margin-top:0}
.pack-item{display:flex;align-items:center;gap:8px;font-size:13px;color:#374151;padding:4px 0;border-bottom:1px solid #f8fafc}
.pack-cb{width:14px;height:14px;border-radius:4px;border:2px solid #cbd5e1;background:#fff;flex-shrink:0}
/* ── budget bars ────────────────────────────────────────────────────────── */
.bbar{display:flex;align-items:center;gap:10px;margin-bottom:10px}
.bbar-lbl{font-size:13px;color:#374151;width:110px;flex-shrink:0}
.bbar-track{flex:1;background:#f1f5f9;border-radius:999px;height:10px;overflow:hidden}
.bbar-fill{height:10px;border-radius:999px}
.bbar-amt{font-size:13px;font-weight:700;color:#1e293b;width:80px;text-align:right;flex-shrink:0}

/* ── tabs ───────────────────────────────────────────────────────────────── */
.bk-tabs-header{border-bottom:2px solid #e2e8f0!important}
.bk-tabs-header .bk-tab{
  font-weight:600;font-size:13px;padding:10px 16px!important;
  color:#64748b!important;border:none!important;background:transparent!important
}
.bk-tabs-header .bk-tab.bk-active{
  color:#3aa7e8!important;border-bottom:3px solid #3aa7e8!important;margin-bottom:-2px!important
}

/* ── loading ────────────────────────────────────────────────────────────── */
.load-wrap{
  display:flex;flex-direction:column;align-items:center;
  justify-content:center;text-align:center;padding:80px 20px;gap:12px
}
.load-title{font-size:22px;font-weight:700;color:#1e293b}
.load-sub{font-size:14px;color:#64748b;max-width:400px;line-height:1.6}

/* ── homepage / welcome ─────────────────────────────────────────────────── */
.welcome-wrap{
  display:flex;flex-direction:column;align-items:center;
  justify-content:center;text-align:center;
  padding:60px 20px;gap:16px;
  min-height:calc(100vh - 40px);
  position:relative;overflow:hidden;
  background:
    radial-gradient(ellipse 80% 55% at 82% 16%, rgba(58,167,232,.12) 0%,transparent 58%),
    radial-gradient(ellipse 60% 70% at 10% 90%, rgba(43,139,191,.09) 0%,transparent 52%),
    radial-gradient(ellipse 45% 35% at 48% 52%, rgba(224,244,253,.9) 0%,transparent 65%),
    #f4f7fb
}
/* dot-grid overlay */
.welcome-wrap::before{
  content:'';position:absolute;inset:0;
  background-image:radial-gradient(rgba(58,167,232,.16) 1.3px,transparent 1.3px);
  background-size:30px 30px;pointer-events:none
}
.welcome-title{font-size:34px;font-weight:800;color:#0f172a;letter-spacing:-.7px;line-height:1.2}
.welcome-sub{font-size:15px;color:#475569;max-width:500px;line-height:1.75}
/* ── animated agent cards ───────────────────────────────────────── */
.agent-cards{display:flex;gap:14px;flex-wrap:wrap;justify-content:center;margin-top:26px}
.agent-card{
  width:100px;background:#fff;border-radius:18px;padding:16px 8px 12px;
  box-shadow:0 3px 16px rgba(58,167,232,.15),0 1px 4px rgba(0,0,0,.05);
  border:1.5px solid #d9eef9;
  display:flex;flex-direction:column;align-items:center;gap:6px;
  animation:ac-float 2.4s ease-in-out infinite;animation-delay:var(--d,0s)
}
@keyframes ac-float{
  0%,100%{transform:translateY(0);box-shadow:0 3px 16px rgba(58,167,232,.15)}
  50%{transform:translateY(-7px);box-shadow:0 12px 30px rgba(58,167,232,.32)}
}
.ac-icon{
  width:54px;height:54px;border-radius:14px;
  background:linear-gradient(140deg,#eaf6fd 0%,#c8e8f8 100%);
  display:flex;align-items:center;justify-content:center
}
.ac-label{font-size:11px;font-weight:700;color:#1e6e9e;letter-spacing:.4px;text-align:center}
.ac-status{font-size:10px;color:#94a3b8;letter-spacing:.2px}
.ac-bar{width:80%;height:3px;background:#e0f0fb;border-radius:99px;overflow:hidden;position:relative}
.ac-bar::after{
  content:'';position:absolute;top:0;left:-100%;width:100%;height:100%;
  background:linear-gradient(90deg,transparent,#3aa7e8,#9dd0ef,transparent);
  animation:ac-scan 1.8s ease-in-out infinite;animation-delay:var(--d,0s)
}
@keyframes ac-scan{0%{left:-100%}100%{left:200%}}
/* plane rocks side-to-side */
.ico-plane{transform-origin:50% 50%;animation:plane-rock 2s ease-in-out infinite}
@keyframes plane-rock{
  0%,100%{transform:rotate(-12deg) scale(1)}25%{transform:rotate(0deg) scale(1.06) translateY(-2px)}
  50%{transform:rotate(12deg) scale(1)}75%{transform:rotate(0deg) scale(1.06) translateY(2px)}
}
/* hotel windows blink in sequence */
.win-a{animation:win-blink 2.8s ease-in-out infinite}
.win-b{animation:win-blink 2.8s ease-in-out infinite;animation-delay:.45s}
.win-c{animation:win-blink 2.8s ease-in-out infinite;animation-delay:.9s}
.win-d{animation:win-blink 2.8s ease-in-out infinite;animation-delay:1.35s}
.win-e{animation:win-blink 2.8s ease-in-out infinite;animation-delay:1.8s}
.win-f{animation:win-blink 2.8s ease-in-out infinite;animation-delay:2.25s}
@keyframes win-blink{0%,100%{opacity:1;fill:#fff}45%,55%{opacity:.08;fill:#90cef0}}
/* compass needle spins */
.ico-needle{transform-origin:50% 50%;animation:needle-spin 3s linear infinite}
@keyframes needle-spin{0%{transform:rotate(0deg)}100%{transform:rotate(360deg)}}
/* radar sweeps */
.ico-radar{transform-origin:50% 50%;animation:radar-rot 2.5s linear infinite}
@keyframes radar-rot{0%{transform:rotate(0deg)}100%{transform:rotate(360deg)}}
/* calendar star pops */
.ico-star{transform-origin:50% 50%;animation:star-pop 1.4s ease-in-out infinite}
@keyframes star-pop{
  0%,100%{transform:scale(1) rotate(0deg);opacity:.75}
  50%{transform:scale(1.7) rotate(180deg);opacity:1}
}
.welcome-hint{
  display:inline-flex;align-items:center;gap:12px;
  background:rgba(255,255,255,.72);
  backdrop-filter:blur(14px);-webkit-backdrop-filter:blur(14px);
  border:1px solid rgba(58,167,232,.22);
  border-radius:999px;padding:11px 26px;
  font-size:13px;color:#475569;margin-top:8px;
  box-shadow:0 4px 22px rgba(58,167,232,.13),0 1px 4px rgba(0,0,0,.04)
}
.welcome-hint b{color:#3aa7e8;font-weight:700}
/* city-dot pulse on SVG */
@keyframes dot-pulse{
  0%,100%{opacity:.35;r:7}50%{opacity:.65;r:11}
}
.wbg-dot-outer{animation:dot-pulse 3s ease-in-out infinite}
.wbg-dot-outer:nth-child(2){animation-delay:.6s}
.wbg-dot-outer:nth-child(3){animation-delay:1.2s}
.wbg-dot-outer:nth-child(4){animation-delay:1.8s}
.wbg-dot-outer:nth-child(5){animation-delay:2.4s}

/* ── AI assistant panel ─────────────────────────────────────────────────── */
.asst-panel{
  background:#fff;border-radius:16px 16px 0 0;padding:0;
  box-shadow:0 -4px 30px rgba(0,0,0,.12);
  border:1px solid #e2e8f0;border-bottom:none;overflow:hidden
}

/* ── floating chat FAB ───────────────────────────────────────────────────── */
.fab-wrap{overflow:visible!important}
button.chat-float-btn,
button.bk-btn.chat-float-btn{
  width:64px!important;height:64px!important;
  border-radius:50%!important;
  background:linear-gradient(145deg,#4ec4fa 0%,#2b8bbf 55%,#1a5c90 100%)!important;
  color:#fff!important;font-size:28px!important;line-height:1!important;
  border:none!important;outline:none!important;
  box-shadow:0 6px 22px rgba(58,167,232,.55),0 2px 6px rgba(0,0,0,.12)!important;
  cursor:pointer!important;padding:0!important;margin:0!important;
  display:flex!important;align-items:center!important;justify-content:center!important;
  transition:transform .18s,box-shadow .18s!important;
  overflow:visible!important;position:relative!important;
  animation:fab-in .5s .4s cubic-bezier(.34,1.56,.64,1) both!important
}
@keyframes fab-in{from{transform:scale(0) rotate(-90deg);opacity:0}to{transform:scale(1) rotate(0);opacity:1}}
button.chat-float-btn::before,
button.bk-btn.chat-float-btn::before{
  content:'';position:absolute;inset:-2px;
  border-radius:50%;border:2px solid rgba(58,167,232,.45);
  animation:fab-pulse 2.2s ease-out 1.5s infinite;pointer-events:none
}
@keyframes fab-pulse{0%{transform:scale(1);opacity:.5}100%{transform:scale(1.65);opacity:0}}
button.chat-float-btn:hover,
button.bk-btn.chat-float-btn:hover{
  transform:translateY(-3px) scale(1.07)!important;
  box-shadow:0 10px 32px rgba(58,167,232,.65),0 4px 10px rgba(0,0,0,.15)!important
}
button.chat-float-btn:active,
button.bk-btn.chat-float-btn:active{transform:scale(.94)!important}
button.chat-float-btn.chat-fab-open,
button.bk-btn.chat-float-btn.chat-fab-open{
  background:linear-gradient(145deg,#f472b6 0%,#e0348a 60%,#b02070 100%)!important;
  box-shadow:0 6px 22px rgba(224,52,138,.5),0 2px 6px rgba(0,0,0,.12)!important;
  animation:none!important
}
button.chat-float-btn.chat-fab-open::before,
button.bk-btn.chat-float-btn.chat-fab-open::before{animation:none!important;opacity:0!important}

/* ── drawer checkbox toggles (CSS-only, no JS needed) ───────────────────── */
#tips-toggle{display:none!important}
#tips-toggle:checked~.tips-drawer{transform:translateX(0)}
#guides-toggle{display:none!important}
#guides-toggle:checked~.guides-drawer{transform:translateX(0)}

/* ── chat overlay panel (fixed, bottom-right) ───────────────────────────── */
.chat-overlay-panel{
  position:fixed!important;bottom:100px!important;right:28px!important;
  width:400px!important;max-height:580px!important;
  background:#fff!important;border-radius:16px!important;
  box-shadow:0 8px 40px rgba(0,0,0,.18)!important;
  border:1px solid #e2e8f0!important;
  overflow:hidden!important;z-index:9998!important;
  display:flex!important;flex-direction:column!important
}
.chat-overlay-panel .bk-panel-models-layout-column{
  display:flex!important;flex-direction:column!important;flex:1!important;
  overflow:hidden!important
}

/* ── pdf export button (green) ──────────────────────────────────────────── */
.pdf-btn button,.pdf-btn a,.pdf-btn .bk-btn{
  width:100%!important;
  background:linear-gradient(135deg,#16a34a,#15803d)!important;
  border:none!important;color:#fff!important;border-radius:10px!important;
  font-size:13px!important;font-weight:700!important;
  padding:10px 16px!important;cursor:pointer!important;
  text-align:center!important;text-decoration:none!important;
  display:flex!important;align-items:center!important;justify-content:center!important;
  gap:7px!important;transition:all .15s!important;
  box-shadow:0 2px 8px rgba(22,163,74,.3)!important
}
.pdf-btn button:hover,.pdf-btn a:hover,.pdf-btn .bk-btn:hover{
  background:linear-gradient(135deg,#15803d,#166534)!important;
  box-shadow:0 4px 14px rgba(22,163,74,.4)!important;
  transform:translateY(-1px)!important
}
.asst-header{
  display:flex;align-items:center;gap:10px;margin-bottom:14px;
  padding-bottom:12px;border-bottom:2px solid #e2e8f0
}
.asst-icon{
  width:36px;height:36px;background:linear-gradient(135deg,#3aa7e8,#2b8bbf);
  border-radius:10px;display:flex;align-items:center;justify-content:center;
  font-size:18px;flex-shrink:0
}
.asst-title{font-size:15px;font-weight:700;color:#1e293b}
.asst-sub{font-size:12px;color:#64748b;margin-top:1px}
.quick-row{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:14px}
.quick-action-btn button{
  background:#f8fafc!important;border:1.5px solid #e2e8f0!important;
  color:#374151!important;border-radius:20px!important;font-size:12px!important;
  font-weight:600!important;padding:7px 14px!important;
  cursor:pointer!important;transition:all .15s!important;white-space:nowrap!important
}
.quick-action-btn button:hover{
  background:#f0f8fe!important;border-color:#9dd0ef!important;color:#2b8bbf!important
}
.chat-box{
  min-height:200px;max-height:340px;overflow-y:auto;
  background:#f8fafc;border-radius:12px;padding:14px;
  margin-bottom:12px;border:1px solid #e2e8f0
}
.chat-empty{
  display:flex;flex-direction:column;align-items:center;
  justify-content:center;padding:32px 0;gap:8px;
  font-size:13px;color:#94a3b8
}
.msg-user{
  background:linear-gradient(135deg,#3aa7e8,#2b8bbf);color:#fff;
  border-radius:14px 14px 3px 14px;padding:10px 14px;
  margin-bottom:10px;font-size:13px;max-width:88%;
  margin-left:auto;text-align:right;line-height:1.5;word-wrap:break-word
}
.msg-asst{
  background:#fff;border:1px solid #e2e8f0;color:#374151;
  border-radius:14px 14px 14px 3px;padding:10px 14px;
  margin-bottom:10px;font-size:13px;max-width:92%;
  line-height:1.6;word-wrap:break-word;
  box-shadow:0 1px 2px rgba(0,0,0,.04)
}
.msg-typing{
  display:flex;gap:5px;padding:12px 14px;
  background:#fff;border:1px solid #e2e8f0;border-radius:14px 14px 14px 3px;
  width:60px;margin-bottom:10px
}
.msg-typing span{
  width:8px;height:8px;border-radius:50%;background:#bfe0f6;
  animation:typing .9s ease-in-out infinite
}
.msg-typing span:nth-child(2){animation-delay:.2s}
.msg-typing span:nth-child(3){animation-delay:.4s}
@keyframes typing{0%,60%,100%{transform:translateY(0)}30%{transform:translateY(-6px)}}
.chat-input-row{display:flex;gap:10px;align-items:center}
.chat-send-btn button{
  background:linear-gradient(135deg,#3aa7e8,#2b8bbf)!important;
  color:#fff!important;border:none!important;border-radius:10px!important;
  font-size:14px!important;font-weight:700!important;
  padding:10px 18px!important;cursor:pointer!important;
  white-space:nowrap!important
}
.chat-send-btn button:hover{
  background:linear-gradient(135deg,#2b8bbf,#1e6e9e)!important;
  box-shadow:0 4px 14px rgba(58,167,232,.4)!important
}
.chat-send-btn button:disabled{background:#cbd5e1!important}
.asst-no-plan{
  text-align:center;padding:20px;font-size:13px;color:#94a3b8
}

/* ── shared card image ──────────────────────────────────────────────────── */
.card-img{width:100%;height:160px;object-fit:cover;display:block}

/* ── restaurant cards ───────────────────────────────────────────────────── */
.rest-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:12px}
.rest-card{
  background:#fff;border-radius:12px;overflow:hidden;
  box-shadow:0 1px 3px rgba(0,0,0,.05);border:1px solid #f1f5f9
}
.rest-card-body{padding:14px 16px}
.rest-name{font-size:14px;font-weight:700;color:#1e293b;margin-bottom:4px}
.rest-cuisine{font-size:11px;color:#94a3b8;text-transform:uppercase;letter-spacing:.5px;margin-bottom:8px}
.rest-must{
  background:#fff7ed;border-left:3px solid #f59e0b;border-radius:0 8px 8px 0;
  padding:7px 10px;margin-top:10px;font-size:12px;color:#92400e;line-height:1.4
}
.rest-must-lbl{font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.5px;margin-bottom:2px}

/* ── visa card ──────────────────────────────────────────────────────────── */
.visa-card{
  background:#fff;border-radius:14px;padding:24px 26px;margin-bottom:16px;
  box-shadow:0 1px 3px rgba(0,0,0,.06),0 4px 12px rgba(0,0,0,.04);
  border:1px solid #f1f5f9
}
.visa-badge-free{background:#dcfce7;color:#166534;padding:4px 14px;border-radius:999px;font-size:12px;font-weight:700}
.visa-badge-req{background:#fee2e2;color:#991b1b;padding:4px 14px;border-radius:999px;font-size:12px;font-weight:700}
.visa-badge-arrival{background:#fef3c7;color:#92400e;padding:4px 14px;border-radius:999px;font-size:12px;font-weight:700}
.visa-badge-eta{background:#ede9fe;color:#5b21b6;padding:4px 14px;border-radius:999px;font-size:12px;font-weight:700}
.visa-row{display:flex;gap:8px;align-items:flex-start;padding:8px 0;border-bottom:1px solid #f1f5f9;font-size:13px}
.visa-row:last-child{border-bottom:none}
.visa-row-lbl{min-width:160px;flex-shrink:0;color:#64748b;font-weight:600;font-size:12px}
.visa-row-val{color:#1e293b}
.visa-req-item{
  display:flex;align-items:flex-start;gap:8px;padding:6px 0;
  font-size:13px;color:#374151;border-bottom:1px solid #f8fafc
}
.visa-req-item:last-child{border-bottom:none}
.visa-check{color:#22c55e;font-weight:700;flex-shrink:0}

/* ── transport cards ────────────────────────────────────────────────────── */
.trans-section-title{
  font-size:12px;font-weight:700;color:#3aa7e8;text-transform:uppercase;
  letter-spacing:.6px;margin:20px 0 10px;padding-bottom:6px;border-bottom:1px solid #e2e8f0
}
.trans-section-title:first-child{margin-top:0}
.trans-card{
  background:#f8fafc;border:1px solid #e2e8f0;border-radius:12px;
  padding:14px 16px;margin-bottom:10px;
  display:grid;grid-template-columns:1fr auto;gap:8px;align-items:start
}
.trans-mode{font-size:13px;font-weight:700;color:#1e293b;margin-bottom:2px}
.trans-desc{font-size:12px;color:#64748b;line-height:1.4}
.trans-cost{font-size:18px;font-weight:800;color:#3aa7e8;text-align:right}
.trans-cost-note{font-size:10px;color:#94a3b8;text-align:right;margin-top:1px}
.trans-tip{
  font-size:11px;color:#64748b;background:#f0f8fe;border-radius:6px;
  padding:4px 8px;margin-top:6px;grid-column:1/-1
}
.trans-duration{font-size:11px;color:#475569;margin-top:2px}

/* ── hourly weather ─────────────────────────────────────────────────────── */
.hourly-day{margin-bottom:20px}
.hourly-day-hdr{
  font-size:12px;font-weight:700;color:#1e6e9e;text-transform:uppercase;
  letter-spacing:.5px;margin-bottom:10px;padding:6px 10px;
  background:#f0f8fe;border-radius:8px;border-left:3px solid #3aa7e8
}
.hourly-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(90px,1fr));gap:8px}
.hourly-slot{
  background:#fff;border:1px solid #e2e8f0;border-radius:10px;
  padding:10px 8px;text-align:center;font-size:11px
}
.hourly-slot.rain{border-color:#93c5fd;background:#eff6ff}
.hourly-slot.storm{border-color:#f87171;background:#fef2f2}
.hourly-time{font-size:10px;font-weight:700;color:#94a3b8;margin-bottom:4px}
.hourly-period{font-size:9px;color:#cbd5e1;text-transform:uppercase;letter-spacing:.3px}
.hourly-temp{font-size:13px;font-weight:800;color:#1e293b;margin:4px 0}
.hourly-desc{font-size:10px;color:#64748b;line-height:1.3;margin-bottom:3px}
.hourly-rain{font-size:10px;color:#3b82f6;font-weight:600}
.caution-item{
  display:flex;gap:8px;align-items:flex-start;padding:8px 12px;margin-bottom:6px;
  background:#fef2f2;border:1px solid #fecaca;border-radius:8px;
  font-size:12px;color:#991b1b;line-height:1.4
}
.caution-icon{flex-shrink:0;font-size:14px}

/* ── travel tips drawer ─────────────────────────────────────────────────── */
#tips-tab{
  position:fixed;right:0;top:50%;transform:translateY(-50%);
  width:36px;height:96px;z-index:9001;
  background:linear-gradient(160deg,#3aa7e8,#2b8bbf);
  border-radius:10px 0 0 10px;border:none;outline:none;
  display:flex;flex-direction:column;align-items:center;justify-content:center;gap:5px;
  cursor:pointer;box-shadow:-3px 0 14px rgba(58,167,232,.45);
  transition:background .15s,width .15s;user-select:none
}
#tips-tab:hover{background:linear-gradient(160deg,#4ec4fa,#3aa7e8);width:40px}
#tips-tab .tt-icon{font-size:16px;line-height:1}
#tips-tab .tt-lbl{
  writing-mode:vertical-rl;text-orientation:mixed;transform:rotate(180deg);
  font-size:9px;font-weight:700;color:#fff;letter-spacing:1.4px;text-transform:uppercase
}
.tips-drawer{
  position:fixed;top:0;right:0;height:100vh;width:340px;
  background:#fff;box-shadow:-4px 0 32px rgba(0,0,0,.14);
  border-left:1px solid #e2e8f0;z-index:9000;
  transform:translateX(100%);transition:transform .3s cubic-bezier(.4,0,.2,1);
  display:flex;flex-direction:column;overflow:hidden
}
.tips-drawer-hdr{
  padding:18px 20px 14px;border-bottom:1px solid #e2e8f0;
  display:flex;align-items:center;justify-content:space-between;flex-shrink:0
}
.tips-drawer-title{font-size:16px;font-weight:700;color:#1e293b;display:flex;align-items:center;gap:8px}
.tips-drawer-close{
  width:30px;height:30px;border-radius:50%;background:#f1f5f9;border:none;
  cursor:pointer;display:flex;align-items:center;justify-content:center;
  font-size:18px;color:#64748b;line-height:1;transition:background .15s;user-select:none
}
.tips-drawer-close:hover{background:#e2e8f0;color:#1e293b}
.tips-drawer-body{flex:1;overflow-y:auto;padding:16px 20px}
.tip-drawer-item{
  display:flex;gap:12px;align-items:flex-start;padding:11px 0;
  border-bottom:1px solid #f1f5f9;font-size:13px;color:#374151;line-height:1.55
}
.tip-drawer-item:last-child{border-bottom:none}
.tip-drawer-num{
  min-width:26px;height:26px;border-radius:50%;
  background:linear-gradient(135deg,#3aa7e8,#2b8bbf);
  color:#fff;font-size:11px;font-weight:700;
  display:flex;align-items:center;justify-content:center;flex-shrink:0;margin-top:1px
}

/* ── travel guides drawer ───────────────────────────────────────────────── */
#guides-tab{
  position:fixed;right:0;top:calc(50% + 56px);
  width:36px;height:90px;z-index:9001;
  background:linear-gradient(160deg,#16a34a,#15803d);
  border-radius:10px 0 0 10px;border:none;outline:none;
  display:flex;flex-direction:column;align-items:center;justify-content:center;gap:5px;
  cursor:pointer;box-shadow:-3px 0 14px rgba(22,163,74,.45);
  transition:background .15s,width .15s;user-select:none
}
#guides-tab:hover{background:linear-gradient(160deg,#22c55e,#16a34a);width:40px}
#guides-tab .gt-icon{font-size:15px;line-height:1}
#guides-tab .gt-lbl{
  writing-mode:vertical-rl;text-orientation:mixed;transform:rotate(180deg);
  font-size:9px;font-weight:700;color:#fff;letter-spacing:1.4px;text-transform:uppercase
}
.guides-drawer{
  position:fixed;top:0;right:0;height:100vh;width:340px;
  background:#fff;box-shadow:-4px 0 32px rgba(0,0,0,.14);
  border-left:1px solid #e2e8f0;z-index:9000;
  transform:translateX(100%);transition:transform .3s cubic-bezier(.4,0,.2,1);
  display:flex;flex-direction:column;overflow:hidden
}
.guides-drawer-hdr{
  padding:18px 20px 14px;border-bottom:1px solid #e2e8f0;
  display:flex;align-items:center;justify-content:space-between;flex-shrink:0
}
.guides-drawer-title{font-size:16px;font-weight:700;color:#1e293b;display:flex;align-items:center;gap:8px}
.guides-drawer-close{
  width:30px;height:30px;border-radius:50%;background:#f1f5f9;border:none;
  cursor:pointer;display:flex;align-items:center;justify-content:center;
  font-size:18px;color:#64748b;line-height:1;transition:background .15s;user-select:none
}
.guides-drawer-close:hover{background:#e2e8f0;color:#1e293b}
.guides-drawer-body{flex:1;overflow-y:auto;padding:16px 20px}
.guide-drawer-item{
  display:block;background:#f8fafc;border:1px solid #e2e8f0;border-radius:10px;
  padding:12px 14px;margin-bottom:8px;text-decoration:none!important;
  transition:background .12s,border-color .12s
}
.guide-drawer-item:hover{background:#f0fdf4;border-color:#86efac}
.guide-drawer-title{font-size:13px;font-weight:600;color:#1e293b;margin-bottom:2px;line-height:1.4}
.guide-drawer-url{font-size:11px;color:#16a34a;margin-bottom:4px;word-break:break-all}
.guide-drawer-snip{font-size:12px;color:#64748b;line-height:1.45}
"""

pn.extension("tabulator", sizing_mode="stretch_width", raw_css=[CSS])


# ── Helpers ───────────────────────────────────────────────────────────────────

def _wx_icon(cond: str) -> str:
    c = cond.lower()
    if "clear" in c or "sunny" in c:   return "Sunny"
    if "overcast" in c:                return "Overcast"
    if "cloud" in c:                   return "Cloudy"
    if "rain" in c or "drizzle" in c:  return "Rain"
    if "thunder" in c or "storm" in c: return "Storm"
    if "snow" in c:                    return "Snow"
    if "fog" in c or "mist" in c:      return "Fog"
    return "Fair"


def _stars(rating: float) -> str:
    f = int(round(rating))
    return (
        "<span style='color:#f59e0b;letter-spacing:1px'>"
        + "★" * min(f, 5) + "☆" * max(0, 5 - f)
        + f"</span> <span style='color:#64748b;font-size:12px'>{rating}</span>"
    )


def _tips_drawer_html(r: dict) -> str:
    """Render the right-side travel tips drawer (fixed position, toggle with handle)."""
    tips = r.get("travel_tips") or []
    if not tips:
        body = '<div style="font-size:13px;color:#94a3b8;text-align:center;padding:24px 0">No travel tips available.</div>'
    else:
        items = "".join(
            f'<div class="tip-drawer-item">'
            f'<div class="tip-drawer-num">{i+1}</div>'
            f'<div>{_html.escape(t)}</div>'
            f'</div>'
            for i, t in enumerate(tips)
        )
        body = items

    return f"""
<input type="checkbox" id="tips-toggle">
<label for="tips-toggle" id="tips-tab" title="Travel Tips">
  <span class="tt-icon">&#9992;</span>
  <span class="tt-lbl">Tips</span>
</label>
<div class="tips-drawer">
  <div class="tips-drawer-hdr">
    <div class="tips-drawer-title">
      <span style="font-size:18px">&#128161;</span> Travel Tips
    </div>
    <label for="tips-toggle" class="tips-drawer-close">&#x2715;</label>
  </div>
  <div class="tips-drawer-body">{body}</div>
</div>"""


def _guides_drawer_html(r: dict) -> str:
    """Render the right-side travel guides drawer (fixed position, toggle with handle)."""
    guides = r.get("travel_guides") or []
    if not guides:
        body = '<div style="font-size:13px;color:#94a3b8;text-align:center;padding:24px 0">No travel guides available.</div>'
    else:
        items = ""
        for g in guides:
            url   = g.get("url", "#")
            title = _html.escape(g.get("title", "Guide"))
            snip  = _html.escape(g.get("snippet", ""))
            url_display  = url[:55] + "…" if len(url) > 55 else url
            snip_display = snip[:160] + "…" if len(snip) > 160 else snip
            items += (
                f'<a class="guide-drawer-item" href="{url}" target="_blank" rel="noopener">'
                f'<div class="guide-drawer-title">{title}</div>'
                f'<div class="guide-drawer-url">{url_display}</div>'
                + (f'<div class="guide-drawer-snip">{snip_display}</div>' if snip_display else "")
                + '</a>'
            )
        body = items

    count = len(guides)
    count_pill = (
        f'<span style="background:#dcfce7;color:#166534;font-size:11px;font-weight:600;'
        f'padding:2px 9px;border-radius:999px;margin-left:8px">{count}</span>'
        if count else ""
    )

    return f"""
<input type="checkbox" id="guides-toggle">
<label for="guides-toggle" id="guides-tab" title="Travel Guides">
  <span class="gt-icon">&#128218;</span>
  <span class="gt-lbl">Guide</span>
</label>
<div class="guides-drawer">
  <div class="guides-drawer-hdr">
    <div class="guides-drawer-title">
      <span style="font-size:18px">&#128218;</span> Travel Guides{count_pill}
    </div>
    <label for="guides-toggle" class="guides-drawer-close">&#x2715;</label>
  </div>
  <div class="guides-drawer-body">{body}</div>
</div>"""


def _wx_full_section_html(r: dict) -> str:
    """Build the combined weather section: daily forecast + extended hourly + cautions."""
    wx          = r.get("weather_info") or {}
    cond        = wx.get("conditions", "No weather data")
    temp        = wx.get("temp_range", "N/A")
    rain        = wx.get("rain_chance", "N/A")
    fcast       = wx.get("forecast") or []
    hourly_days = wx.get("hourly_forecast") or []
    cautions    = wx.get("outdoor_caution") or []

    rain_pill_color = {
        "Low":      ("#f0fdf4", "#bbf7d0", "#166534"),
        "Moderate": ("#fef9c3", "#fde68a", "#854d0e"),
        "High":     ("#fee2e2", "#fecaca", "#991b1b"),
    }.get(rain, ("#f8fafc", "#e2e8f0", "#64748b"))

    def _parse_fcast(d):
        if isinstance(d, dict):
            return d.get("condition", "?"), d.get("temp_range", "")
        parts = str(d).split(",", 1)
        label = parts[0].strip()
        rest  = parts[1].strip() if len(parts) > 1 else ""
        if ":" in label:
            label = label.split(":", 1)[-1].strip()
        return label, rest

    def _wx_day_icon(label: str) -> str:
        l = label.lower()
        if "clear" in l or "sunny" in l:  return "☀️"
        if "overcast" in l:               return "☁️"
        if "cloud" in l:                  return "⛅"
        if "rain" in l or "drizzle" in l: return "🌧️"
        if "thunder" in l or "storm" in l:return "⛈️"
        if "snow" in l:                   return "🌨️"
        if "fog" in l or "mist" in l:     return "🌫️"
        return "🌤️"

    wx_cards = "".join(f"""
    <div class="wx-day">
      <div class="wx-lbl">Day {i+1}</div>
      <div style="font-size:22px;margin:4px 0">{_wx_day_icon(_parse_fcast(d)[0])}</div>
      <div class="wx-cond">{_parse_fcast(d)[0][:28]}</div>
      <div class="wx-temp">{_parse_fcast(d)[1]}</div>
    </div>""" for i, d in enumerate(fcast[:7]))

    caution_inline_html = "".join(
        f'<div style="display:flex;gap:6px;align-items:flex-start;padding:5px 0;'
        f'font-size:12px;color:#991b1b">'
        f'<span>&#9888;</span><span>{_html.escape(c)}</span></div>'
        for c in cautions[:3]
    )

    daily_html = f"""
    <div class="sec-card" style="margin-bottom:16px">
      <div class="sec-title">Weather Forecast
        <span class="cnt-pill">{len(fcast)} days</span>
      </div>
      <div style="display:flex;gap:10px;flex-wrap:wrap;margin-bottom:14px">
        <span class="hero-pill" style="background:#f0f8fe;border-color:#9dd0ef;color:#1e6e9e">
          &#127777; {_html.escape(temp)}
        </span>
        <span class="hero-pill" style="background:#f8fafc;border-color:#e2e8f0;color:#374151">
          {_html.escape(cond)}
        </span>
        <span class="hero-pill"
              style="background:{rain_pill_color[0]};border-color:{rain_pill_color[1]};color:{rain_pill_color[2]}">
          &#127783; Rain: {_html.escape(rain)}
        </span>
      </div>
      <div class="wx-grid">{wx_cards}</div>
      {('<div style="margin-top:12px;padding-top:12px;border-top:1px dashed #e2e8f0">' + caution_inline_html + '</div>') if caution_inline_html else ''}
    </div>"""

    # ── Extended hourly forecast ──────────────────────────────────────────
    if not hourly_days:
        return daily_html

    def _slot_cls(slot):
        desc = slot.get("description", "").lower()
        rain_mm = slot.get("rain_mm", 0) or 0
        if "storm" in desc or "thunder" in desc:  return "hourly-slot storm"
        if "rain" in desc or rain_mm > 1.0:       return "hourly-slot rain"
        return "hourly-slot"

    day_blocks = ""
    for day in hourly_days:
        label      = _html.escape(day.get("label") or day.get("date", ""))
        slots      = day.get("slots") or []
        slot_cards = ""
        for s in slots:
            emoji   = _wx_icon_emoji(s.get("icon", "partly-cloudy"))
            rain_mm = s.get("rain_mm", 0) or 0
            slot_cards += f"""
            <div class="{_slot_cls(s)}">
              <div class="hourly-time">{_html.escape(s.get('time',''))}</div>
              <div class="hourly-period">{_html.escape(s.get('period',''))}</div>
              <div style="font-size:18px;margin:4px 0">{emoji}</div>
              <div class="hourly-temp">{s.get('temp_c','?')}°C</div>
              <div class="hourly-desc">{_html.escape(s.get('description',''))}</div>
              {'<div class="hourly-rain">&#128166; ' + f'{rain_mm:.1f}mm' + '</div>' if rain_mm > 0.1 else ''}
            </div>"""
        day_blocks += f"""
        <div class="hourly-day">
          <div class="hourly-day-hdr">{label}</div>
          <div class="hourly-grid">{slot_cards}</div>
        </div>"""

    caution_items = "".join(
        f'<div class="caution-item"><div class="caution-icon">&#9888;</div>'
        f'<div>{_html.escape(c)}</div></div>'
        for c in cautions
    )
    caution_block = (
        f'<div style="margin-bottom:16px">'
        f'<div style="font-size:12px;font-weight:700;color:#dc2626;text-transform:uppercase;'
        f'letter-spacing:.5px;margin-bottom:8px">Outdoor Cautions</div>'
        f'{caution_items}</div>'
    ) if caution_items else ""

    hourly_html = (
        f'<div class="sec-card" style="margin-bottom:16px">'
        f'<div class="sec-title">Hourly Forecast '
        f'<span class="cnt-pill">{len(hourly_days)} days</span></div>'
        f'{caution_block}{day_blocks}</div>'
    )

    return daily_html + hourly_html


# ── Map helpers ──────────────────────────────────────────────────────────────
_geo_cache: dict = {}

# Hardcoded lat/lon for the most common destinations — instant, no network call.
# Falls back to Nominatim only for cities not listed here.
_CITY_COORDS: dict[str, tuple] = {
    # Asia
    "tokyo": (35.6762, 139.6503), "osaka": (34.6937, 135.5023),
    "kyoto": (35.0116, 135.7681), "sapporo": (43.0618, 141.3545),
    "beijing": (39.9042, 116.4074), "shanghai": (31.2304, 121.4737),
    "hong kong": (22.3193, 114.1694), "singapore": (1.3521, 103.8198),
    "bangkok": (13.7563, 100.5018), "phuket": (7.8804, 98.3923),
    "chiang mai": (18.7883, 98.9853), "bali": (-8.3405, 115.0920),
    "denpasar": (-8.6705, 115.2126), "jakarta": (-6.2088, 106.8456),
    "kuala lumpur": (3.1390, 101.6869), "manila": (14.5995, 120.9842),
    "seoul": (37.5665, 126.9780), "taipei": (25.0330, 121.5654),
    "hanoi": (21.0285, 105.8542), "ho chi minh city": (10.8231, 106.6297),
    "colombo": (6.9271, 79.8612), "kathmandu": (27.7172, 85.3240),
    "delhi": (28.6139, 77.2090), "new delhi": (28.6139, 77.2090),
    "mumbai": (19.0760, 72.8777), "bangalore": (12.9716, 77.5946),
    "bengaluru": (12.9716, 77.5946), "chennai": (13.0827, 80.2707),
    "hyderabad": (17.3850, 78.4867), "kolkata": (22.5726, 88.3639),
    "goa": (15.2993, 74.1240), "jaipur": (26.9124, 75.7873),
    "dubai": (25.2048, 55.2708), "abu dhabi": (24.4539, 54.3773),
    "doha": (25.2854, 51.5310), "riyadh": (24.7136, 46.6753),
    "istanbul": (41.0082, 28.9784), "tel aviv": (32.0853, 34.7818),
    "male": (4.1755, 73.5093),
    # Europe
    "london": (51.5074, -0.1278), "paris": (48.8566, 2.3522),
    "rome": (41.9028, 12.4964), "milan": (45.4654, 9.1859),
    "venice": (45.4408, 12.3155), "florence": (43.7696, 11.2558),
    "barcelona": (41.3851, 2.1734), "madrid": (40.4168, -3.7038),
    "berlin": (52.5200, 13.4050), "munich": (48.1351, 11.5820),
    "frankfurt": (50.1109, 8.6821), "amsterdam": (52.3676, 4.9041),
    "vienna": (48.2082, 16.3738), "zurich": (47.3769, 8.5417),
    "stockholm": (59.3293, 18.0686), "oslo": (59.9139, 10.7522),
    "copenhagen": (55.6761, 12.5683), "athens": (37.9838, 23.7275),
    "lisbon": (38.7223, -9.1393), "prague": (50.0755, 14.4378),
    "budapest": (47.4979, 19.0402), "warsaw": (52.2297, 21.0122),
    "dublin": (53.3498, -6.2603), "edinburgh": (55.9533, -3.1883),
    "reykjavik": (64.1355, -21.8954),
    # Americas
    "new york": (40.7128, -74.0060), "los angeles": (34.0522, -118.2437),
    "chicago": (41.8781, -87.6298), "miami": (25.7617, -80.1918),
    "san francisco": (37.7749, -122.4194), "seattle": (47.6062, -122.3321),
    "boston": (42.3601, -71.0589), "washington": (38.9072, -77.0369),
    "washington dc": (38.9072, -77.0369), "toronto": (43.6532, -79.3832),
    "vancouver": (49.2827, -123.1207), "montreal": (45.5017, -73.5673),
    "mexico city": (19.4326, -99.1332), "cancun": (21.1619, -86.8515),
    "havana": (23.1136, -82.3666),
    "bogota": (4.7110, -74.0721), "lima": (-12.0464, -77.0428),
    "sao paulo": (-23.5505, -46.6333), "rio de janeiro": (-22.9068, -43.1729),
    "buenos aires": (-34.6037, -58.3816), "santiago": (-33.4489, -70.6693),
    # Africa
    "cairo": (30.0444, 31.2357), "casablanca": (33.5731, -7.5898),
    "marrakech": (31.6295, -7.9811), "nairobi": (-1.2921, 36.8219),
    "cape town": (-33.9249, 18.4241), "johannesburg": (-26.2041, 28.0473),
    # Oceania
    "sydney": (-33.8688, 151.2093), "melbourne": (-37.8136, 144.9631),
    "brisbane": (-27.4698, 153.0251), "perth": (-31.9505, 115.8605),
    "auckland": (-36.8509, 174.7645), "honolulu": (21.3069, -157.8583),
}


def _geocode_city(query: str) -> tuple | None:
    """
    Resolve a destination string to (lat, lon).
    Layer 1 — instant hardcoded lookup for ~100 major cities.
    Layer 2 — Nominatim (OpenStreetMap) geocoding API.
    """
    key = query.lower().strip()
    # Strip country suffix for lookup  (e.g. "Sydney, Australia" → "sydney")
    city_key = key.split(",")[0].strip()

    if city_key in _CITY_COORDS:
        return _CITY_COORDS[city_key]
    if key in _geo_cache:
        return _geo_cache[key]

    # Nominatim fallback
    try:
        url = ("https://nominatim.openstreetmap.org/search?"
               + _uparse.urlencode({"q": query, "format": "json", "limit": 1}))
        req = _urllib_req.Request(url, headers={"User-Agent": "VoyagerTripPlanner/1.0"})
        with _urllib_req.urlopen(req, timeout=10) as resp:
            data = _json.loads(resp.read())
        result = (float(data[0]["lat"]), float(data[0]["lon"])) if data else None
    except Exception:
        result = None
    _geo_cache[key] = result
    return result


def _map_jitter(text: str, scale: float = 0.022) -> tuple:
    """Deterministic lat/lng offset seeded by text — spreads points around city center."""
    h = int(_hashlib.md5(text.encode()).hexdigest(), 16)
    return (round(((h & 0xFFFF) / 65535 - 0.5) * scale, 6),
            round(((h >> 16 & 0xFFFF) / 65535 - 0.5) * scale, 6))


_CAT_ACT = {
    "Culture":   ("#e0f4fd", "#2b8bbf"),
    "Food":      ("#fff7ed", "#c2410c"),
    "Adventure": ("#fef2f2", "#dc2626"),
    "Leisure":   ("#f0fdfa", "#0f766e"),
    "Nature":    ("#f0fdf4", "#15803d"),
}

_CAT_EVT = {
    "Music":      ("#fdf4ff", "#7e22ce"),
    "Sports":     ("#ecfdf5", "#065f46"),
    "Arts":       ("#fff7ed", "#c2410c"),
    "Comedy":     ("#fefce8", "#854d0e"),
    "Family":     ("#f0f8fe", "#1e6e9e"),
    "Film":       ("#f8fafc", "#475569"),
    "Other":      ("#f1f5f9", "#64748b"),
    "Undefined":  ("#f1f5f9", "#64748b"),
}


# ── Section builders ──────────────────────────────────────────────────────────

def _hero(r: dict, source_city: str = "") -> pn.pane.HTML:
    dest    = r.get("destination", "—")
    start   = r.get("start_date", "")
    end     = r.get("end_date", "")
    nights  = r.get("nights") or "?"
    budget  = r.get("budget_usd", 0)
    bd      = r.get("budget_breakdown") or {}
    spent   = bd.get("flights", 0) + bd.get("accommodation", 0) + bd.get("activities", 0)
    remain  = budget - spent
    style   = r.get("travel_style") or "Mid-range"
    purpose = r.get("trip_purpose") or "Leisure"
    n_trav  = r.get("num_travelers") or 1
    events  = len(r.get("event_results") or [])
    src     = _html.escape(source_city) if source_city else "Origin"
    dst     = _html.escape(dest)

    return pn.pane.HTML(f"""
    <div class="trip-hero">
      <div class="hero-bg-c1"></div>
      <div class="hero-bg-c2"></div>
      <div class="hero-route">
        <div class="hero-city">
          <div class="hero-city-lbl">FROM</div>
          <div class="hero-city-name">{src}</div>
        </div>
        <div class="hero-track">
          <div class="hero-track-line"></div>
          <div class="hero-plane-anim">&#x2708;&#xFE0E;</div>
        </div>
        <div class="hero-city dst">
          <div class="hero-city-lbl">TO</div>
          <div class="hero-city-name big">{dst}</div>
        </div>
      </div>
      <div class="hero-dates-badge">{start} → {end} &nbsp;·&nbsp; {nights} nights</div>
      <div>
        <span class="hero-pill">Budget: ${budget:,.0f}</span>
        <span class="hero-pill">{n_trav} traveler{'s' if n_trav != 1 else ''}</span>
        <span class="hero-pill">{style}</span>
        <span class="hero-pill">{purpose}</span>
        <span class="hero-pill">{events} events</span>
        <span class="hero-pill">${abs(remain):,.0f} {'left' if remain >= 0 else 'over budget'}</span>
      </div>
    </div>""", sizing_mode="stretch_width")


def _tab_overview(r: dict) -> pn.Column:
    bd    = r.get("budget_breakdown") or {}
    fl    = bd.get("flights", 0)
    ho    = bd.get("accommodation", 0)
    ac    = bd.get("activities", 0)
    rem   = bd.get("remaining", 0)
    total = r.get("budget_usd", 1) or 1
    spent = fl + ho + ac
    pct   = min(int(spent / total * 100), 100)

    def bar(lbl, amt, color):
        w = min(int(amt / total * 100), 100)
        return (f'<div class="bbar"><div class="bbar-lbl">{lbl}</div>'
                f'<div class="bbar-track"><div class="bbar-fill" style="width:{w}%;background:{color}"></div></div>'
                f'<div class="bbar-amt">${amt:,.0f}</div></div>')

    rem_color = "#16a34a" if rem >= 0 else "#dc2626"
    rem_str   = f"${rem:,.0f}" if rem >= 0 else f"-${abs(rem):,.0f}"

    events     = r.get("event_results") or []
    evt_count  = len(events)
    rem_kc  = "#22c55e" if rem >= 0 else "#ef4444"
    evt_kpi = f"""
      <div class="kpi-card" style="--kc:#ec4899">
        <div class="kpi-badge">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
            <rect x="2" y="4" width="12" height="11" rx="2" fill="white"/>
            <rect x="2" y="4" width="12" height="4.5" rx="2" fill="white" opacity=".5"/>
            <rect x="5.5" y="2.5" width="1.5" height="3" rx=".75" fill="white"/>
            <rect x="9" y="2.5" width="1.5" height="3" rx=".75" fill="white"/>
            <line x1="5" y1="11" x2="11" y2="11" stroke="rgba(0,0,0,.18)" stroke-width="1"/>
          </svg>
        </div>
        <div class="kpi-v">{evt_count}</div>
        <div class="kpi-l">Events</div>
      </div>"""

    html = f"""
    <div class="kpi-row">
      <div class="kpi-card" style="--kc:#3b82f6">
        <div class="kpi-badge">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
            <path d="M2 8.5 L8 6 L14 8 Q14 9.2 8 10.5 Z" fill="white"/>
            <path d="M7.5 8 L5 2 L8.2 3 L10 7.5 Z" fill="white" opacity=".72"/>
            <path d="M7.5 8 L5 14 L8.2 13 L10 8.5 Z" fill="white" opacity=".72"/>
            <circle cx="13.5" cy="8" r=".9" fill="white" opacity=".5"/>
          </svg>
        </div>
        <div class="kpi-v">${fl:,.0f}</div>
        <div class="kpi-l">Flights</div>
      </div>
      <div class="kpi-card" style="--kc:#f59e0b">
        <div class="kpi-badge">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
            <rect x="3" y="3" width="10" height="12" rx="1.5" fill="white"/>
            <rect x="3" y="3" width="10" height="3.5" rx="1.5" fill="white" opacity=".45"/>
            <rect x="5" y="8" width="2" height="2" rx=".5" fill="rgba(0,0,0,.22)"/>
            <rect x="9" y="8" width="2" height="2" rx=".5" fill="rgba(0,0,0,.22)"/>
            <rect x="6.5" y="12" width="3" height="3" rx=".5" fill="rgba(0,0,0,.2)"/>
            <line x1="3" y1="6.5" x2="13" y2="6.5" stroke="rgba(0,0,0,.12)" stroke-width="1"/>
          </svg>
        </div>
        <div class="kpi-v">${ho:,.0f}</div>
        <div class="kpi-l">Hotels</div>
      </div>
      <div class="kpi-card" style="--kc:#2b8bbf">
        <div class="kpi-badge">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
            <circle cx="8" cy="8" r="6.5" stroke="white" stroke-width="1.4" fill="none"/>
            <circle cx="8" cy="8" r="3.5" stroke="white" stroke-width=".7" fill="none" opacity=".4"/>
            <path d="M8 8 L5.5 12 L8 1.5 L10.5 12 Z" fill="white"/>
            <path d="M8 8 L11 4.5 L8 14.5 L5 4.5 Z" fill="white" opacity=".3"/>
            <circle cx="8" cy="8" r="1.4" fill="white"/>
          </svg>
        </div>
        <div class="kpi-v">${ac:,.0f}</div>
        <div class="kpi-l">Activities</div>
      </div>
      {evt_kpi}
      <div class="kpi-card" style="--kc:{rem_kc}">
        <div class="kpi-badge">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
            <rect x="1.5" y="5.5" width="13" height="8.5" rx="2" fill="white"/>
            <path d="M4 5.5 L12 3 L13.5 5.5" stroke="white" stroke-width="1.5"
                  stroke-linejoin="round" fill="none"/>
            <rect x="10" y="9" width="3.5" height="2.5" rx="1.25" fill="rgba(0,0,0,.18)"/>
            <circle cx="11.75" cy="10.25" r=".65" fill="white" opacity=".65"/>
          </svg>
        </div>
        <div class="kpi-v">{rem_str}</div>
        <div class="kpi-l">Remaining</div>
      </div>
    </div>

    <div class="sec-card">
      <div class="sec-title">Budget Breakdown <span class="cnt-pill">{pct}% used</span></div>
      {bar("Flights",     fl, "#3b82f6")}
      {bar("Hotels",      ho, "#f59e0b")}
      {bar("Activities",  ac, "#2b8bbf")}
      <div style="border-top:2px solid #e2e8f0;margin-top:12px;padding-top:12px;
                  display:flex;justify-content:space-between;align-items:center">
        <div style="font-size:13px;color:#64748b">Total: <b style="color:#1e293b">${total:,.0f}</b></div>
        <div style="font-size:15px;font-weight:700;color:{rem_color}">
          {rem_str} {'remaining' if rem >= 0 else 'over budget'}
        </div>
      </div>
    </div>"""
    return pn.Column(
        pn.pane.HTML(html, sizing_mode="stretch_width"),
        pn.pane.HTML(_wx_full_section_html(r), sizing_mode="stretch_width"),
        _tab_map(r),
        sizing_mode="stretch_width"
    )


def _tab_flights(r: dict) -> pn.Column:
    flights = r.get("flight_results") or []
    if not flights:
        return pn.Column(pn.pane.Alert("No flight data available.", alert_type="warning"),
                         sizing_mode="stretch_width")

    dest  = r.get("destination", "")
    d_out = r.get("start_date", "")
    d_ret = r.get("end_date", "")
    min_p = min(f.get("price_usd", 9999) for f in flights)
    rows = ""
    for f in flights:
        p       = f.get("price_usd", 0)
        cheap   = p == min_p
        airline = f.get("airline", "")
        bg      = "#f0fdf4" if cheap else "#fff"
        tag     = ("<span style='background:#dcfce7;color:#166534;padding:1px 7px;"
                   "border-radius:999px;font-size:10px;font-weight:700;margin-left:6px'>Cheapest</span>"
                   if cheap else "")
        q       = _uparse.quote(f"{airline} flight to {dest} {d_out}")
        book_url = f"https://www.google.com/search?q={q}"
        rows += (f"<tr style='background:{bg}'>"
                 f"<td style='padding:11px 13px;font-weight:{'700' if cheap else '400'};color:#1e293b'>{_html.escape(airline)}{tag}</td>"
                 f"<td style='padding:11px 13px;color:#374151'>{f.get('departure','?')}</td>"
                 f"<td style='padding:11px 13px;color:#374151'>{f.get('arrival','?')}</td>"
                 f"<td style='padding:11px 13px;color:#374151'>{f.get('duration','?')}</td>"
                 f"<td style='padding:11px 13px;text-align:center;color:#374151'>{f.get('stops',0)}</td>"
                 f"<td style='padding:11px 13px;color:#374151'>{f.get('cabin_class','Economy')}</td>"
                 f"<td style='padding:11px 13px;text-align:right;font-weight:700;"
                 f"color:{'#16a34a' if cheap else '#1e293b'}'>${p:,.0f}</td>"
                 f"<td style='padding:11px 13px;text-align:center'>"
                 f"<a class='book-link' href='{book_url}' target='_blank' rel='noopener' "
                 f"style='margin-top:0;padding:5px 12px'>Book</a></td></tr>")

    th = ("<tr style='background:#f8fafc'>" +
          "".join(f"<th style='padding:9px 13px;text-align:{a};color:#64748b;font-size:11px;"
                  f"font-weight:700;text-transform:uppercase;letter-spacing:.5px'>{h}</th>"
                  for h, a in [("Airline","left"),("Departs","left"),("Arrives","left"),
                                ("Duration","left"),("Stops","center"),("Class","left"),
                                ("Price","right"),("","center")])
          + "</tr>")

    html = f"""<div class="sec-card">
      <div class="sec-title">Flights <span class="cnt-pill">{len(flights)} options</span></div>
      <div style="overflow-x:auto">
        <table style="width:100%;border-collapse:collapse;font-size:13px">
          <thead>{th}</thead><tbody>{rows}</tbody>
        </table>
      </div>
    </div>"""
    return pn.Column(pn.pane.HTML(html, sizing_mode="stretch_width"), sizing_mode="stretch_width")


def _tab_hotels(r: dict) -> pn.Column:
    stays = r.get("stay_results") or []
    if not stays:
        return pn.Column(pn.pane.Alert("No hotel data available.", alert_type="warning"),
                         sizing_mode="stretch_width")

    dest      = r.get("destination", "")
    start_dt  = r.get("start_date", "")
    end_dt    = r.get("end_date", "")
    travelers = r.get("num_travelers", 1) or 1
    best      = min(range(len(stays)), key=lambda i: stays[i].get("price_per_night_usd", 9999))
    cards     = ""
    for i, h in enumerate(stays):
        bv     = i == best
        name   = _html.escape(h.get("name", "Hotel"))
        stars  = int(h.get("stars", 3))
        ppn    = h.get("price_per_night_usd", 0)
        total  = h.get("total_cost_usd", 0)
        nights = h.get("nights", 1)
        loc    = _html.escape(h.get("location", ""))
        ams    = h.get("amenities", [])
        rat    = float(h.get("rating", 0))

        star_html = "★" * min(stars, 5)
        chips     = "".join(f'<span class="chip">{_html.escape(a)}</span>' for a in ams[:4])
        loc_tag   = (f'<span style="background:#d0ebf8;color:#1e6e9e;padding:2px 8px;'
                     f'border-radius:6px;font-size:11px;font-weight:600">{loc}</span>'
                     if loc else "")
        q_hotel   = _uparse.quote(f"{h.get('name', '')} {dest}")
        book_url  = (f"https://www.booking.com/search.html"
                     f"?ss={q_hotel}"
                     f"&checkin={start_dt}&checkout={end_dt}"
                     f"&group_adults={travelers}")

        img_url = (h.get("photo_url") or "").strip()
        bv_badge  = ('<span style="position:absolute;top:10px;right:10px;'
                     'background:#22c55e;color:#fff;padding:3px 9px;border-radius:999px;'
                     'font-size:11px;font-weight:700;z-index:1">Best Value</span>'
                     if bv else "")

        img_tag = (
            f'<img class="card-img" src="{img_url}" alt="{name}" loading="lazy"'
            f' onerror="this.style.display=\'none\';this.nextElementSibling.style.display=\'flex\'">'
            if img_url else ""
        )
        fallback_display = "flex" if not img_url else "none"

        cards += f"""
        <div class="hotel-card {'bv' if bv else ''}" style="position:relative">
          {bv_badge}
          {img_tag}
          <div style="display:{fallback_display};width:100%;height:160px;align-items:center;justify-content:center;
                      background:linear-gradient(135deg,#e0e7ef,#c7d6e8);font-size:36px">&#127970;</div>
          <div class="hotel-card-body">
            <div class="h-name">{name} <span style="color:#f59e0b">{star_html}</span></div>
            <div style="margin:5px 0">{loc_tag}</div>
            <div style="display:flex;align-items:baseline;gap:6px;margin:8px 0 4px">
              <div class="h-price">${ppn:,.0f}<span>/night</span></div>
              <div style="font-size:12px;color:#94a3b8">· ${total:,.0f} total · {nights}n</div>
            </div>
            <div style="margin:6px 0 8px">{chips}</div>
            <div style="font-size:11px;color:#94a3b8;margin-bottom:3px">Rating: {rat}/5</div>
            <div class="rbar"><div class="rbar-fill" style="width:{int(rat/5*100)}%"></div></div>
            <a class="book-link" href="{book_url}" target="_blank" rel="noopener"
               style="margin-top:auto;padding-top:12px">Check Availability</a>
          </div>
        </div>"""

    html = f"""<div class="sec-card">
      <div class="sec-title">Hotels <span class="cnt-pill">{len(stays)} options</span></div>
      <div class="hotel-grid">{cards}</div>
    </div>"""
    return pn.Column(pn.pane.HTML(html, sizing_mode="stretch_width"), sizing_mode="stretch_width")


def _tab_activities(r: dict) -> pn.Column:
    acts = r.get("activity_results") or []
    if not acts:
        return pn.Column(pn.pane.Alert("No activity data available.", alert_type="warning"),
                         sizing_mode="stretch_width")

    dest  = r.get("destination", "")
    total = sum(a.get("price_usd", 0) for a in acts)
    cards = ""
    for a in acts:
        name = _html.escape(a.get("name", "Activity"))
        cat  = a.get("category", "Leisure")
        p    = a.get("price_usd", 0)
        dur  = a.get("duration", "?")
        rat  = float(a.get("rating", 4.5))
        desc = _html.escape(a.get("description", ""))
        bg, fg   = _CAT_ACT.get(cat, ("#f1f5f9", "#475569"))
        q_act    = _uparse.quote_plus(f"{a.get('name', '')} {dest}")
        book_url = f"https://www.getyourguide.com/s/?q={q_act}&searchSource=2"
        cards += f"""
        <div class="act-card">
          <div style="display:flex;justify-content:space-between;align-items:flex-start">
            <div class="act-name">{name}</div>
            <span class="badge" style="background:{bg};color:{fg};flex-shrink:0;margin-left:8px">{cat}</span>
          </div>
          <div class="act-meta" style="margin:5px 0">
            <b style="color:#1e293b;font-size:14px">${p:,.0f}</b>/person  ·  {dur}
          </div>
          <div style="margin:4px 0">{_stars(rat)}</div>
          <div style="font-size:12px;color:#94a3b8;line-height:1.4;margin-top:4px">{desc}</div>
          <a class="book-link" href="{book_url}" target="_blank" rel="noopener">Book on GetYourGuide</a>
        </div>"""

    html = f"""<div class="sec-card">
      <div class="sec-title">Activities <span class="cnt-pill">{len(acts)} activities</span></div>
      <div class="act-grid">{cards}</div>
      <div style="text-align:right;padding-top:12px;margin-top:4px;border-top:1px solid #f1f5f9;
                  font-size:14px;color:#64748b">
        Total: <b style="color:#1e293b;font-size:16px">${total:,.0f}</b>
      </div>
    </div>"""
    return pn.Column(pn.pane.HTML(html, sizing_mode="stretch_width"), sizing_mode="stretch_width")


def _tab_events(r: dict) -> pn.Column:
    events = r.get("event_results") or []
    dest   = r.get("destination", "")

    if not events:
        html = """<div class="sec-card">
          <div class="sec-title">Events</div>
          <div class="evt-empty">
            <div class="evt-empty-icon"></div>
            <div class="evt-empty-title">No events found</div>
            <div class="evt-empty-sub">
              Add event preferences in the sidebar and re-plan, or check local
              event calendars for your travel dates.
            </div>
          </div>
        </div>"""
        return pn.Column(pn.pane.HTML(html, sizing_mode="stretch_width"), sizing_mode="stretch_width")

    cards = ""
    for ev in events:
        name     = _html.escape(ev.get("name", "Event"))
        venue    = _html.escape(ev.get("venue", ""))
        addr     = _html.escape(ev.get("venue_address", ""))
        ev_date  = ev.get("date", "")
        ev_time  = ev.get("time", "")
        cat      = ev.get("category", "Other")
        p_min    = ev.get("price_min", 0)
        p_max    = ev.get("price_max", 0)
        url      = ev.get("url", "")
        desc     = _html.escape(ev.get("description", ""))
        nearby   = ev.get("nearby_hotels") or []

        bg, fg   = _CAT_EVT.get(cat, _CAT_EVT["Other"])
        if p_min == 0 and p_max == 0:
            price_str = "Free / TBD"
        elif p_max > 0:
            price_str = f"${p_min:.0f} – ${p_max:.0f}"
        else:
            price_str = f"${p_min:.0f}+"

        hotel_chips = "".join(
            f'<span class="evt-hotel-chip">{_html.escape(h)}</span>'
            for h in nearby[:3]
        )
        hotel_section = f"""
        <div class="evt-hotels">
          <div class="evt-hotel-lbl">Nearby Hotels for this Event</div>
          <div>{hotel_chips or '<span style="font-size:12px;color:#94a3b8">—</span>'}</div>
        </div>""" if nearby else ""

        if url:
            ticket_btn = f'<a class="evt-link" href="{url}" target="_blank" rel="noopener">Buy Tickets</a>'
        else:
            q_evt      = _uparse.quote(f"{ev.get('name', '')} {dest} tickets")
            ticket_btn = (f'<a class="evt-link" href="https://www.google.com/search?q={q_evt}" '
                          f'target="_blank" rel="noopener">Find Tickets</a>')

        cards += f"""
        <div class="evt-card">
          <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:6px">
            <div class="evt-name">{name}</div>
            <span class="badge" style="background:{bg};color:{fg};flex-shrink:0;margin-left:8px">{cat}</span>
          </div>
          <div class="evt-venue">{venue} {' — ' + addr if addr else ''}</div>
          <div class="evt-pills">
            {'<span class="evt-pill">' + ev_date + '</span>' if ev_date else ''}
            {'<span class="evt-pill">' + ev_time + '</span>' if ev_time else ''}
            <span class="evt-pill price">{price_str}</span>
          </div>
          {'<div class="evt-desc">' + desc + '</div>' if desc else ''}
          {hotel_section}
          {ticket_btn}
        </div>"""

    html = f"""<div class="sec-card">
      <div class="sec-title">Events During Your Stay <span class="cnt-pill">{len(events)} events</span></div>
      <div class="evt-grid">{cards}</div>
    </div>"""
    return pn.Column(pn.pane.HTML(html, sizing_mode="stretch_width"), sizing_mode="stretch_width")


def _tab_map(r: dict) -> pn.viewable.Viewable:
    """Interactive map using Bokeh's native tile rendering — no CDN, no script issues."""
    import math
    from bokeh.models import ColumnDataSource, HoverTool, TapTool, OpenURL, Legend, LegendItem
    from bokeh import plotting as bp

    dest      = r.get("destination", "")
    hotels    = r.get("stay_results") or []
    acts      = r.get("activity_results") or []
    events    = r.get("event_results") or []
    s_date    = r.get("start_date", "")
    e_date    = r.get("end_date", "")
    travelers = r.get("num_travelers", 1) or 1

    center = _geocode_city(dest)
    if not center:
        return pn.pane.HTML(
            '<div class="sec-card"><div class="sec-title">Map View</div>'
            '<div style="padding:40px;text-align:center;color:#94a3b8">'
            f'Could not locate "{_html.escape(dest)}" on the map. '
            'Check internet connection and re-plan.</div></div>',
            sizing_mode="stretch_width")

    clat, clng = center

    def _merc(lat: float, lon: float) -> tuple:
        k = 6378137.0
        return (lon * k * math.pi / 180,
                math.log(math.tan((90 + lat) * math.pi / 360)) * k)

    cx, cy = _merc(clat, clng)

    # ── Build one ColumnDataSource per category ───────────────────────────────
    def _empty_ds():
        return {"x": [], "y": [], "name": [], "sub": [], "price": [], "meta": [], "link": []}

    hd, ad, ed = _empty_ds(), _empty_ds(), _empty_ds()

    for h in hotels:
        name  = h.get("name", "Hotel")
        loc   = h.get("location", "")
        ppn   = h.get("price_per_night_usd", 0)
        rat   = h.get("rating", 0)
        stars = int(h.get("stars", 3))
        dlat, dlng = _map_jitter(name + "_H")
        mx, my = _merc(clat + dlat, clng + dlng)
        q    = _uparse.quote(f"{name} {dest}")
        link = (f"https://www.booking.com/search.html?ss={q}"
                f"&checkin={s_date}&checkout={e_date}&group_adults={travelers}")
        hd["x"].append(mx);  hd["y"].append(my)
        hd["name"].append(name)
        hd["sub"].append(("★" * stars + (f" · {loc}" if loc else "")))
        hd["price"].append(f"${ppn:,.0f}/night")
        hd["meta"].append(f"Rating: {rat}/5")
        hd["link"].append(link)

    for a in acts:
        name = a.get("name", "Activity")
        cat  = a.get("category", "Leisure")
        p    = a.get("price_usd", 0)
        rat  = a.get("rating", 4.5)
        dlat, dlng = _map_jitter(name + "_A")
        mx, my = _merc(clat + dlat, clng + dlng)
        q    = _uparse.quote_plus(f"{name} {dest}")
        link = f"https://www.getyourguide.com/s/?q={q}&searchSource=2"
        ad["x"].append(mx);  ad["y"].append(my)
        ad["name"].append(name);  ad["sub"].append(cat)
        ad["price"].append(f"${p:,.0f}/person")
        ad["meta"].append(f"Rating: {rat}/5")
        ad["link"].append(link)

    for ev in events:
        name    = ev.get("name", "Event")
        venue   = ev.get("venue", "")
        p_min   = ev.get("price_min", 0)
        p_max   = ev.get("price_max", 0)
        ev_date = ev.get("date", "")
        url     = ev.get("url", "")
        if not url:
            q_ev = _uparse.quote(f"{name} {dest} tickets")
            url  = f"https://www.google.com/search?q={q_ev}"
        dlat, dlng = _map_jitter(name + "_E")
        mx, my = _merc(clat + dlat, clng + dlng)
        pstr = (f"${p_min:.0f}–${p_max:.0f}" if p_max > 0
                else ("Free / TBD" if p_min == 0 else f"${p_min:.0f}+"))
        ed["x"].append(mx);  ed["y"].append(my)
        ed["name"].append(name);  ed["sub"].append(venue)
        ed["price"].append(pstr);  ed["meta"].append(ev_date)
        ed["link"].append(url)

    # ── Bokeh figure ──────────────────────────────────────────────────────────
    pad = 14_000
    fig = bp.figure(
        x_range=(cx - pad, cx + pad),
        y_range=(cy - pad, cy + pad),
        x_axis_type="mercator", y_axis_type="mercator",
        sizing_mode="stretch_width", height=500,
        toolbar_location="above",
        tools="pan,wheel_zoom,box_zoom,reset",
    )
    from bokeh.models import WMTSTileSource
    osm_tiles = WMTSTileSource(
        url="https://tile.openstreetmap.org/{Z}/{X}/{Y}.png",
        attribution="© OpenStreetMap contributors",
    )
    fig.add_tile(osm_tiles)
    fig.axis.visible      = False
    fig.grid.visible      = False
    fig.toolbar.logo      = None
    fig.outline_line_color = None

    def _tooltip(color: str) -> str:
        return f"""
<div style="padding:8px 10px;min-width:210px;
            font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif">
  <div style="font-weight:700;font-size:13px;color:#1e293b;margin-bottom:2px">@name</div>
  <div style="font-size:11px;color:#64748b;margin-bottom:5px">@sub</div>
  <div style="display:flex;justify-content:space-between;align-items:center">
    <span style="font-weight:700;color:{color}">@price</span>
    <span style="font-size:11px;color:#94a3b8">@meta</span>
  </div>
  <div style="margin-top:6px;font-size:10px;color:#94a3b8">Click marker to book</div>
</div>"""

    legend_items = []
    tap_renderers = []

    # Hotels — blue circles
    if hd["x"]:
        src = ColumnDataSource(hd)
        rnd = fig.scatter("x", "y", source=src, marker="circle", size=15,
                          color="#3b82f6", alpha=0.9,
                          line_color="white", line_width=2,
                          nonselection_alpha=0.4)
        fig.add_tools(HoverTool(renderers=[rnd], tooltips=_tooltip("#3b82f6")))
        legend_items.append(LegendItem(label="Hotels", renderers=[rnd]))
        tap_renderers.append(rnd)

    # Activities — green triangles
    if ad["x"]:
        src = ColumnDataSource(ad)
        rnd = fig.scatter("x", "y", source=src, marker="triangle", size=16,
                          color="#22c55e", alpha=0.9,
                          line_color="white", line_width=2,
                          nonselection_alpha=0.4)
        fig.add_tools(HoverTool(renderers=[rnd], tooltips=_tooltip("#22c55e")))
        legend_items.append(LegendItem(label="Activities", renderers=[rnd]))
        tap_renderers.append(rnd)

    # Events — amber diamonds
    if ed["x"]:
        src = ColumnDataSource(ed)
        rnd = fig.scatter("x", "y", source=src, marker="diamond", size=17,
                          color="#f59e0b", alpha=0.9,
                          line_color="white", line_width=2,
                          nonselection_alpha=0.4)
        fig.add_tools(HoverTool(renderers=[rnd], tooltips=_tooltip("#f59e0b")))
        legend_items.append(LegendItem(label="Events", renderers=[rnd]))
        tap_renderers.append(rnd)

    # Click a marker → open booking URL in new tab
    if tap_renderers:
        fig.add_tools(TapTool(renderers=tap_renderers,
                              callback=OpenURL(url="@link")))

    # Legend with click-to-hide layers
    if legend_items:
        legend = Legend(items=legend_items, click_policy="hide",
                        location="top_left",
                        label_text_font_size="11px",
                        label_text_color="#475569",
                        border_line_color="#e2e8f0",
                        background_fill_color="#ffffffdd",
                        padding=10, spacing=6)
        fig.add_layout(legend)

    n_pts = len(hd["x"]) + len(ad["x"]) + len(ed["x"])
    header = pn.pane.HTML(
        f'<div class="sec-card" style="padding:14px 20px 10px;margin-top:20px;'
        f'border-bottom-left-radius:0;border-bottom-right-radius:0;border-bottom:none">'
        f'<div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:8px">'
        f'<div class="sec-title" style="margin:0">Map View'
        f'<span class="cnt-pill" style="margin-left:8px">{n_pts} locations</span></div>'
        f'<div style="font-size:11px;color:#94a3b8">Click marker to open booking · '
        f'Click legend label to show/hide layer</div></div></div>',
        sizing_mode="stretch_width")

    map_pane = pn.pane.Bokeh(fig, sizing_mode="stretch_width")

    return pn.Column(
        header,
        pn.pane.HTML(
            '<div style="border:1px solid #f0f4f8;border-top:none;'
            'border-bottom-left-radius:18px;border-bottom-right-radius:18px;'
            'overflow:hidden;margin-bottom:8px">',
            sizing_mode="stretch_width", height=0, margin=0),
        map_pane,
        sizing_mode="stretch_width",
    )


def _tab_itinerary(r: dict) -> pn.Column:
    days = r.get("daily_itinerary") or []
    if not days:
        return pn.Column(pn.pane.Alert("No itinerary available.", alert_type="warning"),
                         sizing_mode="stretch_width")

    html = ""
    for d in days:
        n    = d.get("day", "?")
        dt   = d.get("date", "")
        mo   = _html.escape(d.get("morning", "—"))
        af   = _html.escape(d.get("afternoon", "—"))
        ev   = _html.escape(d.get("evening", "—"))
        din  = d.get("dining") or []
        note = _html.escape(d.get("notes", ""))

        din_html = ""
        for s in din[:3]:
            parts = s.split(":", 1)
            meal  = parts[0].strip() if len(parts) == 2 else "Meal"
            food  = parts[1].strip() if len(parts) == 2 else s
            din_html += (f'<div class="dining-item">'
                         f'<div class="dining-meal">{_html.escape(meal)}</div>'
                         f'<div>{_html.escape(food)}</div></div>')

        html += f"""
        <div class="day-card">
          <div class="day-hdr">
            <div>
              <div class="day-num">Day {n}</div>
              <div class="day-dt">{dt}</div>
            </div>
          </div>
          <div class="day-body">
            <div class="ts">
              <div class="ts-lbl"><div class="ts-name">AM</div></div>
              <div class="ts-body">{mo}</div>
            </div>
            <div class="ts">
              <div class="ts-lbl"><div class="ts-name">PM</div></div>
              <div class="ts-body">{af}</div>
            </div>
            <div class="ts">
              <div class="ts-lbl"><div class="ts-name">EVE</div></div>
              <div class="ts-body">{ev}</div>
            </div>
            {'<div class="dining-row">' + din_html + '</div>' if din_html else ''}
            {'<div class="notes">' + note + '</div>' if note else ''}
          </div>
        </div>"""

    return pn.Column(pn.pane.HTML(html, sizing_mode="stretch_width"), sizing_mode="stretch_width")


def _tab_restaurants(r: dict) -> pn.Column:
    restaurants = r.get("restaurant_results") or []
    dest        = r.get("destination", "")

    if not restaurants:
        html = """<div class="sec-card">
          <div class="sec-title">Restaurants</div>
          <div class="evt-empty">
            <div class="evt-empty-icon"></div>
            <div class="evt-empty-title">No restaurant data available</div>
            <div class="evt-empty-sub">Restaurant recommendations will appear here after planning.</div>
          </div>
        </div>"""
        return pn.Column(pn.pane.HTML(html, sizing_mode="stretch_width"), sizing_mode="stretch_width")

    _price_colors = {
        "$":    ("#dcfce7", "#166534"),
        "$$":   ("#fef9c3", "#854d0e"),
        "$$$":  ("#fef3c7", "#b45309"),
        "$$$$": ("#fee2e2", "#991b1b"),
    }

    cards = ""
    for i, rr in enumerate(restaurants):
        name      = _html.escape(rr.get("name", "Restaurant"))
        cuisine   = _html.escape(rr.get("cuisine", ""))
        price_lvl = rr.get("price_level", "$$")
        rating    = float(rr.get("rating", 4.0))
        address   = _html.escape(rr.get("address", ""))
        desc      = _html.escape(rr.get("description", ""))
        must_try  = _html.escape(rr.get("must_try", ""))
        bg, fg    = _price_colors.get(price_lvl, ("#f8fafc", "#475569"))

        q_rest    = _uparse.quote(f"{rr.get('name','')} {dest}")
        maps_url  = f"https://www.google.com/maps/search/{q_rest}"

        img_url = (rr.get("photo_url") or "").strip()

        rest_img_tag = (
            f'<img class="card-img" src="{img_url}" alt="{name}" loading="lazy"'
            f' onerror="this.style.display=\'none\';this.nextElementSibling.style.display=\'flex\'">'
            if img_url else ""
        )
        rest_fallback_display = "flex" if not img_url else "none"

        cards += f"""
        <div class="rest-card">
          {rest_img_tag}
          <div style="display:{rest_fallback_display};width:100%;height:160px;align-items:center;justify-content:center;
                      background:linear-gradient(135deg,#fef3c7,#fde68a);font-size:36px">&#127860;</div>
          <div class="rest-card-body">
            <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:4px">
              <div class="rest-name">{name}</div>
              <span class="badge" style="background:{bg};color:{fg};flex-shrink:0;margin-left:8px">{price_lvl}</span>
            </div>
            <div class="rest-cuisine">{cuisine}</div>
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">
              <div>{_stars(rating)}</div>
              {'<div style="font-size:11px;color:#94a3b8">' + address + '</div>' if address else ''}
            </div>
            {'<div style="font-size:12px;color:#64748b;line-height:1.4;margin-bottom:6px">' + desc + '</div>' if desc else ''}
            {'<div class="rest-must"><div class="rest-must-lbl">Must try</div>' + must_try + '</div>' if must_try else ''}
            <a class="book-link" href="{maps_url}" target="_blank" rel="noopener"
               style="margin-top:10px">View on Maps</a>
          </div>
        </div>"""

    html = f"""<div class="sec-card">
      <div class="sec-title">Restaurants <span class="cnt-pill">{len(restaurants)} places</span></div>
      <div class="rest-grid">{cards}</div>
    </div>"""
    return pn.Column(pn.pane.HTML(html, sizing_mode="stretch_width"), sizing_mode="stretch_width")


def _tab_visa(r: dict) -> pn.Column:
    visa = r.get("visa_info") or {}
    src  = _html.escape(r.get("source_city", "Your origin"))
    dest = _html.escape(r.get("destination", "destination"))

    if not visa:
        html = f"""<div class="sec-card">
          <div class="sec-title">Visa &amp; Entry Requirements</div>
          <div class="evt-empty">
            <div class="evt-empty-icon"></div>
            <div class="evt-empty-title">Visa information unavailable</div>
            <div class="evt-empty-sub">Enter your source city in the sidebar and re-plan
            to see visa requirements for {dest}.</div>
          </div>
        </div>"""
        return pn.Column(pn.pane.HTML(html, sizing_mode="stretch_width"), sizing_mode="stretch_width")

    req          = visa.get("requirement", "Unknown")
    visa_type    = visa.get("visa_type", "")
    proc_time    = visa.get("processing_time", "")
    validity     = visa.get("validity", "")
    cost_usd     = visa.get("cost_usd", 0)
    app_url      = visa.get("application_url", "")
    req_list     = visa.get("requirements_list") or []
    notes        = visa.get("notes", "")
    src_country  = _html.escape(visa.get("source_country", src))
    dest_country = _html.escape(visa.get("destination_country", dest))

    _badge = {
        "Visa Free":       'visa-badge-free',
        "Visa on Arrival": 'visa-badge-arrival',
        "Visa Required":   'visa-badge-req',
        "eTA Required":    'visa-badge-eta',
    }.get(req, 'visa-badge-req')

    def _row(label, val):
        if not val:
            return ""
        return (f'<div class="visa-row">'
                f'<div class="visa-row-lbl">{label}</div>'
                f'<div class="visa-row-val">{_html.escape(str(val))}</div>'
                f'</div>')

    req_items = "".join(
        f'<div class="visa-req-item"><div class="visa-check">&#10003;</div>'
        f'<div>{_html.escape(item)}</div></div>'
        for item in req_list
    )

    btn_html = ""
    if app_url and app_url.startswith("http"):
        btn_html = (f'<a class="book-link" href="{app_url}" target="_blank" rel="noopener" '
                    f'style="margin-top:16px;display:inline-flex">Apply Online</a>')

    html = f"""<div class="sec-card">
      <div class="sec-title">Visa &amp; Entry Requirements</div>
      <div style="display:flex;align-items:center;gap:16px;margin-bottom:20px;flex-wrap:wrap">
        <div style="font-size:18px;font-weight:800;color:#1e293b">
          {src_country} &rarr; {dest_country}
        </div>
        <span class="{_badge}">{_html.escape(req)}</span>
      </div>
      <div style="margin-bottom:20px">
        {_row("Visa Type",       visa_type)}
        {_row("Processing Time", proc_time)}
        {_row("Validity",        validity)}
        {_row("Cost",            f"${cost_usd:,.0f}" if cost_usd else "")}
      </div>
      {'<div class="sec-title" style="font-size:13px;margin-bottom:8px">Required Documents</div>' + req_items if req_items else ''}
      {'<div style="margin-top:16px;padding:12px 14px;background:#f0f8fe;border-radius:8px;border-left:3px solid #3aa7e8;font-size:13px;color:#1e6e9e;line-height:1.5">' + _html.escape(notes) + '</div>' if notes else ''}
      {btn_html}
    </div>"""
    return pn.Column(pn.pane.HTML(html, sizing_mode="stretch_width"), sizing_mode="stretch_width")


def _tab_transport(r: dict) -> pn.Column:
    transport = r.get("transport_info") or {}
    dest      = r.get("destination", "")

    if not transport:
        html = """<div class="sec-card">
          <div class="sec-title">Transportation &amp; Getting Around</div>
          <div class="evt-empty">
            <div class="evt-empty-icon"></div>
            <div class="evt-empty-title">No transport data available</div>
            <div class="evt-empty-sub">Transport information will appear here after planning.</div>
          </div>
        </div>"""
        return pn.Column(pn.pane.HTML(html, sizing_mode="stretch_width"), sizing_mode="stretch_width")

    airport_opts  = transport.get("airport_transfer") or []
    local_opts    = transport.get("local_transport") or []
    between_est   = transport.get("between_activities_estimate") or {}
    tips          = transport.get("tips") or []

    def _airport_card(opt):
        mode     = _html.escape(opt.get("mode", ""))
        desc     = _html.escape(opt.get("description", ""))
        cost     = opt.get("cost_usd", 0)
        duration = _html.escape(opt.get("duration", ""))
        freq     = _html.escape(opt.get("frequency", ""))
        tip      = _html.escape(opt.get("tips", ""))
        return f"""
        <div class="trans-card">
          <div>
            <div class="trans-mode">{mode}</div>
            <div class="trans-desc">{desc}</div>
            {'<div class="trans-duration">' + duration + (' &nbsp;·&nbsp; ' + freq if freq else '') + '</div>' if duration else ''}
            {'<div class="trans-tip">' + tip + '</div>' if tip else ''}
          </div>
          <div>
            <div class="trans-cost">${cost:,.0f}</div>
            <div class="trans-cost-note">per trip</div>
          </div>
        </div>"""

    def _local_card(opt):
        mode      = _html.escape(opt.get("mode", ""))
        pass_name = _html.escape(opt.get("pass_name", ""))
        daily     = opt.get("daily_cost_usd", 0)
        coverage  = _html.escape(opt.get("coverage", ""))
        tip       = _html.escape(opt.get("tips", ""))
        cost_str  = f"${daily:,.0f}/day" if daily else "Varies"
        return f"""
        <div class="trans-card">
          <div>
            <div class="trans-mode">{mode}{(' — ' + pass_name) if pass_name else ''}</div>
            {'<div class="trans-desc">' + coverage + '</div>' if coverage else ''}
            {'<div class="trans-tip">' + tip + '</div>' if tip else ''}
          </div>
          <div>
            <div class="trans-cost" style="font-size:14px">{cost_str}</div>
          </div>
        </div>"""

    airport_html = "".join(_airport_card(o) for o in airport_opts)
    local_html   = "".join(_local_card(o) for o in local_opts)

    between_html = ""
    if between_est:
        avg  = between_est.get("avg_ride_usd", 0)
        note = _html.escape(between_est.get("note", ""))
        between_html = f"""
        <div class="trans-card" style="background:#f0fdf4;border-color:#bbf7d0">
          <div>
            <div class="trans-mode">Between Activities (Uber/Taxi)</div>
            <div class="trans-desc">{note}</div>
          </div>
          <div>
            <div class="trans-cost" style="color:#16a34a">~${avg:,.0f}</div>
            <div class="trans-cost-note">avg ride</div>
          </div>
        </div>"""

    tip_items = "".join(
        f'<div class="tip-item"><div class="tip-dot"></div>{_html.escape(t)}</div>'
        for t in tips
    )

    html = f"""<div class="sec-card">
      <div class="sec-title">Transportation &amp; Getting Around</div>
      {'<div class="trans-section-title">Airport Transfers</div>' + airport_html if airport_html else ''}
      {'<div class="trans-section-title">Local Transport</div>' + local_html if local_html else ''}
      {between_html}
      {'<div class="trans-section-title">Tips</div>' + tip_items if tip_items else ''}
    </div>"""
    return pn.Column(pn.pane.HTML(html, sizing_mode="stretch_width"), sizing_mode="stretch_width")


def _wx_icon_emoji(icon: str) -> str:
    """Convert icon key to emoji for hourly forecast display."""
    return {
        "sunny":         "☀️",
        "cloudy":        "☁️",
        "partly-cloudy": "⛅",
        "rainy":         "🌧️",
        "stormy":        "⛈️",
        "snowy":         "🌨️",
        "windy":         "💨",
    }.get(icon, "🌤️")


def _tab_info(r: dict) -> pn.Column:
    fc   = r.get("food_culture_tips") or {}
    pack = r.get("packing_list") or []

    foods   = fc.get("must_try_foods") or []
    customs = fc.get("dining_customs", "")
    tipping = fc.get("tipping", "")
    ctips   = fc.get("cultural_tips") or []
    chips   = "".join(f'<span class="badge" style="background:#fff7ed;color:#c2410c;margin:3px">'
                      f'{_html.escape(f)}</span>' for f in foods)
    c_items = "".join(f'<div class="tip-item"><div class="tip-dot"></div>'
                      f'{_html.escape(t)}</div>' for t in ctips)

    food_html = f"""<div class="sec-card">
      <div class="sec-title">Food &amp; Culture</div>
      {'<div style="margin-bottom:12px"><div style="font-size:10px;color:#94a3b8;font-weight:700;text-transform:uppercase;letter-spacing:.5px;margin-bottom:6px">Must-try</div>' + chips + '</div>' if chips else ''}
      {'<div style="margin-bottom:8px"><b style="font-size:12px;color:#374151">Dining: </b><span style="font-size:13px;color:#64748b">' + _html.escape(customs) + '</span></div>' if customs else ''}
      {'<div style="margin-bottom:10px"><b style="font-size:12px;color:#374151">Tipping: </b><span style="font-size:13px;color:#64748b">' + _html.escape(tipping) + '</span></div>' if tipping else ''}
      {c_items}
    </div>"""

    cats: dict[str, list] = {}
    for item in pack:
        p = item.split(":", 1)
        c = p[0].strip() if len(p) == 2 else "Other"
        t = p[1].strip() if len(p) == 2 else item
        cats.setdefault(c, []).append(t)

    pack_inner = ""
    for cat, items in cats.items():
        pack_inner += f'<div class="pack-cat">{_html.escape(cat)}</div>'
        pack_inner += "".join(
            f'<div class="pack-item"><div class="pack-cb"></div>{_html.escape(it)}</div>'
            for it in items)

    pack_html = (f'<div class="sec-card"><div class="sec-title">Packing List '
                 f'<span class="cnt-pill">{len(pack)} items</span></div>'
                 f'<div class="pack-grid">{pack_inner}</div></div>'
                 if pack_inner else "")

    return pn.Column(
        pn.pane.HTML(
            food_html + pack_html,
            sizing_mode="stretch_width"
        ),
        sizing_mode="stretch_width",
    )


# ── App ───────────────────────────────────────────────────────────────────────

class VoyagerDashboard(param.Parameterized):
    _loading      = param.Boolean(default=False)
    _result       = param.Parameter(default=None)
    _error        = param.String(default="")
    _val_err      = param.String(default="")
    _chat_history = param.List(default=[])
    _chat_busy    = param.Boolean(default=False)
    _chat_open    = param.Boolean(default=False)

    def __init__(self, **params):
        super().__init__(**params)
        today     = date.today()
        tomorrow  = today + timedelta(days=1)
        next_week = today + timedelta(days=8)

        # ── Core trip inputs ──
        self.w_source   = pn.widgets.TextInput(name="Source City",    placeholder="e.g. New Delhi",       value="New Delhi")
        self.w_dest     = pn.widgets.TextInput(name="Destination",     placeholder="e.g. Tokyo, Japan",    value="")
        self.w_depart   = pn.widgets.DatePicker(name="Departure Date", value=tomorrow)
        self.w_return   = pn.widgets.DatePicker(name="Return Date",    value=next_week)
        self.w_travelers = pn.widgets.IntSlider(
            name="Number of Travelers", start=1, end=20, step=1, value=1,
        )

        self.w_budget = pn.widgets.IntSlider(
            name="Budget (USD)", start=500, end=30_000, step=100, value=3000,
        )
        self.w_budget_label = pn.pane.HTML(pn.bind(
            lambda v: f'<div class="budget-box"><div class="budget-box-lbl">Total Budget</div>'
                      f'<div class="budget-box-val">${v:,}</div></div>',
            self.w_budget,
        ))

        # ── Travel preferences ──
        self.w_travel_style = pn.widgets.RadioButtonGroup(
            name="Travel Style",
            options=["Budget", "Mid-range", "Luxury"],
            value="Mid-range",
            button_type="default",
        )
        self.w_trip_purpose = pn.widgets.Select(
            name="Trip Purpose",
            options=["Leisure", "Business", "Family", "Adventure", "Romantic", "Solo"],
            value="Leisure",
        )
        self.w_activities = pn.widgets.CheckBoxGroup(
            name="Preferred Activities",
            options=["Sightseeing", "Nature", "Food & Dining", "Shopping",
                     "Nightlife", "Cultural Experiences", "Outdoor Activities"],
            value=["Sightseeing", "Food & Dining"],
        )

        # ── Event preferences ──
        self.w_event_prefs = pn.widgets.CheckBoxGroup(
            name="Event Preferences",
            options=["Music", "Sports", "Arts & Theatre", "Comedy", "Family", "Film"],
            value=[],
        )

        # ── Plan button ──
        self.btn = pn.widgets.Button(
            name="Plan My Trip",
            button_type="primary",
            css_classes=["plan-btn"],
            sizing_mode="stretch_width",
        )
        self.btn.on_click(self._on_click)

        # ── Chat widgets ──
        self.w_chat_input = pn.widgets.TextInput(
            placeholder="Ask me about your trip, e.g. 'Suggest cheaper hotels'…",
            sizing_mode="stretch_width",
        )
        self.w_chat_send = pn.widgets.Button(
            name="Send ›",
            button_type="primary",
            css_classes=["chat-send-btn"],
            width=90,
        )
        self.w_chat_send.on_click(self._on_chat_send)

        # Quick action buttons
        _quick = [
            ("Cheaper Hotels",     "Suggest cheaper hotel alternatives for my trip"),
            ("More Adventure",     "Add more adventure activities to my itinerary"),
            ("Cut Costs 20%",      "How can I reduce my overall trip cost by about 20%?"),
            ("Luxury Upgrade",     "Create a luxury version of this trip with premium upgrades"),
        ]
        self._quick_btns = []
        for label, prompt in _quick:
            def _make_handler(p):
                def _handler(_):
                    self._on_chat_send(message=p)
                return _handler
            btn = pn.widgets.Button(
                name=label,
                css_classes=["quick-action-btn"],
                width=170,
            )
            btn.on_click(_make_handler(prompt))
            self._quick_btns.append(btn)

        self._chat_session = None

        # ── Floating chat toggle button ──
        self.btn_chat_toggle = pn.widgets.Button(
            name="💬",
            css_classes=["chat-float-btn"],
            width=64, height=64,
        )
        self.btn_chat_toggle.on_click(self._toggle_chat)

        # ── PDF export button (sidebar footer) ──
        self.btn_pdf = pn.widgets.FileDownload(
            label="Export PDF",
            callback=self._get_pdf_io,
            filename="voyager_trip_plan.pdf",
            css_classes=["pdf-btn"],
            sizing_mode="stretch_width",
        )

    # ── Sidebar ──────────────────────────────────────────────────────────────

    def sidebar(self) -> pn.Column:
        return pn.Column(
            pn.pane.HTML(
                '<div class="brand-area">'
                '<img class="brand-gif"'
                ' src="https://cdn.dribbble.com/userupload/22528296/file/original-f27441fc3124cb97104c1bf8d62c5bc5.gif"'
                ' alt="Voyager" loading="eager"/>'
                '<div class="brand-text">'
                '<div class="brand-name">Voyager</div>'
                '<div class="brand-tag">AI-Powered Trip Planner</div>'
                '</div>'
                '</div>'
            ),
            pn.layout.Divider(),

            # Core inputs
            self.w_source,
            self.w_dest,
            self.w_depart,
            self.w_return,
            self.w_travelers,
            pn.Spacer(height=4),
            self.w_budget_label,
            self.w_budget,

            # Travel preferences
            pn.pane.HTML('<div class="sidebar-sect">Travel Preferences</div>'),
            self.w_travel_style,
            pn.Spacer(height=6),
            self.w_trip_purpose,

            # Preferred activities
            pn.pane.HTML('<div class="sidebar-sect">Preferred Activities</div>'),
            self.w_activities,

            # Event preferences
            pn.pane.HTML('<div class="sidebar-sect">Event Preferences</div>'),
            self.w_event_prefs,

            pn.Spacer(height=10),
            pn.bind(
                lambda m: pn.pane.HTML(f'<div class="val-err">{m}</div>') if m else pn.Spacer(height=0),
                self.param._val_err,
            ),
            self.btn,

            pn.layout.Divider(),
            self.btn_pdf,

            css_classes=["sidebar-panel"],
            width=300,
            sizing_mode="fixed",
            scroll=True,
        )

    # ── Chat assistant ────────────────────────────────────────────────────────

    def _render_chat_html(self, history: list, busy: bool) -> str:
        if not history and not busy:
            return ('<div class="chat-empty">'
                    '<div>Ask me anything about your trip!</div>'
                    '</div>')
        msgs = ""
        for msg in history:
            content = (_html.escape(msg["content"])
                       .replace("\n", "<br>"))
            if msg["role"] == "user":
                msgs += f'<div class="msg-user">{content}</div>'
            else:
                msgs += f'<div class="msg-asst">{content}</div>'
        if busy:
            msgs += ('<div class="msg-typing">'
                     '<span></span><span></span><span></span></div>')
        return f'<div class="chat-box">{msgs}</div>'

    def _toggle_chat(self, _=None):
        self._chat_open = not self._chat_open
        if self._chat_open:
            self.btn_chat_toggle.css_classes = ["chat-float-btn", "chat-fab-open"]
            self.btn_chat_toggle.name = "✕"
        else:
            self.btn_chat_toggle.css_classes = ["chat-float-btn"]
            self.btn_chat_toggle.name = "💬"

    def _get_pdf_io(self):
        import io
        if self._result is None:
            buf = io.BytesIO(b"No trip plan generated yet. Please plan a trip first.")
            buf.seek(0)
            return buf
        try:
            from trip_planner.pdf_export import export_pdf_bytes
            return export_pdf_bytes(self._result)
        except Exception:
            traceback.print_exc()
            # Plain-text fallback
            buf = io.BytesIO()
            plan = (self._result.get("final_plan") or "No plan text available.").encode("utf-8", errors="replace")
            buf.write(plan)
            buf.seek(0)
            return buf

    def _build_chat_overlay(self) -> pn.Column:
        chat_view = pn.bind(
            lambda h, b: pn.pane.HTML(
                self._render_chat_html(h, b),
                sizing_mode="stretch_width",
                height=240,
            ),
            self.param._chat_history,
            self.param._chat_busy,
        )
        input_row = pn.Row(
            self.w_chat_input,
            self.w_chat_send,
            sizing_mode="stretch_width",
            margin=(0, 12, 12, 12),
        )
        quick_row1 = pn.Row(*self._quick_btns[:2], sizing_mode="stretch_width",
                            css_classes=["quick-row"], margin=(8, 12, 0, 12))
        quick_row2 = pn.Row(*self._quick_btns[2:], sizing_mode="stretch_width",
                            css_classes=["quick-row"], margin=(4, 12, 8, 12))

        return pn.Column(
            pn.pane.HTML("""
            <div style="display:flex;align-items:center;gap:10px;
                        padding:14px 16px 12px;border-bottom:1px solid #e2e8f0">
              <div style="width:32px;height:32px;background:linear-gradient(135deg,#3aa7e8,#2b8bbf);border-radius:8px;display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:700;color:#fff;flex-shrink:0">AI</div>
              <div>
                <div style="font-size:13px;font-weight:700;color:#1e293b">
                  AI Travel Assistant</div>
                <div style="font-size:11px;color:#64748b">
                  Ask anything about your trip</div>
              </div>
            </div>""", margin=0),
            quick_row1,
            quick_row2,
            chat_view,
            input_row,
            css_classes=["chat-overlay-panel"],
            sizing_mode="fixed",
            width=400,
            margin=0,
        )

    def _on_chat_send(self, event=None, message: str | None = None):
        q = (message or self.w_chat_input.value or "").strip()
        if not q or self._result is None:
            return
        self._chat_history = list(self._chat_history) + [{"role": "user", "content": q}]
        self.w_chat_input.value = ""
        self._chat_busy = True
        threading.Thread(target=self._run_chat, args=(q,), daemon=True).start()

    def _run_chat(self, q: str):
        try:
            if self._chat_session is None:
                self._chat_session = ChatSession(self._result)
            answer = self._chat_session.ask(q)
        except Exception as exc:
            traceback.print_exc()
            answer = f"Sorry, I couldn't answer that right now. ({exc})"
        finally:
            self._chat_history = list(self._chat_history) + [{"role": "assistant", "content": answer}]
            self._chat_busy = False

    # ── Results builder ───────────────────────────────────────────────────────

    def _build_results(self, r: dict) -> pn.Column:
        errs    = r.get("errors") or []
        err_col = pn.Column()
        for e in errs:
            err_col.append(pn.pane.Alert(f"{e}", alert_type="warning"))

        tabs = pn.Tabs(
            ("Overview",        _tab_overview(r)),
            ("Flights",         _tab_flights(r)),
            ("Hotels",          _tab_hotels(r)),
            ("Activities",      _tab_activities(r)),
            ("Transport",       _tab_transport(r)),
            ("Restaurants",     _tab_restaurants(r)),
            ("Events",          _tab_events(r)),
            ("Visa & Entry",    _tab_visa(r)),
            ("Itinerary",       _tab_itinerary(r)),
            ("Food & Packing",  _tab_info(r)),
            dynamic=True,
            sizing_mode="stretch_width",
        )
        return pn.Column(
            _hero(r, source_city=self.w_source.value),
            err_col,
            tabs,
            pn.pane.HTML(_tips_drawer_html(r), sizing_mode="stretch_width"),
            pn.pane.HTML(_guides_drawer_html(r), sizing_mode="stretch_width"),
            sizing_mode="stretch_width",
        )

    # ── Main render ───────────────────────────────────────────────────────────

    def main(self) -> pn.viewable.Viewable:
        return pn.bind(self._render, self.param._loading, self.param._result, self.param._error)

    def _render(self, loading, result, error) -> pn.viewable.Viewable:
        if error:
            return pn.Column(
                pn.pane.Alert(f"**Error:** {error}", alert_type="danger"),
                sizing_mode="stretch_width",
            )
        if loading:
            return pn.Column(
                pn.pane.HTML("""
                <div class="load-wrap">
                  
                  <div class="load-title">Planning your trip…</div>
                  <div class="load-sub">
                    8 AI agents are searching flights, hotels, activities, events, transport, visa &amp; restaurants in parallel
                  </div>
                  <div class="agent-cards">

                    <!-- Flights: plane rocks side-to-side -->
                    <div class="agent-card" style="--d:0s">
                      <div class="ac-icon">
                        <svg width="32" height="32" viewBox="0 0 40 40" fill="none">
                          <g class="ico-plane">
                            <rect x="8" y="17.5" width="24" height="5" rx="2.5" fill="#3aa7e8"/>
                            <path d="M16 20 L8 7 L13 9 L20 19 Z" fill="#3aa7e8"/>
                            <path d="M16 20 L8 33 L13 31 L20 21 Z" fill="#2b8bbf" opacity=".8"/>
                            <path d="M10 20 L7 15 L9 16 L11 19.5 Z" fill="#1e6e9e"/>
                            <path d="M10 20 L7 25 L9 24 L11 20.5 Z" fill="#1e6e9e" opacity=".75"/>
                            <ellipse cx="32" cy="20" rx="2.5" ry="2" fill="#1e6e9e" opacity=".7"/>
                          </g>
                        </svg>
                      </div>
                      <div class="ac-label">Flights</div>
                      <div class="ac-status">Searching…</div>
                      <div class="ac-bar"></div>
                    </div>

                    <!-- Hotels: windows blink in sequence -->
                    <div class="agent-card" style="--d:.35s">
                      <div class="ac-icon">
                        <svg width="32" height="32" viewBox="0 0 40 40" fill="none">
                          <rect x="10" y="10" width="20" height="26" rx="2" fill="#3aa7e8"/>
                          <rect x="8" y="8" width="24" height="6" rx="2" fill="#2b8bbf"/>
                          <rect class="win-a" x="13" y="17" width="5" height="4" rx="1" fill="#fff"/>
                          <rect class="win-b" x="22" y="17" width="5" height="4" rx="1" fill="#fff"/>
                          <rect class="win-c" x="13" y="24" width="5" height="4" rx="1" fill="#fff"/>
                          <rect class="win-d" x="22" y="24" width="5" height="4" rx="1" fill="#fff"/>
                          <rect x="17" y="29" width="6" height="7" rx="1" fill="#1e6e9e" opacity=".8"/>
                          <line x1="20" y1="8" x2="20" y2="4" stroke="#2b8bbf" stroke-width="1.5"/>
                          <circle cx="20" cy="3.5" r="1.2" fill="#3aa7e8"/>
                        </svg>
                      </div>
                      <div class="ac-label">Hotels</div>
                      <div class="ac-status">Comparing…</div>
                      <div class="ac-bar"></div>
                    </div>

                    <!-- Activities: compass needle spins -->
                    <div class="agent-card" style="--d:.7s">
                      <div class="ac-icon">
                        <svg width="32" height="32" viewBox="0 0 40 40" fill="none">
                          <circle cx="20" cy="20" r="16" stroke="#3aa7e8" stroke-width="2.5" fill="#eaf6fd"/>
                          <circle cx="20" cy="20" r="10" stroke="#d9eef9" stroke-width="1" fill="none"/>
                          <line x1="20" y1="5" x2="20" y2="9" stroke="#3aa7e8" stroke-width="2"/>
                          <line x1="20" y1="31" x2="20" y2="35" stroke="#3aa7e8" stroke-width="2"/>
                          <line x1="5" y1="20" x2="9" y2="20" stroke="#3aa7e8" stroke-width="2"/>
                          <line x1="31" y1="20" x2="35" y2="20" stroke="#3aa7e8" stroke-width="2"/>
                          <g class="ico-needle">
                            <path d="M20 20 L17.5 26 L20 8 L22.5 26 Z" fill="#3aa7e8"/>
                            <path d="M20 20 L22.5 14 L20 32 L17.5 14 Z" fill="#1e6e9e" opacity=".45"/>
                          </g>
                          <circle cx="20" cy="20" r="2.5" fill="#fff" stroke="#3aa7e8" stroke-width="1.5"/>
                        </svg>
                      </div>
                      <div class="ac-label">Activities</div>
                      <div class="ac-status">Exploring…</div>
                      <div class="ac-bar"></div>
                    </div>

                    <!-- Info: radar sweep rotates -->
                    <div class="agent-card" style="--d:1.05s">
                      <div class="ac-icon">
                        <svg width="32" height="32" viewBox="0 0 40 40" fill="none">
                          <circle cx="20" cy="20" r="16" stroke="#3aa7e8" stroke-width="2" fill="#eaf6fd"/>
                          <circle cx="20" cy="20" r="10" stroke="#d9eef9" stroke-width="1" fill="none"/>
                          <circle cx="20" cy="20" r="5" stroke="#d9eef9" stroke-width="1" fill="none"/>
                          <line x1="4" y1="20" x2="36" y2="20" stroke="#d9eef9" stroke-width="1"/>
                          <line x1="20" y1="4" x2="20" y2="36" stroke="#d9eef9" stroke-width="1"/>
                          <g class="ico-radar">
                            <path d="M20 20 L36 20 A16 16 0 0 0 20 4 Z" fill="#3aa7e8" opacity=".22"/>
                            <line x1="20" y1="20" x2="36" y2="20" stroke="#3aa7e8" stroke-width="2" opacity=".9"/>
                          </g>
                          <circle cx="27" cy="13" r="2" fill="#3aa7e8" opacity=".6"/>
                          <circle cx="20" cy="20" r="3" fill="#3aa7e8"/>
                        </svg>
                      </div>
                      <div class="ac-label">Info</div>
                      <div class="ac-status">Scanning…</div>
                      <div class="ac-bar"></div>
                    </div>

                    <!-- Events: calendar star pulses -->
                    <div class="agent-card" style="--d:1.4s">
                      <div class="ac-icon">
                        <svg width="32" height="32" viewBox="0 0 40 40" fill="none">
                          <rect x="6" y="10" width="28" height="25" rx="3" fill="#fff" stroke="#3aa7e8" stroke-width="2"/>
                          <rect x="6" y="10" width="28" height="9" rx="3" fill="#3aa7e8"/>
                          <rect x="13" y="7" width="3.5" height="6" rx="1.75" fill="#2b8bbf"/>
                          <rect x="23.5" y="7" width="3.5" height="6" rx="1.75" fill="#2b8bbf"/>
                          <line x1="11" y1="25" x2="29" y2="25" stroke="#d9eef9" stroke-width="1.5"/>
                          <line x1="11" y1="30" x2="22" y2="30" stroke="#d9eef9" stroke-width="1.5"/>
                          <g class="ico-star" transform="translate(26,23)">
                            <path d="M0-5 L1.5-1.5 L5 0 L1.5 1.5 L0 5 L-1.5 1.5 L-5 0 L-1.5-1.5 Z" fill="#f59e0b"/>
                          </g>
                        </svg>
                      </div>
                      <div class="ac-label">Events</div>
                      <div class="ac-status">Finding…</div>
                      <div class="ac-bar"></div>
                    </div>

                    <!-- Transport: bus/road icon -->
                    <div class="agent-card" style="--d:1.75s">
                      <div class="ac-icon">
                        <svg width="32" height="32" viewBox="0 0 40 40" fill="none">
                          <rect x="6" y="10" width="28" height="18" rx="4" fill="#3aa7e8"/>
                          <rect x="8" y="13" width="10" height="7" rx="2" fill="white" opacity=".85"/>
                          <rect x="22" y="13" width="10" height="7" rx="2" fill="white" opacity=".85"/>
                          <rect x="6" y="24" width="28" height="4" rx="2" fill="#2b8bbf"/>
                          <circle cx="12" cy="30" r="3.5" fill="#1e6e9e"/>
                          <circle cx="12" cy="30" r="1.5" fill="white"/>
                          <circle cx="28" cy="30" r="3.5" fill="#1e6e9e"/>
                          <circle cx="28" cy="30" r="1.5" fill="white"/>
                          <line x1="20" y1="10" x2="20" y2="28" stroke="#2b8bbf" stroke-width="1.5"/>
                        </svg>
                      </div>
                      <div class="ac-label">Transport</div>
                      <div class="ac-status">Mapping…</div>
                      <div class="ac-bar"></div>
                    </div>

                    <!-- Visa: passport icon -->
                    <div class="agent-card" style="--d:2.1s">
                      <div class="ac-icon">
                        <svg width="32" height="32" viewBox="0 0 40 40" fill="none">
                          <rect x="8" y="6" width="24" height="28" rx="3" fill="#3aa7e8"/>
                          <rect x="8" y="6" width="24" height="10" rx="3" fill="#2b8bbf"/>
                          <circle cx="20" cy="20" r="5" stroke="white" stroke-width="1.5" fill="none"/>
                          <line x1="20" y1="15" x2="20" y2="25" stroke="white" stroke-width="1.5"/>
                          <line x1="15" y1="20" x2="25" y2="20" stroke="white" stroke-width="1.5"/>
                          <rect x="11" y="28" width="8" height="2" rx="1" fill="white" opacity=".5"/>
                          <rect x="21" y="28" width="8" height="2" rx="1" fill="white" opacity=".5"/>
                        </svg>
                      </div>
                      <div class="ac-label">Visa</div>
                      <div class="ac-status">Checking…</div>
                      <div class="ac-bar"></div>
                    </div>

                    <!-- Restaurants: fork & knife icon -->
                    <div class="agent-card" style="--d:2.45s">
                      <div class="ac-icon">
                        <svg width="32" height="32" viewBox="0 0 40 40" fill="none">
                          <circle cx="20" cy="20" r="14" fill="#3aa7e8" opacity=".18"/>
                          <line x1="13" y1="8" x2="13" y2="32" stroke="#3aa7e8" stroke-width="2.5" stroke-linecap="round"/>
                          <path d="M10 8 Q10 16 13 18 Q16 16 16 8" stroke="#3aa7e8" stroke-width="2" fill="none" stroke-linecap="round"/>
                          <line x1="27" y1="8" x2="27" y2="32" stroke="#3aa7e8" stroke-width="2.5" stroke-linecap="round"/>
                          <path d="M24 8 L24 18 Q27 20 30 18 L30 8" stroke="#2b8bbf" stroke-width="1.8" fill="none" stroke-linecap="round" stroke-linejoin="round"/>
                        </svg>
                      </div>
                      <div class="ac-label">Restaurants</div>
                      <div class="ac-status">Discovering…</div>
                      <div class="ac-bar"></div>
                    </div>

                  </div>
                </div>"""),
                pn.indicators.LoadingSpinner(value=True, color="primary", width=48, height=48, align="center"),
                sizing_mode="stretch_width",
                align="center",
            )
        if result is None:
            return pn.Column(
                pn.pane.HTML("""
                <div class="welcome-wrap">

                  <!-- ── Decorative background ── -->
                  <svg xmlns="http://www.w3.org/2000/svg"
                       viewBox="0 0 1100 700" preserveAspectRatio="xMidYMid slice"
                       style="position:absolute;inset:0;width:100%;height:100%;pointer-events:none">

                    <!-- Globe rings (upper-right) -->
                    <circle cx="940" cy="95"  r="295" stroke="rgba(58,167,232,.07)" stroke-width="1.5" fill="none"/>
                    <circle cx="940" cy="95"  r="205" stroke="rgba(58,167,232,.06)" stroke-width="1.2" fill="none"/>
                    <circle cx="940" cy="95"  r="118" stroke="rgba(58,167,232,.07)" stroke-width="1"   fill="none"/>
                    <!-- Latitude arcs on globe -->
                    <path d="M645,95  Q792,52  940,95  Q1088,138 1236,95"  stroke="rgba(58,167,232,.07)" stroke-width="1" fill="none"/>
                    <path d="M658,175 Q799,145 940,175 Q1081,205 1222,175" stroke="rgba(58,167,232,.05)" stroke-width="1" fill="none"/>
                    <path d="M658,15  Q799,45  940,15  Q1081,-15 1222,15"  stroke="rgba(58,167,232,.05)" stroke-width="1" fill="none"/>
                    <!-- Meridian -->
                    <path d="M940,-200 Q912,52 940,95 Q968,138 940,390"   stroke="rgba(58,167,232,.05)" stroke-width="1" fill="none"/>

                    <!-- Second ambient ring (lower-left) -->
                    <circle cx="60"  cy="620" r="180" stroke="rgba(43,139,191,.06)" stroke-width="1.2" fill="none"/>
                    <circle cx="60"  cy="620" r="110" stroke="rgba(43,139,191,.05)" stroke-width="1"   fill="none"/>

                    <!-- ── Flight-path arcs (dashed) ── -->
                    <!-- Delhi → Paris -->
                    <path d="M148,530 C235,370 370,280 468,238" stroke="rgba(58,167,232,.26)" stroke-width="1.6" fill="none" stroke-dasharray="7,5"/>
                    <!-- Paris → Tokyo -->
                    <path d="M468,238 C588,196 718,202 846,218" stroke="rgba(58,167,232,.22)" stroke-width="1.6" fill="none" stroke-dasharray="7,5"/>
                    <!-- Delhi → Singapore -->
                    <path d="M148,530 C310,510 460,470 598,450" stroke="rgba(43,139,191,.18)" stroke-width="1.3" fill="none" stroke-dasharray="5,6"/>
                    <!-- Singapore → Tokyo -->
                    <path d="M598,450 C678,382 762,296 846,218" stroke="rgba(43,139,191,.16)" stroke-width="1.3" fill="none" stroke-dasharray="5,6"/>
                    <!-- NYC → London/Paris -->
                    <path d="M72,348 C180,264 320,222 468,238"  stroke="rgba(58,167,232,.14)" stroke-width="1.1" fill="none" stroke-dasharray="4,7"/>
                    <!-- Bali arc -->
                    <path d="M598,450 C640,500 700,520 730,510" stroke="rgba(43,139,191,.12)" stroke-width="1" fill="none" stroke-dasharray="4,6"/>

                    <!-- ── City dots (inner solid + outer pulse circle) ── -->
                    <!-- Delhi -->
                    <circle class="wbg-dot-outer" cx="148" cy="530" r="9"   fill="rgba(58,167,232,.14)"/>
                    <circle cx="148" cy="530" r="4.5" fill="rgba(58,167,232,.45)"/>
                    <!-- Paris -->
                    <circle class="wbg-dot-outer" cx="468" cy="238" r="9"   fill="rgba(58,167,232,.14)"/>
                    <circle cx="468" cy="238" r="4.5" fill="rgba(58,167,232,.45)"/>
                    <!-- Tokyo -->
                    <circle class="wbg-dot-outer" cx="846" cy="218" r="9"   fill="rgba(58,167,232,.14)"/>
                    <circle cx="846" cy="218" r="4.5" fill="rgba(58,167,232,.45)"/>
                    <!-- Singapore -->
                    <circle class="wbg-dot-outer" cx="598" cy="450" r="8"   fill="rgba(43,139,191,.12)"/>
                    <circle cx="598" cy="450" r="4"   fill="rgba(43,139,191,.38)"/>
                    <!-- NYC -->
                    <circle class="wbg-dot-outer" cx="72"  cy="348" r="8"   fill="rgba(58,167,232,.10)"/>
                    <circle cx="72"  cy="348" r="4"   fill="rgba(58,167,232,.32)"/>
                    <!-- Bali -->
                    <circle cx="730" cy="510" r="3.5" fill="rgba(43,139,191,.28)"/>

                    <!-- Tiny airplane on Paris→Tokyo arc -->
                    <g transform="translate(656,220) rotate(-6)" opacity=".22">
                      <ellipse cx="0" cy="0" rx="1.6" ry="9" fill="#3aa7e8"/>
                      <path d="M-1.6 1 L-8 5 L-8 6.5 L-1.6 2.5 Z" fill="#3aa7e8"/>
                      <path d="M1.6 1 L8 5 L8 6.5 L1.6 2.5 Z" fill="#3aa7e8"/>
                    </g>
                    <!-- Tiny airplane on Delhi→Paris arc -->
                    <g transform="translate(300,316) rotate(-32)" opacity=".18">
                      <ellipse cx="0" cy="0" rx="1.4" ry="7.5" fill="#2b8bbf"/>
                      <path d="M-1.4 1 L-7 4.5 L-7 5.8 L-1.4 2.2 Z" fill="#2b8bbf"/>
                      <path d="M1.4 1 L7 4.5 L7 5.8 L1.4 2.2 Z" fill="#2b8bbf"/>
                    </g>

                    <!-- Horizon wave (bottom) -->
                    <path d="M0,660 Q220,628 450,648 Q680,668 900,636 Q1020,620 1100,640"
                          stroke="rgba(58,167,232,.06)" stroke-width="1.2" fill="none"/>
                  </svg>

                  <!-- ── Content ── -->
                  <div style="position:relative;z-index:1;display:flex;flex-direction:column;align-items:center;gap:16px">
                    <div class="welcome-title">Where are you headed?</div>
                    <div class="welcome-sub">
                      Enter your destination, travel dates and budget — Voyager's AI agents will
                      plan flights, hotels, activities, local events, and a full day-by-day itinerary.
                    </div>
                    <div class="welcome-hint">
                      Try: <b>Tokyo</b>&nbsp; , &nbsp;<b>Paris</b>&nbsp; , &nbsp;<b>Chicago</b>&nbsp; , &nbsp;<b>Bali</b>
                    </div>
                  </div>

                </div>"""),
                sizing_mode="stretch_width",
            )
        return self._build_results(result)

    # ── Button handlers ───────────────────────────────────────────────────────

    def _on_click(self, _):
        dest   = self.w_dest.value.strip()
        dep    = self.w_depart.value
        ret    = self.w_return.value
        budget = self.w_budget.value
        errs   = []
        if not dest:
            errs.append("Destination is required.")
        if dep and ret and ret <= dep:
            errs.append("Return must be after departure.")
        if budget <= 0:
            errs.append("Budget must be > $0.")
        if errs:
            self._val_err = " ".join(errs)
            return
        self._val_err       = ""
        self._error         = ""
        self._result        = None
        self._chat_history  = []
        self._chat_session  = None
        self._loading       = True
        self.btn.disabled   = True
        self.btn.name       = "Planning..."
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        try:
            self._result = plan_trip(
                destination          = self.w_dest.value.strip(),
                start_date           = self.w_depart.value.isoformat(),
                end_date             = self.w_return.value.isoformat(),
                budget_usd           = float(self.w_budget.value),
                num_travelers        = int(self.w_travelers.value),
                travel_style         = self.w_travel_style.value,
                trip_purpose         = self.w_trip_purpose.value,
                preferred_activities = list(self.w_activities.value),
                event_preferences    = list(self.w_event_prefs.value),
                source_city          = self.w_source.value.strip() or "New Delhi, India",
            )
        except Exception as exc:
            traceback.print_exc()
            self._error = str(exc)
        finally:
            self._loading     = False
            self.btn.disabled = False
            self.btn.name     = "Plan My Trip"

    def view(self) -> pn.viewable.Viewable:
        def _maybe_overlay(is_open):
            if not is_open:
                return pn.pane.HTML("", margin=0, width=0, height=0)
            return self._build_chat_overlay()

        chat_overlay = pn.bind(_maybe_overlay, self.param._chat_open)

        fab = pn.Row(
            self.btn_chat_toggle,
            css_classes=["fab-wrap"],
            styles={"position": "fixed", "bottom": "30px", "right": "30px",
                    "z-index": "99999", "width": "64px", "height": "64px",
                    "overflow": "visible"},
            margin=0,
        )

        return pn.Column(
            pn.Row(
                self.sidebar(),
                pn.Column(self.main(), sizing_mode="stretch_width", margin=(20, 24)),
                sizing_mode="stretch_width",
            ),
            chat_overlay,
            fab,
            sizing_mode="stretch_width",
        )


# ── Serve ─────────────────────────────────────────────────────────────────────
dashboard = VoyagerDashboard()
app = dashboard.view()
app.servable(title="Voyager — AI Trip Planner")

if __name__ == "__main__":
    pn.serve(app, show=True, title="Voyager — AI Trip Planner")
