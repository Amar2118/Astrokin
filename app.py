# app.py
import streamlit as st
import time
import re
import math
import html
import swisseph as swe
from datetime import time as dtime, date, datetime, timedelta
from huggingface_hub import InferenceClient

# 1. Page Configuration & Modern Theme Styling
st.set_page_config(page_title="AstroKin", page_icon="🔮", layout="centered")

st.markdown("""
    <style>
    .stApp {
        background: linear-gradient(135deg, #0f0c20 0%, #15102a 50%, #060410 100%);
        color: #e2e8f0;
    }
    .main-title {
        text-align: center;
        font-size: 2.8rem;
        font-weight: 800;
        background: linear-gradient(90deg, #a78bfa, #f472b6, #38bdf8);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0px;
    }
    .sub-title {
        text-align: center;
        color: #94a3b8;
        font-size: 1.1rem;
        margin-bottom: 2rem;
    }
    .stButton>button {
        width: 100%;
        border-radius: 12px;
        font-weight: bold;
        background: linear-gradient(90deg, #6366f1, #8b5cf6);
        color: white;
        border: none;
        padding: 0.6rem 1rem;
        transition: all 0.3s ease;
    }
    .stButton>button:hover {
        background: linear-gradient(90deg, #4f46e5, #7c3aed);
        box-shadow: 0 0 15px rgba(139, 92, 246, 0.5);
    }
    </style>
""", unsafe_allow_html=True)

st.markdown("<h1 class='main-title'>🔮 AstroKin</h1>", unsafe_allow_html=True)
st.markdown("<p class='sub-title'>Authentic Indian Vedic Family Matrix Analysis</p>", unsafe_allow_html=True)

hf_token = st.secrets.get("HF_TOKEN", "")

# Callback logic to wipe out stale AI calculations if user mutates parameters
def clear_stale_analysis():
    st.session_state.analysis_results = None
    st.session_state.last_analysis_key = None
    st.session_state.selected_member = None

def build_family_key(members):
    """Stable, hashable snapshot of the data an analysis was generated from -
    used only within a single running session, to avoid re-calling the AI
    when 'Reveal Cosmic Dynamics' is clicked again with unchanged data."""
    valid = [m for m in members if m["name"].strip() != ""]
    return tuple(
        (m["name"], m["gender"], m["dob"].isoformat(), m["tob"].isoformat(), m["pob"])
        for m in valid
    )

# 2. Initialize Permanent Session State Keys
# No file-based persistence: family data and analysis results always start
# blank on every restart, living only in memory for the current session.
if "family_members" not in st.session_state:
    st.session_state.family_members = [
        {"name": "", "gender": "Male", "dob": date(2000, 1, 1), "tob": dtime(12, 0), "pob": ""},
        {"name": "", "gender": "Male", "dob": date(1975, 1, 1), "tob": dtime(12, 0), "pob": ""}
    ]

if "analysis_results" not in st.session_state:
    st.session_state.analysis_results = None

if "last_analysis_key" not in st.session_state:
    st.session_state.last_analysis_key = None

def add_member():
    st.session_state.family_members.append(
        {"name": "", "gender": "Male", "dob": date(2000, 1, 1), "tob": dtime(12, 0), "pob": ""}
    )
    clear_stale_analysis()

