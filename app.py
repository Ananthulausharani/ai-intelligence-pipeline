import json
from pathlib import Path

import pandas as pd
import streamlit as st

# ---------------------------------------------------------
# Page configuration
# ---------------------------------------------------------

st.set_page_config(
    page_title="AI Intelligence Pipeline",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ---------------------------------------------------------
# Styling
# ---------------------------------------------------------

st.markdown(
    """
    <style>
        .main {
            background-color: #f7f9fc;
        }

        .block-container {
            padding-top: 2rem;
            padding-bottom: 2rem;
        }

        .dashboard-title {
            font-size: 2.2rem;
            font-weight: 700;
            color: #172033;
            margin-bottom: 0.2rem;
        }

        .dashboard-subtitle {
            color: #667085;
            font-size: 1rem;
            margin-bottom: 1.5rem;
        }

        .metric-card {
            background: white;
            padding: 1.2rem;
            border-radius: 14px;
            border: 1px solid #e6eaf0;
            box-shadow: 0 2px 8px rgba(16, 24, 40, 0.04);
        }

        .section-title {
            font-size: 1.35rem;
            font-weight: 650;
            color: #172033;
            margin-top: 1rem;
            margin-bottom: 0.8rem;
        }

        .info-box {
            background: #eef6ff;
            border-left: 4px solid #3b82f6;
            padding: 0.9rem 1rem;
            border-radius: 8px;
            margin-bottom: 1rem;
        }
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------
# Paths
# ---------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data" / "output"


# ---------------------------------------------------------
# Data loading
# ---------------------------------------------------------


@st.cache_data
def load_json(filename):
    """Load a JSON dataset from the pipeline output folder."""
    file_path = DATA_DIR / filename

    if not file_path.exists():
        return []

    with open(file_path, "r", encoding="utf-8") as file:
        return json.load(file)


# ---------------------------------------------------------
# Dataset preparation
# ---------------------------------------------------------


def prepare_startups(records):
    rows = []

    for record in records:
        content = record.get("content", {})
        data = content.get("data", {})

        rows.append(
            {
                "Startup": content.get("entityName"),
                "Employees": data.get("employeeCount"),
                "Website": data.get("website"),
                "Industries": ", ".join(data.get("industries", [])),
                "Description": data.get("description"),
                "Source": record.get("source", {}).get("name"),
                "Collected": record.get("collectedAt"),
            }
        )

    return pd.DataFrame(rows)


def prepare_products(records):
    rows = []

    for record in records:
        content = record.get("content", {})

        rows.append(
            {
                "Product": content.get("productName"),
                "Startup": content.get("startupName"),
                "Pricing": content.get("pricingModel"),
                "Product URL": content.get("product_url"),
                "Source": record.get("source", {}).get("name"),
                "Collected": record.get("collectedAt"),
            }
        )

    return pd.DataFrame(rows)


def prepare_research(records):
    rows = []

    for record in records:
        rows.append(
            {
                "Title": record.get("title") or record.get("content", {}).get("title"),
                "Authors": ", ".join(
                    record.get("authors")
                    or record.get("content", {}).get("authors", [])
                ),
                "Published": record.get("published_date")
                or record.get("content", {}).get("published_date"),
                "GitHub Stars": record.get("github_stars")
                or record.get("content", {}).get("github_stars"),
                "Paper URL": record.get("paper_url")
                or record.get("content", {}).get("paper_url"),
                "GitHub": record.get("github_url")
                or record.get("content", {}).get("github_url"),
                "Source": record.get("source", {}).get("name"),
                "Collected": record.get("collectedAt"),
            }
        )

    return pd.DataFrame(rows)


def prepare_jobs(records):
    rows = []

    for record in records:
        content = record.get("content", {})

        rows.append(
            {
                "Company": content.get("company"),
                "Role": content.get("role") or content.get("title"),
                "Date": content.get("date"),
                "Remote": content.get("is_remote"),
                "Job URL": content.get("url"),
                "Source": record.get("source", {}).get("name"),
                "Collected": record.get("collected_at"),
            }
        )

    return pd.DataFrame(rows)


def prepare_news(records):
    rows = []

    for record in records:
        content = record.get("content", {})

        rows.append(
            {
                "Title": content.get("title"),
                "Published": content.get("published_date"),
                "News URL": content.get("url"),
                "Source": record.get("source", {}).get("url"),
                "Collected": record.get("collected_at"),
            }
        )

    return pd.DataFrame(rows)


def prepare_entity_logs(records):
    rows = []

    for record in records:
        rows.append(
            {
                "Raw Name": record.get("raw_name"),
                "Canonical Name": record.get("canonical_name"),
                "Match Type": record.get("match_type"),
                "Entity Type": record.get("entity_type"),
                "Confidence": record.get("confidence"),
                "Reason": record.get("reason"),
            }
        )

    return pd.DataFrame(rows)


# ---------------------------------------------------------
# Load datasets
# ---------------------------------------------------------

startup_records = load_json("startups.json")
product_records = load_json("products.json")
research_records = load_json("research_papers.json")
job_records = load_json("jobs.json")
news_records = load_json("news.json")
entity_records = load_json("entity_mapping_logs.json")

startups_df = prepare_startups(startup_records)
products_df = prepare_products(product_records)
research_df = prepare_research(research_records)
jobs_df = prepare_jobs(job_records)
news_df = prepare_news(news_records)
entity_df = prepare_entity_logs(entity_records)


# ---------------------------------------------------------
# Sidebar
# ---------------------------------------------------------

st.sidebar.title("🚀 AI Intelligence")

st.sidebar.markdown("""
    **Pipeline Dashboard**

    Explore the latest collected intelligence across startups,
    products, research papers, jobs and technology news.
    """)

st.sidebar.divider()

dataset = st.sidebar.radio(
    "Explore Dataset",
    [
        "Overview",
        "Startups",
        "Products",
        "Research Papers",
        "Jobs",
        "News",
        "Entity Mapping",
    ],
)

st.sidebar.divider()

st.sidebar.caption("Data generated by AI Intelligence Pipeline")


# ---------------------------------------------------------
# Header
# ---------------------------------------------------------

st.markdown(
    '<div class="dashboard-title">🚀 AI Intelligence Pipeline</div>',
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="dashboard-subtitle">'
    "Automated collection, enrichment and analysis of startup, "
    "product, research and market intelligence."
    "</div>",
    unsafe_allow_html=True,
)


# ---------------------------------------------------------
# Overview
# ---------------------------------------------------------

# ---------------------------------------------------------
# Overview
# ---------------------------------------------------------

if dataset == "Overview":

    st.markdown(
        '<div class="section-title">Pipeline Overview</div>',
        unsafe_allow_html=True,
    )

    metrics = [
        ("Startups", len(startups_df)),
        ("Products", len(products_df)),
        ("Research Papers", len(research_df)),
        ("Jobs", len(jobs_df)),
        ("News", len(news_df)),
        ("Entity Mappings", len(entity_df)),
    ]

    for start_index in range(0, len(metrics), 3):
        cols = st.columns(3)

        for col, (label, value) in zip(
            cols,
            metrics[start_index:start_index + 3],
        ):
            with col:
                st.markdown(
                    f"""
                    <div class="metric-card">
                        <div style="color:#667085;font-size:0.9rem;">
                            {label}
                        </div>
                        <div style="font-size:1.9rem;font-weight:700;color:#172033;margin-top:0.2rem;">
                            {value:,}
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

        st.markdown("")

    st.markdown(
        '<div class="section-title">Core Intelligence</div>',
        unsafe_allow_html=True,
    )

    core_data = pd.DataFrame(
        {
            "Dataset": ["Startups", "Products", "Research Papers"],
            "Records": [
                len(startups_df),
                len(products_df),
                len(research_df),
            ],
        }
    )

    col1, col2 = st.columns([1.5, 1])

    with col1:
        st.markdown("#### Dataset Volume")
        st.bar_chart(
            core_data.set_index("Dataset"),
            height=300,
        )

    with col2:
        st.markdown("#### Collection Summary")

        total_core = (
            len(startups_df)
            + len(products_df)
            + len(research_df)
        )

        total_supporting = (
            len(jobs_df)
            + len(news_df)
            + len(entity_df)
        )

        st.metric(
            "Core intelligence records",
            f"{total_core:,}",
        )

        st.metric(
            "Supporting records",
            f"{total_supporting:,}",
        )

    st.markdown(
        '<div class="section-title">Supporting Intelligence</div>',
        unsafe_allow_html=True,
    )

    supporting_data = pd.DataFrame(
        {
            "Dataset": ["Jobs", "News", "Entity Mappings"],
            "Records": [
                len(jobs_df),
                len(news_df),
                len(entity_df),
            ],
        }
    )

    st.bar_chart(
        supporting_data.set_index("Dataset"),
        height=260,
    )

    st.markdown(
        '<div class="section-title">Pipeline Status</div>',
        unsafe_allow_html=True,
    )

    status_col1, status_col2, status_col3 = st.columns(3)

    with status_col1:
        st.success("Data available")

    with status_col2:
        st.info("Six datasets loaded")

    with status_col3:
        st.success("Dashboard ready")

    st.markdown(
        """
        <div class="info-box">
            <strong>About this dashboard</strong><br>
            This dashboard presents structured intelligence collected by
            the AI Intelligence Pipeline from multiple technology,
            startup, research, job and news sources.
        </div>
        """,
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------
# Startups
# ---------------------------------------------------------

elif dataset == "Startups":

    st.markdown("## 🏢 Startups")

    if startups_df.empty:
        st.warning("No startup data available.")
    else:
        col1, col2 = st.columns(2)

        with col1:
            industries = sorted(
                {
                    industry
                    for values in startups_df["Industries"].dropna()
                    for industry in values.split(", ")
                    if industry
                }
            )

            selected_industries = st.multiselect(
                "Filter by industry",
                industries,
            )

        with col2:
            search = st.text_input(
                "🔎 Search startups",
                placeholder="Search by startup name...",
            )

        filtered = startups_df.copy()

        if selected_industries:
            filtered = filtered[
                filtered["Industries"].apply(
                    lambda x: any(
                        industry in str(x) for industry in selected_industries
                    )
                )
            ]

        if search:
            filtered = filtered[
                filtered["Startup"]
                .fillna("")
                .str.contains(search, case=False, na=False)
            ]

        st.caption(f"Showing {len(filtered):,} of {len(startups_df):,} startups")

        st.dataframe(
            filtered,
            use_container_width=True,
            hide_index=True,
        )


# ---------------------------------------------------------
# Products
# ---------------------------------------------------------

elif dataset == "Products":

    st.markdown("## 📦 Products")

    if products_df.empty:
        st.warning("No product data available.")
    else:
        search = st.text_input(
            "🔎 Search products",
            placeholder="Search product or startup...",
        )

        filtered = products_df.copy()

        if search:
            mask = filtered["Product"].fillna("").str.contains(
                search, case=False, na=False
            ) | filtered["Startup"].fillna("").str.contains(
                search, case=False, na=False
            )

            filtered = filtered[mask]

        st.caption(f"Showing {len(filtered):,} of {len(products_df):,} products")

        st.dataframe(
            filtered,
            use_container_width=True,
            hide_index=True,
        )


# ---------------------------------------------------------
# Research Papers
# ---------------------------------------------------------

elif dataset == "Research Papers":

    st.markdown("## 📄 Research Papers")

    if research_df.empty:
        st.warning("No research paper data available.")
    else:
        search = st.text_input(
            "🔎 Search papers",
            placeholder="Search by title or author...",
        )

        filtered = research_df.copy()

        if search:
            mask = filtered["Title"].fillna("").str.contains(
                search, case=False, na=False
            ) | filtered["Authors"].fillna("").str.contains(
                search, case=False, na=False
            )

            filtered = filtered[mask]

        st.caption(f"Showing {len(filtered):,} of {len(research_df):,} papers")

        st.dataframe(
            filtered,
            use_container_width=True,
            hide_index=True,
        )


# ---------------------------------------------------------
# Jobs
# ---------------------------------------------------------

elif dataset == "Jobs":

    st.markdown("## 💼 Jobs")

    if jobs_df.empty:
        st.warning("No job data available.")
    else:
        col1, col2 = st.columns(2)

        with col1:
            remote_filter = st.selectbox(
                "Remote status",
                ["All", "Remote", "Not Remote"],
            )

        with col2:
            search = st.text_input(
                "🔎 Search jobs",
                placeholder="Search company or role...",
            )

        filtered = jobs_df.copy()

        if remote_filter == "Remote":
            filtered = filtered[filtered["Remote"] == True]
        elif remote_filter == "Not Remote":
            filtered = filtered[filtered["Remote"] == False]

        if search:
            mask = filtered["Company"].fillna("").str.contains(
                search, case=False, na=False
            ) | filtered["Role"].fillna("").str.contains(search, case=False, na=False)

            filtered = filtered[mask]

        st.caption(f"Showing {len(filtered):,} of {len(jobs_df):,} jobs")

        st.dataframe(
            filtered,
            use_container_width=True,
            hide_index=True,
        )


# ---------------------------------------------------------
# News
# ---------------------------------------------------------

elif dataset == "News":

    st.markdown("## 📰 Technology News")

    if news_df.empty:
        st.warning("No news data available.")
    else:
        search = st.text_input(
            "🔎 Search news",
            placeholder="Search article titles...",
        )

        filtered = news_df.copy()

        if search:
            filtered = filtered[
                filtered["Title"].fillna("").str.contains(search, case=False, na=False)
            ]

        st.caption(f"Showing {len(filtered):,} of {len(news_df):,} articles")

        st.dataframe(
            filtered,
            use_container_width=True,
            hide_index=True,
        )


# ---------------------------------------------------------
# Entity Mapping
# ---------------------------------------------------------

elif dataset == "Entity Mapping":

    st.markdown("## 🔗 Entity Mapping")

    if entity_df.empty:
        st.warning("No entity mapping data available.")
    else:
        col1, col2 = st.columns(2)

        with col1:
            match_types = sorted(entity_df["Match Type"].dropna().unique().tolist())

            selected_match = st.multiselect(
                "Match type",
                match_types,
            )

        with col2:
            entity_types = sorted(entity_df["Entity Type"].dropna().unique().tolist())

            selected_entity = st.multiselect(
                "Entity type",
                entity_types,
            )

        filtered = entity_df.copy()

        if selected_match:
            filtered = filtered[filtered["Match Type"].isin(selected_match)]

        if selected_entity:
            filtered = filtered[filtered["Entity Type"].isin(selected_entity)]

        st.caption(f"Showing {len(filtered):,} of {len(entity_df):,} mappings")

        st.dataframe(
            filtered,
            use_container_width=True,
            hide_index=True,
        )
