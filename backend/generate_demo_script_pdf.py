"""
generate_demo_script_pdf.py
----------------------------
Generates a broadcast-quality, professionally formatted PDF document containing
the complete scene-by-scene script, visual directions, audio dialogue, and presentation
playbook for recording the Tarang product demonstration video.
"""

import os
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch

def create_demo_script_pdf(output_paths: list[str]):
    for out_path in output_paths:
        os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)

    # Use the first path for generation, then copy if needed
    primary_path = output_paths[0]

    doc = SimpleDocTemplate(
        primary_path,
        pagesize=letter,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=36,
    )

    styles = getSampleStyleSheet()

    # Brand Palette
    c_primary = colors.HexColor("#0C6E8C")      # Deep Marine Ocean Cyan
    c_secondary = colors.HexColor("#0F172A")    # Slate 900
    c_muted = colors.HexColor("#475569")        # Slate 600
    c_teal = colors.HexColor("#0D9488")         # Teal accent
    c_bg_light = colors.HexColor("#F8FAFC")     # Slate 50
    c_border = colors.HexColor("#CBD5E1")       # Slate 300
    c_rose = colors.HexColor("#BE123C")         # Crimson Rose
    c_amber = colors.HexColor("#B45309")        # Amber

    # Typography styles
    title_style = ParagraphStyle(
        "DocTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        textColor=c_primary,
        spaceAfter=3,
    )

    subtitle_style = ParagraphStyle(
        "DocSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9.5,
        leading=13,
        textColor=c_muted,
        spaceAfter=10,
    )

    h1_style = ParagraphStyle(
        "H1_Custom",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=15,
        textColor=c_secondary,
        spaceBefore=10,
        spaceAfter=4,
    )

    h2_style = ParagraphStyle(
        "H2_Custom",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=9.5,
        leading=12,
        textColor=c_primary,
        spaceBefore=6,
        spaceAfter=3,
    )

    body_style = ParagraphStyle(
        "Body_Custom",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        leading=11,
        textColor=c_secondary,
        spaceAfter=4,
    )

    table_header_style = ParagraphStyle(
        "TH_Custom",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=7.5,
        leading=10,
        textColor=colors.white,
    )

    table_cell_bold = ParagraphStyle(
        "TCell_Bold",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=7.5,
        leading=10,
        textColor=c_secondary,
    )

    table_cell_text = ParagraphStyle(
        "TCell_Text",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=7.5,
        leading=10.5,
        textColor=c_secondary,
    )

    table_cell_spoken = ParagraphStyle(
        "TCell_Spoken",
        parent=styles["Normal"],
        fontName="Helvetica-Oblique",
        fontSize=7.5,
        leading=10.5,
        textColor=colors.HexColor("#0F3C4C"),
    )

    table_cell_callout = ParagraphStyle(
        "TCell_Callout",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=7,
        leading=9.5,
        textColor=c_rose,
    )

    bullet_style = ParagraphStyle(
        "Bullet_Custom",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=7.5,
        leading=10.5,
        textColor=c_secondary,
        leftIndent=10,
        spaceAfter=2,
    )

    story = []

    # Title & Metadata Banner
    story.append(Paragraph("🌊 Tarang (तरंग) — Official Product Demo Video Script", title_style))
    story.append(Paragraph("A Comprehensive Scene-by-Scene Screenplay & Master Presentation Playbook for Evaluators, Hackathons, and Investors", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=1.5, color=c_primary, spaceBefore=0, spaceAfter=8))

    # Executive Production Specs Table
    specs_data = [
        [
            Paragraph("<b>Target Duration</b>: 3 min 15 sec", body_style),
            Paragraph("<b>Target Video Resolution</b>: 1080p (1920x1080) @ 60 FPS", body_style),
        ],
        [
            Paragraph("<b>Voiceover Pacing</b>: 130 - 140 words / min", body_style),
            Paragraph("<b>Audio Mix</b>: Spoken Voice (0 dB) + Ambient Ocean Synth (-22 dB)", body_style),
        ],
        [
            Paragraph("<b>Browser Zoom</b>: 100% or 110% (Hi-DPI crisp UI)", body_style),
            Paragraph("<b>Primary Tech</b>: Next.js + FastAPI + LangGraph + Leaflet", body_style),
        ]
    ]
    t_specs = Table(specs_data, colWidths=[270, 270])
    t_specs.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), c_bg_light),
        ('BOX', (0,0), (-1,-1), 1, c_border),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
        ('RIGHTPADDING', (0,0), (-1,-1), 8),
    ]))
    story.append(t_specs)
    story.append(Spacer(1, 8))

    def make_scene_table(rows):
        """Builds a standardized 4-column scene script table."""
        col_widths = [55, 155, 235, 95]
        header = [
            Paragraph("Timing", table_header_style),
            Paragraph("Visual Screen Action (What to Click / Show)", table_header_style),
            Paragraph("Voiceover Dialogue (What to Say Verbatim)", table_header_style),
            Paragraph("On-Screen Badges & Callouts", table_header_style),
        ]
        table_rows = [header]
        for r in rows:
            table_rows.append([
                Paragraph(r[0], table_cell_bold),
                Paragraph(r[1], table_cell_text),
                Paragraph(f'"{r[2]}"', table_cell_spoken),
                Paragraph(r[3], table_cell_callout),
            ])

        t = Table(table_rows, colWidths=col_widths)
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), c_primary),
            ('ALIGN', (0,0), (-1,-1), 'LEFT'),
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('BOX', (0,0), (-1,-1), 1, c_border),
            ('GRID', (0,0), (-1,-1), 0.5, c_border),
            ('TOPPADDING', (0,0), (-1,-1), 4),
            ('BOTTOMPADDING', (0,0), (-1,-1), 4),
            ('LEFTPADDING', (0,0), (-1,-1), 5),
            ('RIGHTPADDING', (0,0), (-1,-1), 5),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, c_bg_light]),
        ]))
        return t

    # ACT 1
    story.append(Paragraph("Act 1: The Problem & The Hook (0:00 - 0:30)", h1_style))
    act1_rows = [
        [
            "0:00 - 0:12",
            "Start on Landing Page (localhost:3000). Slowly scroll past hero section showcasing the Indian coastline map and mission headline.",
            "Every single day, over 4 million artisanal fishermen along India's 7,500-kilometer coastline venture into the sea in small motorized boats under 20 meters. They face dangerous seas, unpredictable weather, and invisible international boundaries.",
            "🔴 4M+ Artisanal Fishermen at Sea Daily"
        ],
        [
            "0:12 - 0:24",
            "Hover over key landing feature cards (Marine Weather, Border Breach Alerts, PFZ, Safe Navigation Routing).",
            "Today, official advisories are locked inside dense PDF bulletins filled with oceanographic jargon, while accidental border crossings in places like the Palk Strait lead to boat seizures and detentions.",
            "⚠️ PDF Jargon • Accidental Arrests • Wasted Fuel"
        ],
        [
            "0:24 - 0:30",
            "Click 'Launch Platform' to smoothly navigate into the live operational app dashboard (/app).",
            "This is Tarang — an AI-powered, deterministic marine decision-support and ecosystem intelligence platform built specifically for Indian waters.",
            "🌊 Tarang: Marine Intelligence Platform"
        ]
    ]
    story.append(make_scene_table(act1_rows))
    story.append(Spacer(1, 10))

    # ACT 2
    story.append(Paragraph("Act 2: Multi-Intent AI & Multilingual Voice (0:30 - 1:15)", h1_style))
    act2_rows = [
        [
            "0:30 - 0:45",
            "On main map, select Mumbai or Chennai harbour. Open Language dropdown to briefly display Tamil, Gujarati, Malayalam, Hindi, etc.",
            "Fishermen don't ask simple single-variable questions. They ask compound queries. Watch what happens when we ask: 'What is the sea level, wind speed, any hazard, and where is the nearest fishing zone near Mumbai?'",
            "🗣️ 9 Indian Coastal Languages Supported"
        ],
        [
            "0:45 - 0:58",
            "Submit query. Immediately open the Trace Panel / Execution Drawer on right, showing LangGraph agents lighting up in parallel.",
            "Notice the execution drawer. Tarang uses an event-driven LangGraph architecture with Groq. Instead of a generic LLM hallucinating ocean stats, Tarang dispatches specialist agents in parallel to live INCOIS satellite streams, harmonic tidal models, and Open-Meteo marine models.",
            "⚡ Deterministic LangGraph Multi-Agent Engine"
        ],
        [
            "0:58 - 1:15",
            "Highlight synthesized multi-section card. Click Audio button to play voice advisory. Hover over the ORCA Risk Dial (0-100).",
            "The output synthesizes all four answers deterministically, with an explainable ORCA safety score based on wave height, wind gusts, and border distance. And with integrated Sarvam AI voice synthesis, fishers receive audio advisories in their own regional accent.",
            "🛡️ Zero Hallucination Safety Scoring"
        ]
    ]
    story.append(make_scene_table(act2_rows))
    story.append(Spacer(1, 10))

    # ACT 3
    story.append(Paragraph("Act 3: Safe Marine Route Optimization Engine (1:15 - 1:55)", h1_style))
    act3_rows = [
        [
            "1:15 - 1:28",
            "Click Trip / Route Planner icon on left rail. Pick coastal starting harbour (e.g. Chennai) and an offshore destination ground.",
            "Commercial GPS apps only understand highways or massive container ships. Tarang features a custom Safe Marine Route Optimization Engine built on an 8-connected coastal water grid.",
            "⚓ Deterministic A* Pathfinding"
        ],
        [
            "1:28 - 1:42",
            "Click 'Calculate Safe Route'. Show blue marine route contouring around land. Zoom in to show waypoints avoiding land and shallow shoals.",
            "Using sub-millisecond Shapely polygon land-masking, the route strictly navigates around peninsulas, sandbanks, and shallow shoals. It dynamically calculates arrival time offsets along each waypoint to evaluate future wave heights and wind corridors.",
            "🗺️ Sub-millisecond Land-Masking & Weather Offsets"
        ],
        [
            "1:42 - 1:55",
            "Toggle 'Attract to PFZ' switch. Show route curve slightly toward the nearest high-chlorophyll fishing ground.",
            "Even better, if enabled, the route incorporates INCOIS satellite chlorophyll data as a positive cost incentive, safely routing boats closer to fertile feeding zones without compromising seaworthiness.",
            "🐟 PFZ Chlorophyll-Attraction Routing"
        ]
    ]
    story.append(make_scene_table(act3_rows))
    story.append(PageBreak())

    # ACT 4
    story.append(Paragraph("Act 4: IMBL Geofencing & Life-Saving Border Alerts (1:55 - 2:25)", h1_style))
    act4_rows = [
        [
            "1:55 - 2:08",
            "Pan map to Palk Bay / Gulf of Mannar between Tamil Nadu and Sri Lanka. Show red dashed UNCLOS international boundary line.",
            "Accidental border crossing in narrow straits is a multi-million-dollar diplomatic and human tragedy. Tarang embeds exact UNCLOS international maritime boundary polylines.",
            "🚨 UNCLOS IMBL Geofencing"
        ],
        [
            "2:08 - 2:25",
            "Trigger evaluation or display the Critical Breach Alert banner showing distance (<5km) and emergency return compass heading.",
            "Using geodesic cross-track calculations, Tarang monitors vessel distance. When a boat drifts within 5 kilometers of international waters, it fires a high-contrast emergency warning, dispatches WhatsApp and SMS alerts, and gives the skipper an immediate safe compass heading to steer back home.",
            "🧭 Proactive SMS & WhatsApp Heading Alerts"
        ]
    ]
    story.append(make_scene_table(act4_rows))
    story.append(Spacer(1, 10))

    # ACT 5
    story.append(Paragraph("Act 5: Marine Ecosystem Analytics & AI Research Fellow (2:25 - 3:00)", h1_style))
    act5_rows = [
        [
            "2:25 - 2:38",
            "Click Research tab on left rail (EcosystemAnalyticsView). Show 84-Month Multi-Axis Time-Series SVG Chart for Malabar Coast.",
            "Beyond aiding fishermen at sea, Tarang empowers marine scientists and policymakers. This is the Researcher Suite — cross-correlating 84 months of satellite Chlorophyll-a, Sea Surface Temperatures, and ICAR-CMFRI commercial catch landings.",
            "🔬 84-Month Longitudinal Ecosystem Suite (2018–2024)"
        ],
        [
            "2:38 - 2:48",
            "Hover over chart to show tooltips with Chl-a Z-scores, SST anomalies, and catch volume. Point out Pearson correlations (r = 0.45, r = -0.39).",
            "Our correlation engine automatically detects Marine Heatwaves and primary productivity deficits, identifying why pelagic shoals like the Malabar Oil Sardine collapsed during anomalous warming periods.",
            "📈 Automated MHW & Trophic Attribution"
        ],
        [
            "2:48 - 3:00",
            "Scroll down to Bio-Oceanographic AI Research Fellow. Click quick prompt: 'Why has fish productivity declined in this coastal region?'",
            "Researchers can consult our Bio-Oceanographic AI Fellow, grounded in empirical time-series data to synthesize causal attribution reports and climate-responsive fisheries management policies.",
            "🤖 Bio-Oceanographic AI Fellow"
        ]
    ]
    story.append(make_scene_table(act5_rows))
    story.append(Spacer(1, 10))

    # ACT 6
    story.append(Paragraph("Act 6: Outro & Call to Action (3:00 - 3:15)", h1_style))
    act6_rows = [
        [
            "3:00 - 3:15",
            "Pan back out to full Indian coastline view on map with Tarang header and GitHub repository URL visible.",
            "With fail-closed safety, multi-channel accessibility, and end-to-end scientific grounding, Tarang is bringing modern intelligence to India's marine frontier. Saving lives, safeguarding livelihoods, and preserving our blue economy. Thank you.",
            "🌊 Tarang — Preserving India's Blue Economy"
        ]
    ]
    story.append(make_scene_table(act6_rows))
    story.append(Spacer(1, 12))

    # Presenter Master Playbook & Checklist
    story.append(Paragraph("🏆 Presenter Master Playbook: Recording & Pitching Tips", h1_style))
    
    tips_data = [
        [
            Paragraph("<b>1. Pre-warm Caches & Models</b>", table_cell_bold),
            Paragraph("Always submit one test query and one route calculation before pressing record. This ensures LangGraph, Groq, and Open-Meteo responses load with zero latency during the actual recording.", table_cell_text)
        ],
        [
            Paragraph("<b>2. Clean Browser Environment</b>", table_cell_bold),
            Paragraph("Press <b>F11</b> to enter clean full-screen mode. Hide your browser bookmarks bar (<b>Ctrl+Shift+B</b>). Close all other background tabs and notifications to maintain focus.", table_cell_text)
        ],
        [
            Paragraph("<b>3. Cursor Discipline</b>", table_cell_bold),
            Paragraph("Avoid erratic, nervous mouse circling. Move the cursor smoothly to an element, click, and let the UI do the talking. Use a subtle yellow cursor highlighter if your recorder supports it.", table_cell_text)
        ],
        [
            Paragraph("<b>4. Audio & Vocal Delivery</b>", table_cell_bold),
            Paragraph("Maintain an energetic, authoritative tone. When mentioning Sarvam AI audio, stop speaking for 2 full seconds so the listener can clearly hear the authentic regional accent.", table_cell_text)
        ],
        [
            Paragraph("<b>5. The Killer Closer for Judges</b>", table_cell_bold),
            Paragraph("Emphasize the <i>'Fail-Closed Architecture'</i>: If live sensors are down, Tarang refuses to hallucinate safety clearance. This single design principle separates toy demos from life-critical engineering.", table_cell_text)
        ]
    ]
    t_tips = Table(tips_data, colWidths=[150, 390])
    t_tips.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), c_bg_light),
        ('BOX', (0,0), (-1,-1), 1, c_border),
        ('GRID', (0,0), (-1,-1), 0.5, c_border),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
        ('RIGHTPADDING', (0,0), (-1,-1), 6),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ]))
    story.append(t_tips)

    doc.build(story)
    print(f"Successfully generated: {primary_path}")

    # Copy to additional paths if provided
    import shutil
    for additional_path in output_paths[1:]:
        shutil.copyfile(primary_path, additional_path)
        print(f"Copied to: {additional_path}")

if __name__ == "__main__":
    paths = [
        os.path.join(os.path.dirname(__file__), "..", "Tarang_Demo_Video_Script_and_Presentation_Guide.pdf"),
        os.path.join(os.path.dirname(__file__), "..", "frontend", "public", "Tarang_Demo_Video_Script_and_Presentation_Guide.pdf"),
    ]
    create_demo_script_pdf(paths)
