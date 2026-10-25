"""Theme injector — native Streamlit theme only.

Uses CSS variables (--app-*) that follow the native Streamlit System/Light/Dark
menu (Image 1) via prefers-color-scheme and html[data-theme]. No custom
session_state theme system is maintained, so native menu is source of truth.
"""
import pathlib
import streamlit as st

_CSS_PATH = pathlib.Path(__file__).resolve().parents[1] / "styles" / "kinetic.css"

# Tokens kept for Plotly helper and reference — match kinetic.css
TOKENS = {
    "dark": {
        "bg": "#09090B",
        "surface": "#18181B",
        "surface2": "#27272A",
        "text": "#F9FAFB",
        "text_secondary": "#D1D5DB",
        "text_muted": "#A1A1AA",
        "border": "#3F3F46",
        "accent": "#DFE104",
        "accent_text": "#000000",
        "accent_muted": "rgba(223,225,4,0.12)",
        "success": "#22C55E",
        "warning": "#F59E0B",
        "danger": "#EF4444",
        "plot_bg": "#09090B",
        "plot_grid": "#27272A",
        "plot_text": "#F9FAFB",
    },
    "light": {
        "bg": "#FFFFFF",
        "surface": "#F8FAFC",
        "surface2": "#F1F5F9",
        "text": "#111827",
        "text_secondary": "#374151",
        "text_muted": "#6B7280",
        "border": "#D1D5DB",
        "accent": "#DFE104",
        "accent_text": "#000000",
        "accent_muted": "rgba(223,225,4,0.18)",
        "success": "#16A34A",
        "warning": "#D97706",
        "danger": "#DC2626",
        "plot_bg": "#FFFFFF",
        "plot_grid": "#E4E4E7",
        "plot_text": "#111827",
    },
}

def is_dark_mode() -> bool:
    """Detect dark mode from native Streamlit theme.
    Tries st.get_option, session_state set by JS, and falls back to light.
    Uses existing theme system — no new theme provider.
    """
    try:
        # 1. Check session_state set by JS theme detector (most accurate for System)
        import streamlit as st
        if "theme_is_dark" in st.session_state:
            return bool(st.session_state["theme_is_dark"])
        # 2. Check query params set by JS (alternative)
        try:
            qp = st.query_params
            if "theme" in qp:
                return qp["theme"] == "dark"
        except Exception:
            pass
        # 3. Check Streamlit config base
        try:
            base = st.get_option("theme.base")
            if base == "dark":
                return True
            if base == "light":
                return False
            # base == "system" -> need to infer from backgroundColor
            bg = st.get_option("theme.backgroundColor")
            if bg and bg.lower() in ("#09090b", "#0b0f14", "#18181b", "#111827"):
                return True
        except Exception:
            pass
    except Exception:
        pass
    return False

def get_theme_colors(is_dark: bool | None = None):
    """Return theme-aware colors matching spec section 10."""
    if is_dark is None:
        is_dark = is_dark_mode()
    return {
        "isDark": is_dark,
        "chartBackground": "#0B0F14" if is_dark else "#FFFFFF",
        "chartTextColor": "#F8FAFC" if is_dark else "#0F172A",
        "legendColor": "#E2E8F0" if is_dark else "#334155",
        "tooltipBackground": "#111827" if is_dark else "#FFFFFF",
        "tooltipText": "#F8FAFC" if is_dark else "#0F172A",
        "tooltipBorder": "#334155" if is_dark else "#CBD5E1",
        "segmentBorder": "#0B0F14" if is_dark else "#FFFFFF",
        "containerBackground": "#0B0F14" if is_dark else "#FFFFFF",
        "containerBorder": "#334155" if is_dark else "#CBD5E1",
    }

def _read_css() -> str:
    try:
        return _CSS_PATH.read_text(encoding="utf-8")
    except Exception:
        return ""

def _current_theme() -> str:
    """Return 'system' — native Streamlit theme is source of truth.
    Kept for backward compat; always returns system so helpers use CSS-driven theming.
    """
    # No custom session_state theme — rely on native Streamlit System/Light/Dark
    return "system"

def _resolve_effective_theme(choice: str) -> str:
    if choice == "system":
        return "light"
    return choice

