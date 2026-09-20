"""
generate_researcher_data_pdf.py
-------------------------------
Generates a publication-quality PDF summary of the data extraction methodology
and scientific architecture for researchers using the Tarang Bio-Oceanographic Suite.
"""

import os
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch

def create_pdf(output_path: str):
    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        leftMargin=40,
        rightMargin=40,
        topMargin=40,
        bottomMargin=40,
    )

    styles = getSampleStyleSheet()

    # Custom color palette
    c_primary = colors.HexColor("#0C6E8C")      # Deep Marine Ocean Cyan
    c_secondary = colors.HexColor("#16242B")    # Dark Slate Ink
    c_muted = colors.HexColor("#52656E")        # Muted Slate
    c_teal = colors.HexColor("#0D9488")         # Teal accent
    c_bg_light = colors.HexColor("#F8FAFC")     # Soft slate background
    c_border = colors.HexColor("#E2E8F0")       # Border light gray
    c_accent_green = colors.HexColor("#059669") # Emerald
    c_accent_rose = colors.HexColor("#E11D48")  # Rose

    # Typography styles
    title_style = ParagraphStyle(
        "DocTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=20,
        leading=24,
        textColor=c_primary,
        spaceAfter=4,
    )

    subtitle_style = ParagraphStyle(
        "DocSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10.5,
        leading=14,
        textColor=c_muted,
        spaceAfter=12,
    )

    h1_style = ParagraphStyle(
        "Heading1_Custom",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=12.5,
        leading=16,
        textColor=c_secondary,
        spaceBefore=12,
        spaceAfter=6,
    )

    h2_style = ParagraphStyle(
        "Heading2_Custom",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=10,
        leading=13,
        textColor=c_primary,
        spaceBefore=8,
        spaceAfter=4,
    )

    body_style = ParagraphStyle(
        "Body_Custom",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=12,
        textColor=c_secondary,
        spaceAfter=5,
    )

    bullet_style = ParagraphStyle(
        "Bullet_Custom",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=11.5,
        textColor=c_secondary,
        leftIndent=14,
        spaceAfter=3,
    )

    table_header_style = ParagraphStyle(
        "TableHeader",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=10,
        textColor=colors.white,
    )

    table_cell_style = ParagraphStyle(
        "TableCell",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=7.5,
        leading=10,
        textColor=c_secondary,
    )

    table_cell_bold = ParagraphStyle(
        "TableCellBold",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=7.5,
        leading=10,
        textColor=c_secondary,
    )

    code_style = ParagraphStyle(
        "Code_Custom",
        parent=styles["Normal"],
        fontName="Courier",
        fontSize=7.5,
        leading=9.5,
        textColor=colors.HexColor("#0F172A"),
        backColor=colors.HexColor("#F1F5F9"),
    )

    story = []

    # Title & Metadata Banner
    story.append(Paragraph("TARANG BIO-OCEANOGRAPHIC RESEARCH SUITE", title_style))
    story.append(Paragraph("<b>Scientific Data Extraction, Sensor Synthesis & Causal Modeling Methodology</b>", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=1.5, color=c_primary, spaceAfter=10))

    # Metadata grid
    meta_data = [
        [
            Paragraph("<b>Target Audience:</b> Fisheries Scientists, Oceanographers, Marine Resource Managers", table_cell_style),
            Paragraph("<b>Coverage:</b> 2018–2024 (84 monthly observation cycles)", table_cell_style),
        ],
        [
            Paragraph("<b>Primary Domains:</b> Satellite Ocean Color, SST Climatology, CMFRI Landings", table_cell_style),
            Paragraph("<b>Geographic Scope:</b> 5 Indian Maritime Sectors (Malabar, Mannar, Saurashtra, Konkan, Coromandel)", table_cell_style),
        ]
    ]
    t_meta = Table(meta_data, colWidths=[3.8 * inch, 3.8 * inch])
    t_meta.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#F0FDFA")),
        ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor("#99F6E4")),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CCFBF1")),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
        ('RIGHTPADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(t_meta)
    story.append(Spacer(1, 10))

    # Section 1: Executive Overview
    story.append(Paragraph("1. Executive Overview & Problem Statement", h1_style))
    story.append(Paragraph(
        "A central problem in coastal marine resource management is answering: <i>'Why has fish productivity declined in a specific coastal region?'</i> "
        "Standard fishing advisories provide only operational short-term forecasts (e.g. today's wave height or immediate potential fishing zones), "
        "leaving researchers without longitudinal ecological diagnostic capabilities. "
        "Tarang bridges this gap by cross-referencing multi-sensor satellite oceanography (thermal regimes and phytoplankton biomass) with long-term "
        "commercial landing statistics to automatically isolate causal mechanisms (e.g., Marine Heatwave thermal displacement, delayed upwelling, or recruitment overfishing).",
        body_style
    ))

    # Section 2: Core Data Provenance & Extraction Protocols
    story.append(Paragraph("2. Primary Data Sources & Scientific Specifications", h1_style))
    
    source_table_data = [
        [
            Paragraph("Parameter", table_header_style),
            Paragraph("Agency & Sensor", table_header_style),
            Paragraph("Resolution & Cadence", table_header_style),
            Paragraph("Extraction Protocol / Endpoint", table_header_style),
            Paragraph("Analytical Role", table_header_style),
        ],
        [
            Paragraph("<b>Sea Surface Temperature (SST)</b>", table_cell_bold),
            Paragraph("NOAA / NCEI & INCOIS<br/>(AVHRR + In-situ OISST v2.1)", table_cell_style),
            Paragraph("0.25° grid (~25 km)<br/>Daily binned to Monthly", table_cell_style),
            Paragraph("REST / OPeNDAP Griddap:<br/><code>coastwatch.pfeg.noaa.gov/erddap</code>", table_cell_style),
            Paragraph("Thermal regime, stratification, thermocline depth, Marine Heatwaves (MHW >= +1.5°C).", table_cell_style),
        ],
        [
            Paragraph("<b>Chlorophyll-a (CHL)</b>", table_cell_bold),
            Paragraph("ISRO / INCOIS Oceansat-2 OCM + NASA MODIS-Aqua / VIIRS", table_cell_style),
            Paragraph("4 km & 9 km grids<br/>Monthly Level-3 composite", table_cell_style),
            Paragraph("NASA OB.DAAC & INCOIS Ocean Color Portal (SMI arrays)", table_cell_style),
            Paragraph("Primary productivity proxy, diatom bloom onset, upwelling efficiency, trophic deficits (Z <= -1.5).", table_cell_style),
        ],
        [
            Paragraph("<b>Commercial Fish Landings & CPUE</b>", table_cell_bold),
            Paragraph("ICAR - Central Marine Fisheries Research Institute (CMFRI)", table_cell_style),
            Paragraph("Maritime State / Region<br/>Monthly aggregated (2018–2024)", table_cell_style),
            Paragraph("CMFRI National Marine Fish Landings Bulletins & FIMS", table_cell_style),
            Paragraph("Empirical harvest telemetry: metric tonnes, Catch Per Unit Effort (kg/hr), MSY baseline benchmarks.", table_cell_style),
        ],
        [
            Paragraph("<b>Near Real-Time Marine Weather</b>", table_cell_bold),
            Paragraph("ECMWF ERA5 + DWD ICON via Open-Meteo", table_cell_style),
            Paragraph("0.1° grid (~11 km)<br/>Hourly operational forecast", table_cell_style),
            Paragraph("Open-Meteo Marine & Forecast API (REST)", table_cell_style),
            Paragraph("Significant wave height (Hs), swell period, surface wind speeds, real-time artisanal boat safety.", table_cell_style),
        ],
    ]

    t_sources = Table(source_table_data, colWidths=[1.4*inch, 1.6*inch, 1.3*inch, 1.7*inch, 1.6*inch])
    t_sources.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), c_primary),
        ('BOX', (0,0), (-1,-1), 0.5, c_border),
        ('INNERGRID', (0,0), (-1,-1), 0.5, c_border),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, c_bg_light]),
    ]))
    story.append(t_sources)
    story.append(Spacer(1, 10))

    # Section 3: Extraction & Alignment Methodology
    story.append(Paragraph("3. Step-by-Step Data Extraction & Processing Pipeline", h1_style))
    story.append(Paragraph("<b>Step 1: Spatial Sector Delimitation & Bathymetric Masking</b>", h2_style))
    story.append(Paragraph(
        "Each of the 5 coastal regions is bounded by a dedicated maritime geofence polygon (e.g. Malabar Coast: 8.5°N–12.0°N, 75.0°E–77.0°E). "
        "A bathymetric mask (< 200 m continental shelf isobath) is applied to discard open-ocean pelagic pixels, ensuring observations reflect "
        "the shallow coastal shelf where artisanal and mechanized near-shore fisheries operate.",
        body_style
    ))

    story.append(Paragraph("<b>Step 2: SST Extraction & Climatological Anomaly Computation</b>", h2_style))
    story.append(Paragraph(
        "Monthly Sea Surface Temperature is extracted via NOAA's OISST v2.1 reanalysis. For each month <i>m</i>, the observed SST is benchmarked "
        "against the 30-year climatological baseline &mu;<sub>SST, m</sub> (1991–2020 average for that calendar month):",
        body_style
    ))
    story.append(Paragraph("&nbsp;&nbsp;&nbsp;&nbsp;<b>&Delta;SST<sub>m</sub> = SST<sub>obs, m</sub> - &mu;<sub>baseline, m</sub></b>", code_style))
    story.append(Paragraph(
        "A <b>Marine Heatwave (MHW)</b> is formally flagged when &Delta;SST &ge; +1.5°C persists over the region.",
        bullet_style
    ))

    story.append(Paragraph("<b>Step 3: Chlorophyll-a Normalization & Z-Score Anomaly Detection</b>", h2_style))
    story.append(Paragraph(
        "Satellite ocean color chlorophyll-a concentrations (&mu;g/L or mg/m³) exhibit high seasonal variability driven by the southwest monsoon upwelling. "
        "To identify genuine primary productivity deficits rather than normal winter troughs, observations are converted to standardized monthly Z-scores:",
        body_style
    ))
    story.append(Paragraph("&nbsp;&nbsp;&nbsp;&nbsp;<b>Z<sub>CHL, m</sub> = (CHL<sub>obs, m</sub> - &mu;<sub>CHL, m</sub>) / &sigma;<sub>CHL, m</sub></b>", code_style))
    story.append(Paragraph(
        "A <b>Trophic Deficit</b> is classified when Z<sub>CHL</sub> &le; -1.5, signaling significant primary phytoplankton collapse.",
        bullet_style
    ))

    story.append(Paragraph("<b>Step 4: CMFRI Catch Statistics Alignment & CPUE Scaling</b>", h2_style))
    story.append(Paragraph(
        "Monthly commercial landings are extracted from CMFRI national bulletins. Landings are correlated with effort hours to compute Catch Per Unit Effort "
        "(CPUE in kg/hour). Landings are benchmarked against historical 5-year rolling averages to identify stock decline windows (> 30% drop below replacement).",
        body_style
    ))

    story.append(PageBreak())

    # Section 4: Mathematical Modeling & Statistical Synthesis
    story.append(Paragraph("4. Mathematical Formulations & Causal Attribution Engine", h1_style))
    story.append(Paragraph(
        "The automated diagnosis engine in <code>backend/tools/ecosystem_analytics.py</code> computes statistical relationships in real-time across user-selected windows:",
        body_style
    ))

    stats_data = [
        [
            Paragraph("Statistical Metric", table_header_style),
            Paragraph("Mathematical Formula", table_header_style),
            Paragraph("Oceanographic / Ecological Interpretation", table_header_style),
        ],
        [
            Paragraph("<b>Trophic Coupling (CHL &harr; Catch)</b>", table_cell_bold),
            Paragraph("<b>r<sub>CHL, Catch</sub> = &Sigma;(x - &mu;<sub>x</sub>)(y - &mu;<sub>y</sub>) / [&radic;&Sigma;(x - &mu;<sub>x</sub>)<sup>2</sup> &radic;&Sigma;(y - &mu;<sub>y</sub>)<sup>2</sup>]</b>", code_style),
            Paragraph("Quantifies bottom-up biological dependency. High positive correlation confirms that larval survival and schooling biomass are directly sustained by coastal diatom blooms.", table_cell_style),
        ],
        [
            Paragraph("<b>Thermal Displacement (SST &harr; Catch)</b>", table_cell_bold),
            Paragraph("<b>r<sub>&Delta;SST, Catch</sub></b> (Pearson correlation with <i>p</i>-value)", code_style),
            Paragraph("Negative correlation indicates thermal displacement: anomalous surface warming forces stenothermal pelagics (Oil Sardine) to dive below 30 m or migrate poleward, escaping artisanal gear.", table_cell_style),
        ],
        [
            Paragraph("<b>Upwelling Efficiency (SST &harr; CHL)</b>", table_cell_bold),
            Paragraph("<b>r<sub>SST, CHL</sub></b> (Monthly lagged correlation)", code_style),
            Paragraph("Evaluates coastal upwelling strength. Strong negative correlation proves that cold, nutrient-rich deep water is the essential prerequisite for primary biological production.", table_cell_style),
        ],
        [
            Paragraph("<b>Composite Ecological Stress Index</b>", table_cell_bold),
            Paragraph("<b>Score = w<sub>1</sub>(MHW_ratio) + w<sub>2</sub>(CHL_deficit_ratio) + w<sub>3</sub>(Catch_drop_ratio)</b>", code_style),
            Paragraph("Normalized 0–100 score classifying regional marine ecosystem health into Nominal, Moderate Stress, or Severe Disruption.", table_cell_style),
        ],
    ]
    t_stats = Table(stats_data, colWidths=[2.2*inch, 2.7*inch, 2.7*inch])
    t_stats.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), c_secondary),
        ('BOX', (0,0), (-1,-1), 0.5, c_border),
        ('INNERGRID', (0,0), (-1,-1), 0.5, c_border),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, c_bg_light]),
    ]))
    story.append(t_stats)
    story.append(Spacer(1, 10))

    # Section 5: Architecture Overview
    story.append(Paragraph("5. Tarang Dual-Track Data Architecture", h1_style))
    story.append(Paragraph(
        "Tarang employs a decoupled architecture separating high-speed longitudinal research analytics from real-time vessel safety operations:",
        body_style
    ))

    arch_data = [
        [
            Paragraph("Dimension", table_header_style),
            Paragraph("Track A: Researcher Longitudinal Engine", table_header_style),
            Paragraph("Track B: Operational Fishing Safety Engine", table_header_style),
        ],
        [
            Paragraph("<b>Primary User</b>", table_cell_bold),
            Paragraph("Fisheries researchers, marine biologists, state fisheries depts.", table_cell_style),
            Paragraph("Artisanal fishermen, boat masters, harbour safety officers.", table_cell_style),
        ],
        [
            Paragraph("<b>Temporal Scope</b>", table_cell_bold),
            Paragraph("2018–2024 (Monthly continuous longitudinal series).", table_cell_style),
            Paragraph("Real-time (Nowcast + 24–72 hour operational forecast).", table_cell_style),
        ],
        [
            Paragraph("<b>Storage & Access</b>", table_cell_bold),
            Paragraph("Pre-compiled unified schema (<code>fisheries_productivity_timeseries.json</code>) with instant client-side SVG rendering.", table_cell_style),
            Paragraph("Live REST APIs (INCOIS ERDDAP, Open-Meteo Marine, IMD, GDACS) with 60-minute in-memory TTL caching.", table_cell_style),
        ],
        [
            Paragraph("<b>AI Interface</b>", table_cell_bold),
            Paragraph("Dedicated Bio-Oceanographic AI Fellow grounded in empirical correlation vectors, MHW counts, and CMFRI reports.", table_cell_style),
            Paragraph("Multilingual Voice & SMS Agent (Hindi, Tamil, Malayalam, Bengali) for daily wave & safety advisories.", table_cell_style),
        ],
    ]
    t_arch = Table(arch_data, colWidths=[1.8*inch, 2.9*inch, 2.9*inch])
    t_arch.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), c_teal),
        ('BOX', (0,0), (-1,-1), 0.5, c_border),
        ('INNERGRID', (0,0), (-1,-1), 0.5, c_border),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, c_bg_light]),
    ]))
    story.append(t_arch)
    story.append(Spacer(1, 10))

    # Section 6: How the AI Uses It
    story.append(Paragraph("6. Bio-Oceanographic AI Grounding & Anti-Hallucination Protocol", h1_style))
    story.append(Paragraph(
        "To ensure the Researcher AI Chatbot remains scientifically rigorous and never produces generic or fabricated answers, "
        "Tarang enforces a strict context injection protocol:",
        body_style
    ))
    story.append(Paragraph("1. <b>Zero Hallucination Grounding:</b> The user's query is never sent in isolation. The system dynamically computes the exact Pearson <i>r</i>, <i>p</i>-values, MHW episode counts, and deficit months for the active region and time window, injecting them directly into the LLM system prompt.", bullet_style))
    story.append(Paragraph("2. <b>Causal Attribution Taxonomy:</b> The model is constrained to evaluate three scientifically validated marine decline mechanisms: (a) Thermal Stratification & Thermocline Deepening, (b) Trophic Larval Starvation via Diatom Bloom Delay, and (c) Post-Spawning Recruitment Overfishing.", bullet_style))
    story.append(Paragraph("3. <b>Policy & Intervention Linking:</b> Every diagnostic attribution maps to actionable management recommendations (e.g., dynamic seasonal ban adjustments, minimum legal size enforcement, and artificial reef nursery deployment).", bullet_style))

    # Footer note
    story.append(Spacer(1, 12))
    story.append(HRFlowable(width="100%", thickness=0.5, color=c_muted, spaceAfter=6))
    story.append(Paragraph(
        "<i>Generated by Tarang Bio-Oceanographic Suite · Document Version 1.0 · Grounded in INCOIS, NOAA OISST v2.1, and ICAR-CMFRI Marine Landings</i>",
        ParagraphStyle("Footer", parent=styles["Normal"], fontName="Helvetica-Oblique", fontSize=7.5, textColor=c_muted, alignment=1)
    ))

    doc.build(story)
    print(f"PDF successfully generated at: {output_path}")

if __name__ == "__main__":
    out1 = os.path.abspath("c:/Users/HP/OneDrive/Desktop/Tarang/Tarang/Tarang_Researcher_Data_Extraction_Methodology.pdf")
    create_pdf(out1)
    out2 = os.path.abspath("c:/Users/HP/OneDrive/Desktop/Tarang/Tarang/frontend/public/Tarang_Researcher_Data_Extraction_Methodology.pdf")
    create_pdf(out2)
