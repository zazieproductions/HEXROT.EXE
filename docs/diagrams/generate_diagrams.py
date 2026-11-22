#!/usr/bin/env python3
"""Generate the color-coded SVG diagrams used by README.md.

The diagrams are deterministic, dependency-free SVG. Run:

    python docs/diagrams/generate_diagrams.py

Palette semantics (also documented in the README legend):
  cyan   -> presentation / interface        green -> verified local facts
  purple -> deterministic transformation    amber -> evidence & interpretation
  red    -> execution, risk, hard limits    slate -> neutral structure
"""
from __future__ import annotations

import textwrap
from pathlib import Path

OUT = Path(__file__).resolve().parent

# ---------------------------------------------------------------------------
# Palette
# ---------------------------------------------------------------------------
BG = "#0A0F0C"
PANEL = "#101713"
PANEL_2 = "#131C17"
BORDER = "#26352C"
GRID = "#17211B"
TEXT = "#E9F2EB"
MUTED = "#97AA9C"
DIM = "#6C7F72"

RED = "#FF6B6B"
RED_DIM = "#3A1A1D"
AMBER = "#F2C14E"
AMBER_DIM = "#332A14"
GREEN = "#6EE7A8"
GREEN_DIM = "#123024"
CYAN = "#5AC8F5"
CYAN_DIM = "#0F2B36"
PURPLE = "#B99CFF"
PURPLE_DIM = "#241B3A"
SLATE = "#8FA3B0"
SLATE_DIM = "#1A242A"

FONT = "'IBM Plex Mono','DejaVu Sans Mono','SFMono-Regular',Menlo,monospace"


def esc(value: str) -> str:
    return (value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


def txt(x, y, s, size=12, fill=TEXT, weight=400, anchor="start", ls=0,
        opacity=1.0, italic=False):
    style = f' font-style="italic"' if italic else ""
    return (f'<text x="{x}" y="{y}" font-family="{FONT}" font-size="{size}" '
            f'font-weight="{weight}" fill="{fill}" text-anchor="{anchor}" '
            f'letter-spacing="{ls}" opacity="{opacity}"{style}>{esc(s)}</text>')


def rect(x, y, w, h, fill=PANEL, stroke=BORDER, rx=8, sw=1, dash=None, opacity=1.0):
    d = f' stroke-dasharray="{dash}"' if dash else ""
    return (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" '
            f'fill="{fill}" stroke="{stroke}" stroke-width="{sw}" opacity="{opacity}"{d}/>')


def line(x1, y1, x2, y2, stroke=BORDER, sw=1, dash=None, opacity=1):
    d = f' stroke-dasharray="{dash}"' if dash else ""
    return (f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{stroke}" '
            f'stroke-width="{sw}" opacity="{opacity}"{d}/>')


def path(d, stroke, sw=1.6, fill="none", dash=None, marker=True, opacity=1):
    m = ' marker-end="url(#arrow)"' if marker else ""
    da = f' stroke-dasharray="{dash}"' if dash else ""
    return (f'<path d="{d}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}" '
            f'opacity="{opacity}"{da}{m}/>')


def wrap(s, width_chars):
    out = []
    for para in s.split("\n"):
        out.extend(textwrap.wrap(para, width_chars) or [""])
    return out


def body(x, y, text, width, size=10.5, fill=MUTED, leading=15.5, max_lines=6):
    chars = max(8, int(width / (size * 0.603)))
    out = []
    for i, ln in enumerate(wrap(text, chars)[:max_lines]):
        out.append(txt(x, y + i * leading, ln, size=size, fill=fill))
    return "".join(out)


def card(x, y, w, h, color, title, desc="", kicker="", tag="", icon=""):
    s = [rect(x, y, w, h, PANEL, BORDER, 8),
         f'<rect x="{x}" y="{y}" width="4" height="{h}" rx="2" fill="{color}"/>']
    if kicker:
        s.append(txt(x + w - 14, y + 19, kicker.upper(), size=8, fill=DIM, anchor="end", ls=1.2))
    title_x = x + 18 + (12 if icon else 0)
    if icon:
        s.append(txt(x + 17, y + 23, icon, size=11, fill=color))
    s.append(txt(title_x, y + 24, title, size=12.5, weight=700, fill=TEXT, ls=.3))
    if desc:
        s.append(body(x + 18, y + 45, desc, w - 34, size=10, fill=MUTED, leading=14.5,
                      max_lines=max(1, int((h - 52) / 14.5))))
    if tag:
        tw = len(tag) * 5.6 + 18
        s.append(rect(x + 18, y + h - 24, tw, 16, color, color, 8, 0, opacity=.13))
        s.append(txt(x + 18 + tw / 2, y + h - 12.5, tag.upper(), size=7.8, fill=color,
                     anchor="middle", ls=.8))
    return "".join(s)


def chip(x, y, w, h, color, label, sub="", align="center"):
    s = [rect(x, y, w, h, PANEL_2, BORDER, 6)]
    if align == "center":
        s.append(txt(x + w / 2, y + h / 2 + (0 if not sub else -3), label, size=10,
                     fill=TEXT, weight=600, anchor="middle", ls=.4))
        if sub:
            s.append(txt(x + w / 2, y + h / 2 + 12, sub, size=7.5, fill=DIM,
                         anchor="middle", ls=.5))
    else:
        s.append(f'<circle cx="{x + 16}" cy="{y + h / 2}" r="3.5" fill="{color}"/>')
        s.append(txt(x + 28, y + h / 2 + (0 if not sub else -2), label, size=10,
                     fill=TEXT, weight=600))
        if sub:
            s.append(txt(x + 28, y + h / 2 + 12, sub, size=7.5, fill=DIM))
    return "".join(s)


def zone(x, y, w, h, color, index, title, subtitle=""):
    s = [rect(x, y, w, h, "#0C120E", BORDER, 12, 1, dash="4 5"),
         f'<rect x="{x}" y="{y}" width="{w}" height="1.5" rx="1" fill="{color}" opacity=".55"/>',
         f'<rect x="{x + 18}" y="{y + 16}" width="3" height="20" rx="1.5" fill="{color}"/>',
         txt(x + 30, y + 32, f"{index}", size=10, fill=color, weight=700, ls=2),
         txt(x + 58, y + 32, title, size=12.5, fill=TEXT, weight=700, ls=1.6)]
    if subtitle:
        s.append(txt(x + w - 18, y + 32, subtitle.upper(), size=8.5, fill=DIM,
                     anchor="end", ls=1.4))
    return "".join(s)


def arrow(x1, y1, x2, y2, color="#5A6E60", sw=1.6):
    return (f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" '
            f'stroke-width="{sw}" marker-end="url(#arrow)"/>')


def arrow_label(x, y, w, label, color=DIM, size=8.5):
    return (rect(x - w / 2, y - 11, w, 20, BG, BG, 4, 0) +
            txt(x, y + 2, label, size=size, fill=color, anchor="middle", ls=.6))


def defs(accent=RED):
    return f'''<defs>
<pattern id="grid" width="28" height="28" patternUnits="userSpaceOnUse">
  <path d="M28 0H0V28" fill="none" stroke="{GRID}" stroke-width="1"/>
</pattern>
<radialGradient id="glow" cx="16%" cy="12%" r="80%">
  <stop offset="0%" stop-color="{accent}" stop-opacity=".16"/>
  <stop offset="55%" stop-color="{accent}" stop-opacity=".03"/>
  <stop offset="100%" stop-color="{accent}" stop-opacity="0"/>
</radialGradient>
<radialGradient id="glow2" cx="88%" cy="8%" r="60%">
  <stop offset="0%" stop-color="{CYAN}" stop-opacity=".12"/>
  <stop offset="100%" stop-color="{CYAN}" stop-opacity="0"/>
</radialGradient>
<marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
  <path d="M0 0L10 5L0 10z" fill="#5A6E60"/>
</marker>
<filter id="soft" x="-20%" y="-20%" width="140%" height="140%">
  <feDropShadow dx="0" dy="10" stdDeviation="14" flood-color="#000" flood-opacity=".45"/>
</filter>
</defs>'''


def document(w, h, body_svg, accent=RED, title="HEXROT.EXE diagram"):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
            f'viewBox="0 0 {w} {h}" role="img" aria-label="{esc(title)}">'
            f'{defs(accent)}<rect width="{w}" height="{h}" fill="{BG}"/>'
            f'<rect width="{w}" height="{h}" fill="url(#grid)" opacity=".55"/>'
            f'<rect width="{w}" height="{h}" fill="url(#glow)"/>'
            f'<rect width="{w}" height="{h}" fill="url(#glow2)"/>'
            f'{body_svg}</svg>\n')