def get_effective_plotly_theme() -> str:
    return "system"

def inject_kinetic_theme():
    """Inject global CSS that follows native Streamlit theme. Call once per page."""
    css = _read_css()
    if css:
        st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)
    # Preload fonts — not theme-specific
    st.markdown(
        '<link rel="preconnect" href="https://fonts.googleapis.com">'
        '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
        '<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">',
        unsafe_allow_html=True,
    )

def inject_theme():
    return inject_kinetic_theme()

def app_theme_toggle():
    """No custom Theme UI — native Streamlit menu (◐ System / ☀ Light / ☾ Dark) is used."""
    return

def kinetic_theme_toggle():
    return app_theme_toggle()

def get_plotly_colors():
    # System-agnostic — CSS handles text color via transparent plotly + CSS vars
    return TOKENS["dark"]

def apply_plotly_theme(fig, theme: str | None = None):
    """Make Plotly follow native theme via transparent bg; CSS vars handle text.

    Sets only transparent backgrounds and lets kinetic.css style SVG text via
    var(--app-text) so native System/Light/Dark all work without Python detection.
    """
    try:
        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(family="Inter, system-ui, sans-serif"),
            margin=dict(l=20, r=20, t=50, b=20),
        )
        # Do not hard-code font color — CSS will style via var(--app-text)
        # Keep grid subtle and let CSS handle axes via transparent + CSS vars
        fig.update_xaxes(gridcolor="rgba(0,0,0,0.08)", zerolinecolor="rgba(0,0,0,0.08)")
        fig.update_yaxes(gridcolor="rgba(0,0,0,0.08)", zerolinecolor="rgba(0,0,0,0.08)")
        try:
            fig.update_polars(bgcolor="rgba(0,0,0,0)")
        except Exception:
            pass
    except Exception:
        pass
    return fig

def kinetic_marquee(items: list[str], variant: str = "accent", speed: str = "normal", reverse: bool = False):
    variant_cls = "kinetic-marquee--muted" if variant == "muted" else ""
    speed_cls = "kinetic-marquee__track--fast" if speed == "fast" else ""
    rev_cls = "kinetic-marquee__track--reverse" if reverse else ""
    doubled = items + items
    inner = "".join(
        f'<span class="kinetic-marquee__item">{it}<span class="kinetic-marquee__dot" aria-hidden="true"></span></span>'
        for it in doubled
    )
    html = f'<div class="kinetic-marquee {variant_cls}"><div class="kinetic-marquee__track {speed_cls} {rev_cls}">{inner}</div></div>'
    st.markdown(html, unsafe_allow_html=True)

def kinetic_hero(eyebrow: str, title_line1: str, title_line2: str, title_line2_accent: bool = True, subtitle: str = ""):
    l2_cls = "kinetic-hero__accent" if title_line2_accent else ""
    sub = f'<p style="color:var(--app-text-muted);font-size:1.05rem;max-width:42rem;margin-top:14px;line-height:1.6;">{subtitle}</p>' if subtitle else ""
    html = f'''
    <div style="padding: 14px 0 8px 0;">
      <div class="kinetic-kicker">{eyebrow}</div>
      <h1 class="kinetic-hero">{title_line1}<br><span class="{l2_cls}">{title_line2}</span></h1>
      {sub}
    </div>
    '''
    st.markdown(html, unsafe_allow_html=True)

def kinetic_massive_number(value: str, label: str, accent: bool = False):
    cls = "kinetic-massive kinetic-massive--accent" if accent else "kinetic-massive"
    html = f'''
    <div style="position:relative; overflow:hidden; border:2px solid var(--app-border); padding:28px 24px; background:var(--app-bg);">
      <div class="{cls}" aria-hidden="true">{value}</div>
      <div style="font-family:var(--app-font-display); text-transform:uppercase; letter-spacing:0.12em; font-size:0.7rem; color:var(--app-text-muted); font-weight:700; margin-top:8px;">{label}</div>
    </div>
    '''
    st.markdown(html, unsafe_allow_html=True)

def kinetic_divider():
    st.markdown('<hr />', unsafe_allow_html=True)