# --- Offline Birthplace Lookup -----------------------------------
# Replaces geopy (Nominatim) + timezonefinder + pytz entirely. Those made
# a LIVE network call to OpenStreetMap on every single Rashi calculation -
# any timeout, rate-limit, or flaky connection would silently fall back to
# a different code path, which is exactly what made results look
# inconsistent run-to-run despite the underlying astronomy being
# deterministic. This table has no network dependency at all: the same
# input always resolves to the exact same coordinates and UTC offset,
# every time, on every machine, forever.
#
# Format: "city key" -> (latitude, longitude, utc_offset_hours)
# Indian cities use a fixed +5.5 (IST never observes DST). International
# entries use STANDARD time offset (not adjusted for daylight saving) -
# an acceptable approximation for a fallback table; this app's primary
# audience is Indian Vedic astrology use cases.
CITY_INFO = {
    "bangalore": (12.9716, 77.5946, 5.5),
    "bengaluru": (12.9716, 77.5946, 5.5),
    "mumbai": (19.0760, 72.8777, 5.5),
    "bombay": (19.0760, 72.8777, 5.5),
    "delhi": (28.7041, 77.1025, 5.5),
    "new delhi": (28.6139, 77.2090, 5.5),
    "chennai": (13.0827, 80.2707, 5.5),
    "madras": (13.0827, 80.2707, 5.5),
    "kolkata": (22.5726, 88.3639, 5.5),
    "calcutta": (22.5726, 88.3639, 5.5),
    "hyderabad": (17.3850, 78.4867, 5.5),
    "pune": (18.5204, 73.8567, 5.5),
    "ahmedabad": (23.0225, 72.5714, 5.5),
    "jaipur": (26.9124, 75.7873, 5.5),
    "lucknow": (26.8467, 80.9462, 5.5),
    "kanpur": (26.4499, 80.3319, 5.5),
    "nagpur": (21.1458, 79.0882, 5.5),
    "indore": (22.7196, 75.8577, 5.5),
    "thane": (19.2183, 72.9781, 5.5),
    "bhopal": (23.2599, 77.4126, 5.5),
    "visakhapatnam": (17.6868, 83.2185, 5.5),
    "patna": (25.5941, 85.1376, 5.5),
    "vadodara": (22.3072, 73.1812, 5.5),
    "ghaziabad": (28.6692, 77.4538, 5.5),
    "ludhiana": (30.9010, 75.8573, 5.5),
    "agra": (27.1767, 78.0081, 5.5),
    "nashik": (19.9975, 73.7898, 5.5),
    "faridabad": (28.4089, 77.3178, 5.5),
    "meerut": (28.9845, 77.7064, 5.5),
    "rajkot": (22.3039, 70.8022, 5.5),
    "varanasi": (25.3176, 82.9739, 5.5),
    "srinagar": (34.0837, 74.7973, 5.5),
    "amritsar": (31.6340, 74.8723, 5.5),
    "belagavi": (15.8497, 74.4977, 5.5),
    "belgaum": (15.8497, 74.4977, 5.5),
    "mysore": (12.2958, 76.6394, 5.5),
    "mysuru": (12.2958, 76.6394, 5.5),
    "mangalore": (12.9141, 74.8560, 5.5),
    "coimbatore": (11.0168, 76.9558, 5.5),
    "kochi": (9.9312, 76.2673, 5.5),
    "cochin": (9.9312, 76.2673, 5.5),
    "thiruvananthapuram": (8.5241, 76.9366, 5.5),
    "trivandrum": (8.5241, 76.9366, 5.5),
    "chandigarh": (30.7333, 76.7794, 5.5),
    "gurgaon": (28.4595, 77.0266, 5.5),
    "gurugram": (28.4595, 77.0266, 5.5),
    "noida": (28.5355, 77.3910, 5.5),
    "surat": (21.1702, 72.8311, 5.5),
    "guwahati": (26.1445, 91.7362, 5.5),
    "bhubaneswar": (20.2961, 85.8245, 5.5),
    "raipur": (21.2514, 81.6296, 5.5),
    "dehradun": (30.3165, 78.0322, 5.5),
    "ranchi": (23.3441, 85.3096, 5.5),
    # A handful of common international cities (standard time offsets)
    "new york": (40.7128, -74.0060, -5.0),
    "london": (51.5072, -0.1276, 0.0),
    "singapore": (1.3521, 103.8198, 8.0),
    "dubai": (25.2048, 55.2708, 4.0),
    "toronto": (43.6532, -79.3832, -5.0),
    "sydney": (-33.8688, 151.2093, 10.0),
    "san francisco": (37.7749, -122.4194, -8.0),
    "los angeles": (34.0522, -118.2437, -8.0),
    "chicago": (41.8781, -87.6298, -6.0),
    # Fallback used when the entered place isn't recognized - defaults to
    # New Delhi / IST, which is the most reasonable default for this app's
    # primary use case, rather than crashing or giving a random result.
    "_default": (28.6139, 77.2090, 5.5),
}