# ---------------------------------------------------------------------------
# 1. Hero
# ---------------------------------------------------------------------------
def hero():
    s = []
    s.append(txt(70, 60, "▚ CHURCH OF MALWARE  //  AUDIO RESEARCH DIVISION", size=10.5,
                 fill=AMBER, weight=600, ls=2.2))
    s.append(txt(70, 110, "AUTHORIZED RESEARCH INSTRUMENT", size=9, fill=DIM, ls=2))
    s.append(f'<text x="66" y="206" font-family="{FONT}" font-size="76" font-weight="700" fill="{TEXT}" letter-spacing="1">HEXROT<tspan fill="{RED}">.EXE</tspan></text>')
    s.append(txt(70, 246, "CORRUPT THE FORMAT.  EXPOSE THE FAULT.", size=17.5, fill=CYAN,
                 weight=700, ls=3.2))
    s.append(body(70, 280, "Local-first audio-format research workstation. Parse real bytes, generate seeded "
                           "malformed variants, run allowlisted decoders inside an OS sandbox, compare observed "
                           "outcomes, and preserve reproducible evidence.", 610, size=11, leading=17, max_lines=3))
    chips = [("v0.2.0", RED), ("16 STRATEGIES", PURPLE), ("3 DECODERS", AMBER),
             ("58 TESTS", GREEN), ("MIT", CYAN)]
    x = 70
    for label, color in chips:
        w = len(label) * 7.4 + 26
        s.append(rect(x, 340, w, 26, PANEL, BORDER, 5))
        s.append(f'<circle cx="{x + 13}" cy="353" r="3" fill="{color}"/>')
        s.append(txt(x + 22, 357, label, size=9, fill=MUTED, weight=600, ls=.8))
        x += w + 9

    # pipeline grid
    px, py, pw, ph = 740, 64, 610, 240
    s.append(rect(px, py, pw, ph, "#0C120E", BORDER, 12, 1, dash="5 6"))
    s.append(txt(px + 20, py + 28, "EVIDENCE PIPELINE", size=9.5, fill=DIM, ls=2.2))
    s.append(txt(px + pw - 20, py + 28, "01 → 06", size=9, fill=RED, anchor="end", ls=1.5))
    stages = [("01", "IMPORT", "real bytes", CYAN), ("02", "PARSE", "structure + hash", GREEN),
              ("03", "MUTATE", "seeded edits", PURPLE), ("04", "DECODE", "sandboxed", RED),
              ("05", "COMPARE", "observed only", AMBER), ("06", "EXPORT", "JSON/MD/HTML", CYAN)]
    for i, (num, name, sub, color) in enumerate(stages):
        cx = px + 20 + (i % 3) * 192
        cy = py + 48 + (i // 3) * 92
        s.append(rect(cx, cy, 180, 74, PANEL, BORDER, 8))
        s.append(f'<rect x="{cx}" y="{cy}" width="3" height="74" rx="1.5" fill="{color}"/>')
        s.append(txt(cx + 14, cy + 20, num, size=8, fill=color, weight=700, ls=1.4))
        s.append(txt(cx + 14, cy + 40, name, size=12, fill=TEXT, weight=700, ls=.6))
        s.append(txt(cx + 14, cy + 58, sub, size=8.5, fill=DIM))
        if i % 3 < 2:
            s.append(arrow(cx + 180, cy + 37, cx + 192, cy + 37, "#3C4B41", 1.2))
    s.append(rect(px, py + ph + 18, pw, 48, PANEL, BORDER, 9))
    s.append(f'<circle cx="{px + 24}" cy="{py + ph + 42}" r="4" fill="{GREEN}"/>')
    s.append(txt(px + 38, py + ph + 39, "LOCAL ENGINE", size=9.5, fill=TEXT, weight=700, ls=1))
    s.append(txt(px + 38, py + ph + 52, "sandbox-gated · zero network · no cloud upload", size=8.5, fill=DIM))
    s.append(txt(px + pw - 20, py + ph + 46, "~/.hexrot", size=9, fill=AMBER, anchor="end"))

    s.append(line(70, 400, 1330, 400, BORDER))
    s.append(txt(70, 426, "AUTHORIZED RESEARCH ONLY  ·  NOT AN EXPLOIT TOOL", size=8.5, fill=DIM, ls=1.6))
    s.append(txt(1330, 426, "README / 2026-11", size=8.5, fill=DIM, anchor="end", ls=1.6))
    return document(1400, 450, "".join(s), RED, "HEXROT.EXE — corrupt the format, expose the fault")


# ---------------------------------------------------------------------------
# 2. Architecture
# ---------------------------------------------------------------------------
def architecture():
    s = []
    s.append(txt(40, 40, "HEXROT.EXE  //  SYSTEM ARCHITECTURE", size=14, fill=TEXT, weight=700, ls=1.8))
    s.append(txt(40, 58, "Four planes. One trust boundary. No simulated evidence.", size=9.5, fill=DIM))
    legend = [(CYAN, "presentation"), (GREEN, "verified facts"), (PURPLE, "transformation"),
              (AMBER, "evidence"), (RED, "execution / risk")]
    lx = 1400
    for color, label in reversed(legend):
        tw = len(label) * 5.2 + 16
        lx -= tw
        s.append(f'<circle cx="{lx + 5}" cy="42" r="3.5" fill="{color}"/>')
        s.append(txt(lx + 13, 46, label, size=8, fill=DIM))
        lx -= 10
    s.append(line(40, 72, 1400, 72, BORDER))

    # Zone 1
    s.append(zone(40, 88, 1360, 208, CYAN, "01", "PRESENTATION — BROWSER",
                  "React 19 · Vite 7 · TypeScript strict"))
    s.append(card(62, 138, 372, 136, CYAN, "SINGLE-PAGE WORKSTATION",
                  "Seven modules share one workspace hook. File content is rendered as text and hex, never HTML.\n"
                  "Browser-only fallback parses a bounded RIFF/AIFF subset in memory.", kicker="display only"))
    mods = [("AUTOPSY", "structure + hex", GREEN), ("METADATA", "tags + offsets", GREEN),
            ("MUTATOR", "seeded variants", PURPLE), ("DECODER LAB", "sandbox status", RED),
            ("DIFFERENTIAL", "comparison matrix", AMBER), ("CRASH VAULT", "triage records", RED),
            ("EVIDENCE", "export bundle", AMBER), ("STATUS BAR", "engine + isolation", CYAN)]
    for i, (name, sub, color) in enumerate(mods):
        mx = 454 + (i % 4) * 232
        my = 138 + (i // 4) * 74
        s.append(chip(mx, my, 216, 62, color, name, sub, align="left"))
        s.append(f'<rect x="{mx}" y="{my}" width="216" height="2" fill="{color}" opacity=".5"/>')
    s.append(txt(1198, 288, "7 MODULES  /  1 WORKSPACE HOOK", size=7.8, fill=DIM, anchor="end", ls=1))

    # arrow 1
    s.append(arrow(720, 296, 720, 330, "#3C4B41", 1.4))
    s.append(arrow_label(720, 315, 520, "JSON over loopback · Host + Origin enforced · no remote binding", CYAN, 8))

    # Zone 2
    s.append(zone(40, 336, 1360, 220, GREEN, "02", "LOCAL API — LOOPBACK ONLY",
                  "FastAPI · port 8000 · no authentication"))
    s.append(card(62, 386, 338, 146, GREEN, "REQUEST GUARD",
                  "Loopback Host, client, and origin are checked before routing. Uploads spool to disk without a size cap. Two methods: GET and POST.", kicker="middleware"))
    s.append(card(418, 386, 552, 146, GREEN, "ROUTER · /api",
                  "sessions · demo · upload · files/{id}/bytes · compare · download · media\n"
                  "sessions/{id}/mutations · jobs · differential · runs/{id}/triage · report", kicker="16 endpoints"))
    s.append(card(988, 386, 390, 146, AMBER, "JOB MANAGER",
                  "Threads one decoder job at a time. Progress counts completed process executions. Startup marks stale jobs interrupted.", kicker="single flight"))

    s.append(arrow(720, 556, 720, 590, "#3C4B41", 1.4))
    s.append(arrow_label(720, 575, 460, "session IDs + file IDs only · callers never supply paths", GREEN, 8))

    # Zone 3
    s.append(zone(40, 596, 1360, 300, PURPLE, "03", "CORE — IN-PROCESS, UNPRIVILEGED",
                  "stdlib parsers · Mutagen · SQLite · reports"))
    s.append(card(62, 648, 418, 108, GREEN, "BOUNDED PARSERS",
                  "RIFF/WAVE · AIFF/AIFC · FLAC metadata blocks · MP3/ID3v1+v2. 4096-chunk and 4096-char bounds.", kicker="facts w/ offsets"))
    s.append(card(496, 648, 418, 108, GREEN, "METADATA EXTRACTION",
                  "Raw INFO/AIFF/ID3 fields with byte offsets; Mutagen supplements tags, properties, artwork hashes.", kicker="facts + heuristics"))
    s.append(card(930, 648, 448, 108, PURPLE, "MUTATION ENGINE",
                  "16 seeded strategies, exact edit offsets, before/after SHA-256, deduplication, replay manifest.", kicker="deterministic"))
    s.append(card(62, 770, 418, 100, CYAN, "STORAGE",
                  "SQLite WAL index; UUID file names; dirs 0700, files 0600; default ~/.hexrot.", kicker="session-scoped"))
    s.append(card(496, 770, 418, 100, AMBER, "DIFFERENTIAL",
                  "Accept/reject matrix, channels, duration, decoded hashes, repeat consistency, resource flags.", kicker="observed only"))
    s.append(card(930, 770, 448, 100, AMBER, "EVIDENCE EXPORT",
                  "JSON is canonical; Markdown and escaped HTML render from it. Workspace paths redacted.", kicker="schema v1"))

    s.append(arrow(720, 896, 720, 930, "#3C4B41", 1.4))
    s.append(arrow_label(720, 915, 520, "fixed argv · one read-only input · no shell · self-test gates execution", RED, 8))

    # Zone 4
    s.append(zone(40, 936, 1360, 170, RED, "04", "OS SANDBOX — DENY BY DEFAULT",
                  "one decoder process tree at a time"))
    s.append(card(62, 982, 400, 104, GREEN, "SUPERVISOR",
                  "Inside the sandbox; preserves true wait status. Sets RLIMIT_CPU/AS/FSIZE/NOFILE/CORE before exec. Caps stdout and stderr at 64 KiB each.", kicker="in-sandbox"))
    s.append(card(478, 982, 430, 104, RED, "BUBBLEWRAP / SANDBOX-EXEC",
                  "Linux: unshare-all + netns, no host home, read-only system dirs, 16 MiB tmpfs. macOS: deny-by-default Seatbelt. Self-test failure disables jobs.", kicker="self-tested"))
    s.append(card(924, 982, 454, 104, AMBER, "DECODERS",
                  "ffmpeg · ffprobe · sndfile-info. Fixed allowlist. ffmpeg emits decoded-output SHA-256; sndfile-info can exit 0 on rejection.", kicker="argv only"))

    s.append(txt(40, 1130, "⚠  Shared kernel, not a disposable VM. The macOS Seatbelt profile is experimental and unverified on Apple Silicon.", size=8.5, fill=AMBER))
    s.append(txt(1400, 1130, "diagram: docs/diagrams/architecture.svg", size=8, fill=DIM, anchor="end"))
    return document(1440, 1150, "".join(s), PURPLE, "HEXROT.EXE architecture")


# ---------------------------------------------------------------------------
# 3. Workflow
# ---------------------------------------------------------------------------
def workflow():
    s = []
    s.append(txt(70, 42, "THE EVIDENCE PIPELINE", size=14, fill=TEXT, weight=700, ls=1.8))
    s.append(txt(70, 62, "Eight stages from raw bytes to a reopenable evidence bundle.", size=9.5, fill=DIM))
    s.append(txt(1370, 50, "DOCS / REPRODUCIBLE WORKFLOW", size=8, fill=DIM, anchor="end", ls=1.5))
    s.append(line(70, 78, 1370, 78, BORDER))

    stages = [
        ("01", "IMPORT", CYAN, "Real file bytes, not a sample record.",
         "Import File → POST /sessions/upload or POST /sessions/demo.", "session + original"),
        ("02", "AUTOPSY", GREEN, "Identify container, chunks, declared vs actual lengths.",
         "SHA-256, magic bytes, chunk map, extension mismatch, warnings.", "structure + hash"),
        ("03", "METADATA", GREEN, "Extract tags without executing their content.",
         "Raw offsets from parsers; Mutagen supplementary; heuristics labeled.", "fields + artwork"),
        ("04", "MUTATE", PURPLE, "Apply seeded edits to a copy of the original.",
         "Pick strategy or default cycle; count, seed, region, limits.", "variant files + edits"),
        ("05", "DECODE", RED, "Execute allowlisted tools inside the OS sandbox.",
         "Self-test → supervisor → rlimits → process; collect stdout/stderr.", "runs + exit status"),
        ("06", "COMPARE", AMBER, "Diff observed acceptance and reported properties.",
         "Matrix per file × decoder; channels, duration, decoded SHA-256, repeats.", "findings"),
        ("07", "TRIAGE", RED, "Rerun a real signal termination and test the original.",
         "Two repeats, baseline original, then single-edit-drop analysis (max 20 edits).", "reproduction record"),
        ("08", "EXPORT", CYAN, "Preserve the session as portable evidence.",
         "JSON canonical; Markdown; escaped self-contained HTML; reopen SQLite.", "bundle"),
    ]
    pos = []
    for i, (num, name, color, desc, detail, output) in enumerate(stages):
        col, row = i % 4, i // 4
        x = 70 + col * 326
        y = 110 + row * 238
        pos.append((x, y))
        s.append(rect(x, y, 302, 196, PANEL, BORDER, 10))
        s.append(f'<rect x="{x}" y="{y}" width="302" height="4" rx="2" fill="{color}"/>')
        s.append(f'<circle cx="{x + 30}" cy="{y + 38}" r="16" fill="{color}" opacity=".14"/>')
        s.append(txt(x + 30, y + 43, num, size=10, fill=color, weight=700, anchor="middle", ls=.5))
        s.append(txt(x + 56, y + 39, name, size=13, fill=TEXT, weight=700, ls=1))
        s.append(body(x + 18, y + 68, desc, 266, size=10, fill=MUTED, leading=14.5, max_lines=2))
        s.append(line(x + 18, y + 104, x + 284, y + 104, BORDER))
        s.append(body(x + 18, y + 121, detail, 266, size=8.8, fill=DIM, leading=13.2, max_lines=3))
        s.append(rect(x + 18, y + 166, 266, 20, PANEL_2, BORDER, 4))
        s.append(txt(x + 28, y + 180, "OUT →", size=7.2, fill=color, weight=700, ls=1))
        s.append(txt(x + 62, y + 180, output.upper(), size=7.6, fill=MUTED, ls=.5))
        if col < 3:
            s.append(arrow(x + 302, y + 98, x + 326, y + 98, "#3C4B41", 1.3))

    # re-mutation loop: triage feeds a new seeded pass
    s.append(path("M 873 348 L 873 324 L 1199 324 L 1199 312", PURPLE, 1.3, dash="5 5"))
    s.append(arrow_label(1030, 318, 180, "RE-MUTATE WITH A NEW SEED", PURPLE, 7.4))

    s.append(rect(70, 570, 1300, 54, PANEL_2, BORDER, 8))
    s.append(txt(90, 593, "REPRODUCE A VARIANT →", size=8, fill=PURPLE, weight=700, ls=.9))
    s.append(txt(246, 593, "reuse the original SHA-256, seed, strategy, index, region, size limit and metadata limit recorded in reproduction_inputs.", size=8.2, fill=MUTED))
    s.append(txt(90, 609, "No simulation, no cloud round-trip: the same local generator and the same original bytes produce the same output.", size=7.6, fill=DIM))

    s.append(rect(70, 650, 1300, 70, PANEL, BORDER, 8))
    notes = [(GREEN, "ORIGINAL IS NEVER MODIFIED", "every variant is written to a new UUID file"),
             (PURPLE, "SAME INPUTS → SAME BYTES", "seed + strategy + index + original SHA-256"),
             (AMBER, "A CRASH ≠ EXPLOIT", "signals and rejections are observations, not verdicts"),
             (RED, "ONE JOB AT A TIME", "cancel terminates the active process group")]
    for i, (color, title, sub) in enumerate(notes):
        nx = 88 + i * 322
        s.append(f'<circle cx="{nx + 4}" cy="676" r="3.5" fill="{color}"/>')
        s.append(txt(nx + 16, 680, title, size=8.6, fill=TEXT, weight=700, ls=.7))
        s.append(txt(nx + 16, 695, sub, size=7.8, fill=DIM))
    return document(1440, 750, "".join(s), AMBER, "HEXROT.EXE evidence pipeline")


# ---------------------------------------------------------------------------
# 4. Trust boundary
# ---------------------------------------------------------------------------
def trust():
    s = []
    s.append(txt(60, 42, "TRUST BOUNDARY", size=14, fill=TEXT, weight=700, ls=1.8))
    s.append(txt(60, 62, "What the sandbox changes — and what it deliberately does not protect.", size=9.5, fill=DIM))
    s.append(txt(1380, 50, "DOCS / SECURITY.md", size=8, fill=DIM, anchor="end", ls=1.5))
    s.append(line(60, 78, 1380, 78, BORDER))

    # host
    s.append(rect(60, 100, 620, 350, "#0E1310", AMBER, 12, 1.2))
    s.append(f'<rect x="60" y="100" width="620" height="4" rx="2" fill="{AMBER}"/>')
    s.append(txt(82, 130, "HOST PROCESS", size=13, fill=TEXT, weight=700, ls=1.2))
    s.append(txt(82, 148, "runs as your user · same kernel · same account", size=8.5, fill=AMBER))
    host_items = [
        ("BACKEND CORE", "stdlib parsers, Mutagen, mutation engine, analysis, report rendering"),
        ("WORKSPACE", "~/.hexrot · SQLite WAL · UUID files · 0700/0600 permissions"),
        ("UPLOAD PATH", "No application cap · spooled to disk · names sanitized"),
        ("NOT DEFENDED", "a hostile process on the same account, the kernel, or a compromised dependency"),
    ]
    for i, (name, desc) in enumerate(host_items):
        y = 170 + i * 68
        s.append(line(82, y - 12, 658, y - 12, BORDER))
        s.append(f'<circle cx="{88}" cy="{y + 3}" r="3" fill="{AMBER}"/>')
        s.append(txt(100, y + 6, name, size=9, fill=TEXT, weight=700, ls=.8))
        s.append(body(100, y + 22, desc, 540, size=8.5, fill=MUTED, leading=12.5, max_lines=2))

    # boundary spine
    s.append(line(706, 96, 706, 466, RED, 1.4, dash="6 5"))
    s.append(rect(666, 232, 80, 92, BG, RED, 7))
    s.append(txt(706, 256, "TRUST", size=7.6, fill=RED, anchor="middle", ls=1.2, weight=700))
    s.append(txt(706, 270, "BOUNDARY", size=7.2, fill=RED, anchor="middle", ls=1.1, weight=700))
    s.append(txt(706, 294, "IDs", size=7, fill=DIM, anchor="middle"))
    s.append(txt(706, 305, "+ argv", size=7, fill=DIM, anchor="middle"))

    # sandbox
    s.append(rect(760, 100, 620, 350, "#0C1712", GREEN, 12, 1.2))
    s.append(f'<rect x="760" y="100" width="620" height="4" rx="2" fill="{GREEN}"/>')
    s.append(txt(782, 130, "SANDBOXED WORKER", size=13, fill=TEXT, weight=700, ls=1.2))
    s.append(txt(782, 148, "one decoder process tree · no network namespace", size=8.5, fill=GREEN))
    sand_items = [
        ("INPUT MOUNT", "one file, read-only, at /input/audio or a literal host path"),
        ("SUPERVISOR", "sets RLIMIT_CPU/AS/FSIZE/NOFILE/CORE, then waits for the decoder"),
        ("DECODER", "fixed executable + fixed argv, stdin closed, output sampled and bounded"),
        ("EPHEMERAL", "private /proc and /dev, 16 MiB tmpfs, no host home mount"),
    ]
    for i, (name, desc) in enumerate(sand_items):
        y = 170 + i * 68
        s.append(line(782, y - 12, 1358, y - 12, BORDER))
        s.append(f'<circle cx="{788}" cy="{y + 3}" r="3" fill="{GREEN}"/>')
        s.append(txt(800, y + 6, name, size=9, fill=TEXT, weight=700, ls=.8))
        s.append(body(800, y + 22, desc, 540, size=8.5, fill=MUTED, leading=12.5, max_lines=2))

    # allowed / denied panels
    s.append(rect(60, 478, 620, 244, PANEL, BORDER, 10))
    s.append(txt(82, 506, "+  ALLOWED INSIDE", size=10, fill=GREEN, weight=700, ls=1.2))
    allowed = [
        "read-only /usr, /lib, /lib64, /bin",
        "selected loader links and /etc/ld.so.cache",
        "the single input file (read-only)",
        "the supervisor script (read-only)",
        "private /proc, /dev and a 16 MiB /tmp",
        "fixed argv arrays with no shell parsing",
        "read-only /etc/alternatives and ld.so.cache",
    ]
    for i, item in enumerate(allowed):
        s.append(txt(90, 530 + i * 24, "+", size=10, fill=GREEN, weight=700))
        s.append(txt(106, 530 + i * 24, item, size=8.8, fill=MUTED))

    s.append(rect(760, 478, 620, 244, PANEL, BORDER, 10))
    s.append(txt(782, 506, "×  DENIED INSIDE", size=10, fill=RED, weight=700, ls=1.2))
    denied = [
        "network namespace / host loopback",
        "the host home directory and unrelated files",
        "user namespaces nested inside the sandbox",
        "writes outside /tmp and /dev/null",
        "arbitrary executables, shell strings and argv",
        "host /proc, host PIDs and mach-lookup (macOS)",
        "reading SSH keys, browser data or unrelated home files",
    ]
    for i, item in enumerate(denied):
        s.append(txt(790, 530 + i * 24, "×", size=11, fill=RED))
        s.append(txt(806, 530 + i * 24, item, size=8.8, fill=MUTED))

    s.append(rect(60, 744, 1320, 54, AMBER_DIM, AMBER, 8, 1))
    s.append(txt(82, 768, "STILL SHARED:", size=9, fill=AMBER, weight=700, ls=1))
    s.append(txt(170, 768, "the host kernel, the container runtime, and any decoder or library vulnerability. Use a disposable Linux VM for high-risk files.", size=9, fill=MUTED))
    s.append(txt(82, 785, "The macOS Seatbelt profile is deny-by-default but has not been independently validated on current Apple Silicon; sandbox-exec is deprecated by Apple.", size=8.2, fill=DIM))

    return document(1440, 830, "".join(s), GREEN, "HEXROT.EXE trust boundary")


# ---------------------------------------------------------------------------
# 5. Verification chart
# ---------------------------------------------------------------------------
def verification():
    s = []
    s.append(txt(60, 42, "VERIFICATION MATRIX", size=14, fill=TEXT, weight=700, ls=1.8))
    s.append(txt(60, 62, "58 collected tests · 52 passed · 6 environment-gated skips · 7 CI jobs.", size=9.5, fill=DIM))
    s.append(txt(1340, 50, "RUN 2026-11-22 / PYTHON 3.11.2", size=8, fill=DIM, anchor="end", ls=1.4))
    s.append(line(60, 78, 1340, 78, BORDER))

    # donut
    cx, cy, r, sw = 300, 270, 104, 30
    c = 2 * 3.141592653589793 * r
    passed, total = 52, 58
    frac = passed / total
    s.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{AMBER}" stroke-width="{sw}" opacity=".85"/>')
    s.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{GREEN}" stroke-width="{sw}" '
             f'stroke-dasharray="{c * frac:.2f} {c:.2f}" stroke-linecap="butt" transform="rotate(-90 {cx} {cy})"/>')
    s.append(txt(cx, cy - 6, "52", size=38, fill=TEXT, weight=700, anchor="middle"))
    s.append(txt(cx, cy + 18, "/ 58 COLLECTED", size=9, fill=GREEN, anchor="middle", ls=1.2))
    s.append(txt(cx, cy + 36, "89.7%", size=9, fill=DIM, anchor="middle"))
    s.append(f'<rect x="{cx - 90}" y="140" width="10" height="10" rx="2" fill="{GREEN}"/>')
    s.append(txt(cx - 74, 148, "PASS", size=8, fill=GREEN, ls=1.2))
    s.append(f'<rect x="{cx + 8}" y="140" width="10" height="10" rx="2" fill="{AMBER}"/>')
    s.append(txt(cx + 24, 148, "SKIP (ENV)", size=8, fill=AMBER, ls=1.2))
    s.append(txt(cx, 402, "6 skips require bubblewrap, ffmpeg or sndfile-info", size=8, fill=DIM, anchor="middle"))
    s.append(txt(cx, 418, "They are NOT counted as passes.", size=8, fill=AMBER, anchor="middle", weight=600))

    # tier bars
    tiers = [
        ("Unit · parsers", 15, 14, 1, GREEN),
        ("Unit · mutation", 17, 17, 0, PURPLE),
        ("Unit · supervisor", 3, 3, 0, GREEN),
        ("Unit · triage", 4, 4, 0, GREEN),
        ("Integration · sandbox", 4, 0, 4, RED),
        ("End-to-end · API", 15, 14, 1, AMBER),
    ]
    bx, by, bw = 590, 124, 700
    scale = bw / 20
    for tick in range(0, 21, 5):
        x = bx + tick * scale
        s.append(line(x, by - 8, x, by + 268, BORDER, 1, dash="3 5"))
        s.append(txt(x, by - 14, str(tick), size=7.5, fill=DIM, anchor="middle"))
    for i, (label, count, p, sk, color) in enumerate(tiers):
        y = by + 16 + i * 46
        s.append(txt(bx - 14, y + 10, label.upper(), size=8.2, fill=MUTED, anchor="end", ls=.4))
        s.append(rect(bx, y, count * scale, 20, "#18211B", BORDER, 3, 0))
        if p:
            s.append(f'<rect x="{bx}" y="{y}" width="{p * scale}" height="20" rx="3" fill="{color}" opacity=".9"/>')
        if sk:
            s.append(f'<rect x="{bx + p * scale}" y="{y}" width="{sk * scale}" height="20" rx="3" fill="{AMBER}" opacity=".8"/>')
        s.append(txt(bx + count * scale + 8, y + 14, f"{count}", size=8.5, fill=DIM))
    s.append(txt(bx, by + 292, "PER-TIER COLLECTED TESTS  ·  green/purple = pass  ·  amber = environment skip", size=7.8, fill=DIM, ls=.6))

    # CI chips
    s.append(line(60, 486, 1340, 486, BORDER))
    s.append(txt(60, 512, "CI MATRIX", size=9, fill=MUTED, weight=700, ls=1.1))
    s.append(txt(60, 527, "ubuntu-latest unless noted", size=7.6, fill=DIM))
    jobs = [("python-backend", "bwrap + ffmpeg", GREEN), ("macos", "continue-on-error", AMBER),
            ("no-sandbox", "execution disabled", RED), ("react-frontend", "tsc + vite build", CYAN),
            ("mutation-repro", "dedup + replay", PURPLE), ("parser-malformed", "resilience", GREEN),
            ("api-contract", "endpoints", CYAN)]
    for i, (name, sub, color) in enumerate(jobs):
        jx = 300 + (i % 4) * 258
        jy = 500 + (i // 4) * 58
        s.append(chip(jx, jy, 240, 46, color, name, sub, align="left"))
        s.append(f'<rect x="{jx}" y="{jy}" width="240" height="2" fill="{color}" opacity=".5"/>')

    s.append(rect(60, 618, 1280, 54, PANEL, BORDER, 8))
    s.append(f'<circle cx="82" cy="645" r="4" fill="{GREEN}"/>')
    s.append(txt(96, 641, "TYPECHECK + BUILD", size=8.5, fill=TEXT, weight=700, ls=.8))
    s.append(txt(96, 656, "tsc --noEmit clean · vite production bundle 858.87 kB (480.45 kB gzip)", size=8, fill=DIM))
    s.append(txt(1320, 645, "PASS", size=9, fill=GREEN, anchor="end", weight=700, ls=1))
    s.append(txt(60, 700, "Historical logs in docs/pytest-output.txt and docs/ui-e2e-output.json describe an earlier build; they are provenance, not current verification.", size=7.8, fill=DIM))
    return document(1400, 730, "".join(s), GREEN, "HEXROT.EXE verification matrix")


# ---------------------------------------------------------------------------
# 6. Guardrails
# ---------------------------------------------------------------------------
def guardrails():
    s = []
    s.append(txt(60, 42, "ENFORCED GUARDRAILS", size=14, fill=TEXT, weight=700, ls=1.8))
    s.append(txt(60, 62, "Hard ceilings in source, plus the defaults used by the UI and API.", size=9.5, fill=DIM))
    s.append(txt(1340, 50, "backend/config.py · workers · parsers", size=8, fill=DIM, anchor="end", ls=1))
    s.append(line(60, 78, 1340, 78, BORDER))

    rows = [
        ("INPUT SURFACE", CYAN, [
            ("No cap", "upload size", "disk and parser resources still apply", .75),
            ("50", "variants / request", "generation loop is bounded", .42),
            ("64 KiB", "metadata value", "larger values rejected", .55),
            ("4096", "parsed chunks", "then parsing stops with a warning", .68),
        ]),
        ("RUNTIME CEILING", RED, [
            ("30 s", "max timeout", "default 5 s · min 0.25 s", .85),
            ("2048 MB", "max sandbox memory", "default 512 MB · rlimit AS", .72),
            ("300", "executions / job", "files × decoders × repeats", .48),
            ("1", "active decoder job", "second start returns 409", .18),
        ]),
        ("OUTPUT & STORAGE", GREEN, [
            ("64 KiB", "each log stream", "stdout and stderr separately", .5),
            ("16 MiB", "sandbox tmpfs", "private, discarded with worker", .36),
            ("64", "file descriptors", "RLIMIT_NOFILE inside worker", .3),
            ("0", "core dumps", "RLIMIT_CORE = 0", .12),
        ]),
    ]
    for r, (label, color, tiles) in enumerate(rows):
        y = 104 + r * 196
        s.append(f'<rect x="60" y="{y}" width="3" height="22" rx="1.5" fill="{color}"/>')
        s.append(txt(72, y + 16, label, size=10, fill=color, weight=700, ls=1.4))
        for i, (value, name, note, meter) in enumerate(tiles):
            x = 60 + i * 326
            s.append(rect(x, y + 34, 302, 138, PANEL, BORDER, 9))
            s.append(f'<rect x="{x}" y="{y + 34}" width="302" height="3" rx="1.5" fill="{color}" opacity=".7"/>')
            s.append(txt(x + 20, y + 82, value, size=27, fill=TEXT, weight=700))
            s.append(txt(x + 20, y + 106, name.upper(), size=8.4, fill=color, weight=700, ls=.9))
            s.append(body(x + 20, y + 127, note, 262, size=8, fill=DIM, leading=12, max_lines=2))
            s.append(rect(x + 20, y + 150, 262, 4, "#1B251E", "#1B251E", 2, 0))
            s.append(rect(x + 20, y + 150, 262 * meter, 4, color, color, 2, 0, opacity=.75))
    s.append(rect(60, 692, 1280, 44, PANEL_2, BORDER, 8))
    s.append(txt(80, 719, "UI / API DEFAULTS →", size=8.5, fill=AMBER, weight=700, ls=1))
    s.append(txt(282, 719, "seed 42 · 5 variants · 5 s timeout · 512 MB · 1 repeat · ffmpeg + ffprobe · 8 KiB metadata value", size=8.5, fill=MUTED))
    s.append(txt(60, 760, "Sampled RSS/CPU and a 32-process threshold are monitoring, not cgroup-wide quotas. Short peaks can be missed.", size=8, fill=DIM))
    return document(1400, 785, "".join(s), RED, "HEXROT.EXE guardrails")


# ---------------------------------------------------------------------------
def main():
    files = {
        "hero.svg": hero(),
        "architecture.svg": architecture(),
        "workflow.svg": workflow(),
        "trust-boundary.svg": trust(),
        "verification.svg": verification(),
        "guardrails.svg": guardrails(),
    }
    for name, markup in files.items():
        (OUT / name).write_text(markup, encoding="utf-8")
        print(f"wrote {name} ({len(markup):,} bytes)")


if __name__ == "__main__":
    main()