def resolve_birthplace(pob_text):
    """
    Offline city lookup - zero network calls, so it can never be flaky or
    give a different answer between runs due to connectivity. Tries an
    exact match, then the text before the first comma (e.g. "Bangalore,
    India" -> "bangalore"), then a loose substring match, before falling
    back to the default entry. Returns (lat, lon, utc_offset_hours).
    """
    if not pob_text or not pob_text.strip():
        return CITY_INFO["_default"]

    normalized = pob_text.strip().lower()

    if normalized in CITY_INFO:
        return CITY_INFO[normalized]

    first_segment = normalized.split(",")[0].strip()
    if first_segment in CITY_INFO:
        return CITY_INFO[first_segment]

    for key, info in CITY_INFO.items():
        if key == "_default":
            continue
        if key in normalized or normalized in key:
            return info

    return CITY_INFO["_default"]

# --- Astronomical Precision Engine ------------------------
def get_utc_datetime(dob_date, tob_time, pob_text):
    """Converts local birth date/time + place into a precise UTC timestamp, entirely offline."""
    lat, lon, utc_offset_hours = resolve_birthplace(pob_text)
    local_dt = datetime.combine(dob_date, tob_time)
    utc_dt = local_dt - timedelta(hours=utc_offset_hours)
    return utc_dt

def calculate_vedic_astrology(dob_date, tob_time, pob_text):
    """Calculates true Sidereal Moon longitude via Swiss Ephemeris (Lahiri Ayanamsa)."""
    utc_dt = get_utc_datetime(dob_date, tob_time, pob_text)
    decimal_hours_utc = utc_dt.hour + (utc_dt.minute / 60.0) + (utc_dt.second / 3600.0)

    julian_day = swe.julday(utc_dt.year, utc_dt.month, utc_dt.day, decimal_hours_utc, swe.GREG_CAL)
    swe.set_sid_mode(swe.SIDM_LAHIRI)

    calc_result, _ = swe.calc_ut(julian_day, swe.MOON, swe.FLG_SIDEREAL)
    moon_sidereal_longitude = calc_result[0]

    rashis = [
        "Mesha (Aries)", "Vrishabha (Taurus)", "Mithuna (Gemini)", "Karka (Cancer)",
        "Simha (Leo)", "Kanya (Virgo)", "Tula (Libra)", "Vrishchika (Scorpio)",
        "Dhanu (Sagittarius)", "Makara (Capricorn)", "Kumbha (Aquarius)", "Meena (Pisces)"
    ]
    rashi_index = int(moon_sidereal_longitude // 30) % 12
    detected_rashi = rashis[rashi_index]

    nakshatras = [
        "Ashwini", "Bharani", "Krittika", "Rohini", "Mrigashira", "Ardra",
        "Punarvasu", "Pushya", "Ashlesha", "Magha", "Purva Phalguni", "Uttara Phalguni",
        "Hasta", "Chitra", "Swati", "Visakha", "Anuradha", "Jyeshtha",
        "Mula", "Purva Ashadha", "Uttara Ashadha", "Shravana", "Dhanishta", "Shatabhisha",
        "Purva Bhadrapada", "Uttara Bhadrapada", "Revati"
    ]
    nakshatra_index = int(moon_sidereal_longitude // (13 + 1/3)) % 27
    detected_nakshatra = nakshatras[nakshatra_index]

    return {"rashi": detected_rashi, "nakshatra": detected_nakshatra}

def calculate_age(dob_date):
    today = date.today()
    age = today.year - dob_date.year
    if (today.month, today.day) < (dob_date.month, dob_date.day):
        age -= 1
    return age

# --- Visual UI Mappings -----------------------------------
ROLE_STYLES = {
    "Silent Guardian":  {"color": "#a78bfa", "glow": "rgba(167,139,250,0.55)", "glyph": "🛡️", "short": "Guardian"},
    "The Dominant":      {"color": "#f97362", "glow": "rgba(249,115,98,0.55)",  "glyph": "⚡", "short": "Dominant"},
    "Kula Deepam":       {"color": "#f472b6", "glow": "rgba(244,114,182,0.55)", "glyph": "🕯️", "short": "Kula Deepam"},
    "Words Matter Most": {"color": "#38bdf8", "glow": "rgba(56,189,248,0.55)",  "glyph": "🗣️", "short": "Words Matter"},
    "Cosmic Toddler":    {"color": "#34d399", "glow": "rgba(52,211,153,0.55)",  "glyph": "🍼", "short": "Toddler"},
}

def detect_role_for_member(analysis_lower, name, all_names):
    escaped_name = re.escape(name.lower())
    match = re.search(escaped_name, analysis_lower)
    if not match:
        return None

    search_from = match.end()
    end_candidates = [min(len(analysis_lower), search_from + 500)]

    heading_match = re.search(r"\n#{1,6}\s", analysis_lower[search_from:])
    if heading_match:
        end_candidates.append(search_from + heading_match.start())

    for other_name in all_names:
        if other_name.lower() == name.lower():
            continue
        other_match = re.search(re.escape(other_name.lower()), analysis_lower[search_from:])
        if other_match:
            end_candidates.append(search_from + other_match.start())

    window_end = min(end_candidates)
    window = analysis_lower[search_from:window_end]

    if "dominant" in window: return "The Dominant"
    if "kula deepam" in window: return "Kula Deepam"
    if "words matter" in window: return "Words Matter Most"
    if "silent guardian" in window: return "Silent Guardian"
    if re.search(r"\blight\b", window): return "Kula Deepam"

    return None

def get_context_snippet(analysis_original, analysis_lower, name, all_names, max_len=220):
    escaped_name = re.escape(name.lower())
    match = re.search(escaped_name, analysis_lower)
    if not match:
        return None

    search_from = match.end()
    end_candidates = [min(len(analysis_lower), search_from + max_len)]
    heading_match = re.search(r"\n#{1,6}\s", analysis_lower[search_from:])
    if heading_match:
        end_candidates.append(search_from + heading_match.start())
    for other_name in all_names:
        if other_name.lower() == name.lower():
            continue
        other_match = re.search(re.escape(other_name.lower()), analysis_lower[search_from:])
        if other_match:
            end_candidates.append(search_from + other_match.start())
    window_end = min(end_candidates)

    snippet = analysis_original[search_from:window_end]
    snippet = re.sub(r"[#*_`]", "", snippet)
    snippet = re.sub(r"\s+", " ", snippet).strip(" -:\n")
    return snippet[:max_len].strip() if snippet else None

def build_orbit_svg(members_with_stats, selected_name=None):
    n = len(members_with_stats)
    if n == 0: return ""

    width, height = 700, 700
    cx, cy = width / 2, height / 2
    orbit_radius = 240
    selected_lower = selected_name.lower() if selected_name else None

    threads = []
    nodes = []

    for i, m in enumerate(members_with_stats):
        angle = (2 * math.pi * i / n) - (math.pi / 2)
        nx = cx + orbit_radius * math.cos(angle)
        ny = cy + orbit_radius * math.sin(angle)

        style = ROLE_STYLES.get(m["role_key"], ROLE_STYLES["Silent Guardian"])
        node_radius = 28 + (m["secret_level"] / 100) * 22
        thread_width = 1.5 + (m["arg_power"] / 100) * 5.5
        thread_opacity = 0.2 + (m["blackmail_res"] / 100) * 0.6

        is_selected = selected_lower is not None and m["name"].lower() == selected_lower
        has_selection = selected_lower is not None

        if is_selected:
            thread_width += 3
            thread_opacity = min(1.0, thread_opacity + 0.35)
        elif has_selection:
            thread_opacity *= 0.25

        threads.append(f'<line x1="{cx}" y1="{cy}" x2="{nx:.1f}" y2="{ny:.1f}" stroke="{style["color"]}" stroke-width="{thread_width:.1f}" stroke-linecap="round" opacity="{thread_opacity:.2f}" />')

        safe_name_text = html.escape(m["name"])
        ring_stroke_width = 4 if is_selected else 2
        node_opacity = 1.0 if (not has_selection or is_selected) else 0.45
        selection_ring = f'<circle cx="{nx:.1f}" cy="{ny:.1f}" r="{node_radius + 8:.1f}" fill="none" stroke="{style["color"]}" stroke-width="2" opacity="0.9" />' if is_selected else ""
        label_dy = node_radius + 18

        node_group = (
            f'<g class="orbit-node" opacity="{node_opacity}">'
            f'{selection_ring}'
            f'<circle cx="{nx:.1f}" cy="{ny:.1f}" r="{node_radius:.1f}" fill="{style["color"]}" opacity="0.18" />'
            f'<circle cx="{nx:.1f}" cy="{ny:.1f}" r="{node_radius - 6:.1f}" fill="#0f172a" stroke="{style["color"]}" stroke-width="{ring_stroke_width}" />'
            f'<text x="{nx:.1f}" y="{ny - 4:.1f}" text-anchor="middle" font-size="13" font-weight="700" fill="#e2e8f0">{safe_name_text}</text>'
            f'<text x="{nx:.1f}" y="{ny + 12:.1f}" text-anchor="middle" font-size="16">{style["glyph"]}</text>'
            f'<text x="{nx:.1f}" y="{ny + label_dy:.1f}" text-anchor="middle" font-size="11" fill="{style["color"]}" font-weight="600">{style["short"]}</text>'
            f'</g>'
        )
        nodes.append(node_group)

    threads_str = "".join(threads)
    nodes_str = "".join(nodes)

    svg = (
        f'<div style="width: 100%; display: flex; justify-content: center; background: transparent;">'
        f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}">'
        f'<defs><radialGradient id="coreGlow" cx="50%" cy="50%" r="50%">'
        f'<stop offset="0%" stop-color="rgba(167,139,250,0.55)" /><stop offset="100%" stop-color="rgba(167,139,250,0)" />'
        f'</radialGradient></defs>'
        f'<circle cx="{cx}" cy="{cy}" r="{orbit_radius}" fill="none" stroke="rgba(148,163,184,0.25)" stroke-width="1" stroke-dasharray="4 6" />'
        f'{threads_str}'
        f'<circle cx="{cx}" cy="{cy}" r="70" fill="url(#coreGlow)" />'
        f'<circle cx="{cx}" cy="{cy}" r="38" fill="#15102a" stroke="#a78bfa" stroke-width="2" />'
        f'<text x="{cx}" y="{cy - 4}" text-anchor="middle" font-size="14" font-weight="700" fill="#e2e8f0">Family</text>'
        f'<text x="{cx}" y="{cy + 14}" text-anchor="middle" font-size="14" font-weight="700" fill="#e2e8f0">Core</text>'
        f'{nodes_str}'
        f'</svg></div>'
        f'<p style="text-align:center; color:#94a3b8; font-size:0.8rem; margin-top: 8px;">Thread thickness = argument power &nbsp;·&nbsp; thread glow = blackmail resistance &nbsp;·&nbsp; node size = secret-keeping level</p>'
    )
    return svg

def build_detail_card(member, stats, astro_data, context_snippet):
    style = ROLE_STYLES.get(stats["role_key"], ROLE_STYLES["Silent Guardian"])
    safe_name = html.escape(member["name"])
    safe_pob = html.escape(member["pob"]) if member["pob"] else "Not specified"
    safe_gender = html.escape(member["gender"])
    dob_display = member["dob"].strftime("%d %b %Y")
    tob_display = member["tob"].strftime("%I:%M %p")

    context_html = ""
    if context_snippet:
        safe_context = html.escape(context_snippet)
        context_html = f'<p style="color:#cbd5e1; font-size:0.9rem; font-style:italic; margin-top:14px; border-left: 3px solid {style["color"]}; padding-left:12px;">"{safe_context}"</p>'

    card_html = f"""<div style="background: linear-gradient(145deg, #1e1b4b 0%, #0f172a 100%); border: 2px solid {style['color']}66; border-radius: 16px; padding: 22px; margin-top: 10px; box-shadow: 0 8px 24px rgba(0,0,0,0.4);">
<div style="display:flex; align-items:center; gap:12px; margin-bottom:14px;">
<span style="font-size:2rem;">{style['glyph']}</span>
<div>
<h3 style="margin:0; color:#e2e8f0; font-size:1.5rem;">{safe_name}</h3>
<span style="background: {style['color']}22; color: {style['color']}; padding: 3px 10px; border-radius: 20px; font-size: 0.8rem; font-weight: bold;">{stats['role_key']}</span>
</div>
</div>
<div style="display:grid; grid-template-columns: 1fr 1fr; gap: 10px; font-size:0.9rem; color:#cbd5e1; margin-bottom: 14px;">
<div>🌙 <b>Rashi:</b> {astro_data['rashi']}</div>
<div>✨ <b>Nakshatra:</b> {astro_data['nakshatra']}</div>
<div>🎂 <b>Born:</b> {dob_display}</div>
<div>🕐 <b>Time:</b> {tob_display}</div>
<div style="grid-column: span 2;">📍 <b>Place:</b> {safe_pob}</div>
</div>
<div style="display:flex; gap:16px; flex-wrap:wrap; font-size:0.85rem;">
<span>🗣️ Argument power: <b style="color:#38bdf8;">{stats['arg_power']}%</b></span>
<span>🎭 Blackmail resist: <b style="color:#f472b6;">{stats['blackmail_res']}%</b></span>
<span>🤫 Secret keeper: <b style="color:#34d399;">{stats['secret_level']}%</b></span>
</div>
{context_html}
</div>"""
    return card_html

# 3. Input UI Component Panel
st.subheader("👨‍👩‍👧‍👦 Family Details")
for i, member in enumerate(st.session_state.family_members):
    st.markdown(f"**Member #{i+1}**")
    col1, col2, col3, col4, col5 = st.columns([2, 1.2, 1.8, 1.5, 2.3])
    with col1:
        member["name"] = st.text_input("Name", value=member["name"], key=f"name_{i}", placeholder="Enter name", on_change=clear_stale_analysis)
    with col2:
        member["gender"] = st.selectbox("Gender", ["Male", "Female", "Other"], key=f"gender_{i}", on_change=clear_stale_analysis)
    with col3:
        member["dob"] = st.date_input("Date of Birth", value=member["dob"], key=f"dob_{i}", min_value=date(1940, 1, 1), max_value=date.today(), on_change=clear_stale_analysis)
    with col4:
        member["tob"] = st.time_input("Time of Birth", value=member["tob"], key=f"tob_{i}", on_change=clear_stale_analysis)
    with col5:
        member["pob"] = st.text_input("Place of Birth", value=member["pob"], key=f"pob_{i}", placeholder="City, Country", on_change=clear_stale_analysis)

st.button("➕ Add Another Member", on_click=add_member)
st.divider()

# 4. Core Processing Engine
if st.button("🔮 Reveal Cosmic Dynamics", type="primary"):
    valid_members = [m for m in st.session_state.family_members if m["name"].strip() != ""]

    if not hf_token:
        st.error("HF_TOKEN missing! Please check .streamlit/secrets.toml")
    elif len(valid_members) < 2:
        st.warning("Please enter details for at least 2 family members!")
    else:
        # Uses the same key format as build_family_key() (see section 2) so
        # a persisted analysis loaded at startup and one generated fresh
        # here are always compared on equal footing.
        current_key = build_family_key(st.session_state.family_members)

        family_astrology_summary = ""
        for m in valid_members:
            astro = calculate_vedic_astrology(m['dob'], m['tob'], m['pob'])
            family_astrology_summary += f"- {m['name']} ({m['gender']}): Vedic Rashi is {astro['rashi']}, Nakshatra is {astro['nakshatra']}. Born at {m['tob'].strftime('%H:%M')} in {m['pob']}.\n"

        if st.session_state.last_analysis_key == current_key and st.session_state.analysis_results:
            st.info("Family details unchanged since last analysis - showing cached result.")
        else:
            system_instruction = """You are an expert Indian Vedic Astrologer. Analyze the interactions between these Rashis and Nakshatras.
Strictly assign ONE traditional role per member from this list: 'The Dominant', 'The Light / Kula Deepam', 'Whose Words Matter Most', or 'The Silent Guardian'.
Provide brief, uplifting explanations in Markdown."""

            with st.spinner("Calculating Ephemeris Positions & Matrix Dynamics... 🌌"):
                try:
                    client = InferenceClient(api_key=hf_token)
                    response = client.chat.completions.create(
                        model="Qwen/Qwen2.5-Coder-32B-Instruct",
                        messages=[
                            {"role": "system", "content": system_instruction},
                            {"role": "user", "content": family_astrology_summary}
                        ],
                        max_tokens=1000,
                        temperature=0.0
                    )
                    st.session_state.analysis_results = response.choices[0].message.content
                    st.session_state.last_analysis_key = current_key
                except Exception as e:
                    st.error(f"Error generating results: {e}")

# 5. Output Layer & Dashboard Display
if st.session_state.analysis_results:
    st.success("Analysis Complete! ✨")
    st.markdown("### 📜 Family Cosmic Matrix Analysis")
    st.write(st.session_state.analysis_results)

    st.divider()
    st.markdown("### 🌌 Cosmic Constellation: Family Orbit Map")
    st.info("Each family member orbits the shared Family Core. Thread thickness shows argument power, thread glow shows blackmail resistance, and node size shows how well they keep secrets.")

    current_active_members = [m for m in st.session_state.family_members if m["name"].strip() != ""]
    analysis_lower = st.session_state.analysis_results.lower()
    all_names = [m["name"] for m in current_active_members]

    members_with_stats = []
    for member in current_active_members:
        name = member["name"]
        role_key = "Silent Guardian"
        arg_power, blackmail_res, secret_level = 65, 85, 95

        detected_role = detect_role_for_member(analysis_lower, name, all_names)
        if detected_role == "The Dominant":
            role_key, arg_power, blackmail_res, secret_level = "The Dominant", 98, 40, 30
        elif detected_role == "Kula Deepam":
            role_key, arg_power, blackmail_res, secret_level = "Kula Deepam", 75, 90, 70
        elif detected_role == "Words Matter Most":
            role_key, arg_power, blackmail_res, secret_level = "Words Matter Most", 95, 60, 80
        elif detected_role == "Silent Guardian":
            role_key, arg_power, blackmail_res, secret_level = "Silent Guardian", 65, 85, 95

        age = calculate_age(member["dob"])
        if age <= 3:
            role_key, arg_power, blackmail_res, secret_level = "Cosmic Toddler", 99, 100, 5
        elif age > 50:
            arg_power += 5
            blackmail_res += 10

        arg_power = min(100, max(0, arg_power))
        blackmail_res = min(100, max(0, blackmail_res))
        secret_level = min(100, max(0, secret_level))

        members_with_stats.append({
            "name": name, "role_key": role_key, "arg_power": arg_power,
            "blackmail_res": blackmail_res, "secret_level": secret_level, "member": member,
        })

    if "selected_member" not in st.session_state:
        st.session_state.selected_member = None

    orbit_html = build_orbit_svg(members_with_stats, selected_name=st.session_state.selected_member)
    st.markdown(orbit_html, unsafe_allow_html=True)

    st.markdown("**Select a family member to view their full astrology profile:**")

    # Grid Layout to prevent column squishing
    grid_columns_count = 3
    for chunk_idx in range(0, len(members_with_stats), grid_columns_count):
        chunk = members_with_stats[chunk_idx:chunk_idx + grid_columns_count]
        cols = st.columns(grid_columns_count)
        for i, entry in enumerate(chunk):
            style = ROLE_STYLES.get(entry["role_key"], ROLE_STYLES["Silent Guardian"])
            with cols[i]:
                if st.button(f"{style['glyph']} {entry['name']}", key=f"select_member_{chunk_idx + i}", use_container_width=True):
                    st.session_state.selected_member = entry["name"]
                    st.rerun()

    if st.session_state.selected_member:
        selected_lower = st.session_state.selected_member.lower()
        selected_entry = next((m for m in members_with_stats if m["name"].lower() == selected_lower), None)

        if selected_entry:
            astro_data = calculate_vedic_astrology(selected_entry["member"]["dob"], selected_entry["member"]["tob"], selected_entry["member"]["pob"])
            context_snippet = get_context_snippet(st.session_state.analysis_results, analysis_lower, selected_entry["name"], all_names)

            st.markdown(build_detail_card(selected_entry["member"], selected_entry, astro_data, context_snippet), unsafe_allow_html=True)
            if st.button("✕ Clear selection"):
                st.session_state.selected_member = None
                st.rerun()
        else:
            st.session_state.selected_member = None