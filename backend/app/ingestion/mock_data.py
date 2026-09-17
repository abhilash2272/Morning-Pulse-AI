"""
app/ingestion/mock_data.py
===========================
Realistic sample data for development / test mode.

When USE_MOCK_DATA=true (or --mock flag is passed), every collector
returns data from this module instead of calling external APIs.

Sample set demonstrates:
  1. NVIDIA announcement (GDELT article)
  2. Microsoft AI announcement (GDELT article)
  3. NVIDIA SEC 10-K filing
  4. Research/industry article about AI chips
  5. Exact duplicate of sample 1 (same URL)
  6. Two articles about the same event (story clustering demo)
"""

from __future__ import annotations

from datetime import datetime, timezone


def _dt(year: int, month: int, day: int) -> datetime:
    return datetime(year, month, day, 10, 0, 0, tzinfo=timezone.utc)


# ================================================================== #
# GDELT mock records
# ================================================================== #
def get_mock_gdelt_records() -> list[dict]:
    return [
        {
            "title": "NVIDIA Announces Breakthrough H200 AI Chip for Data Centers",
            "url": "https://techcrunch.com/2024/01/15/nvidia-h200-ai-chip-announcement",
            "domain": "techcrunch.com",
            "tone": "7.5",
            "language": "English",
            "seendate": "20240115T100000Z",
            "_query": "NVIDIA",
        },
        {
            "title": "Microsoft Integrates OpenAI GPT-4 Across Azure Cloud Platform",
            "url": "https://www.theverge.com/2024/01/16/microsoft-azure-gpt4-integration",
            "domain": "theverge.com",
            "tone": "6.2",
            "language": "English",
            "seendate": "20240116T120000Z",
            "_query": "Microsoft",
        },
        # Exact duplicate of record 1 — same URL, should be caught by L1 dedup
        {
            "title": "NVIDIA Announces Breakthrough H200 AI Chip for Data Centers",
            "url": "https://techcrunch.com/2024/01/15/nvidia-h200-ai-chip-announcement",
            "domain": "techcrunch.com",
            "tone": "7.5",
            "language": "English",
            "seendate": "20240115T100000Z",
            "_query": "NVIDIA",
        },
        # Related article — same event (NVIDIA H200), different source → story cluster
        {
            "title": "NVIDIA H200 GPU Unveiled: What It Means for the AI Industry",
            "url": "https://arstechnica.com/2024/01/15/nvidia-h200-analysis",
            "domain": "arstechnica.com",
            "tone": "6.8",
            "language": "English",
            "seendate": "20240115T143000Z",
            "_query": "NVIDIA",
        },
        {
            "title": "Apple Reports Record iPhone Sales in Q4 2023 Earnings Call",
            "url": "https://reuters.com/2024/01/17/apple-q4-earnings-iphone",
            "domain": "reuters.com",
            "tone": "4.1",
            "language": "English",
            "seendate": "20240117T090000Z",
            "_query": "Apple",
        },
        {
            "title": "Tesla Faces Recall of 200,000 Vehicles Over Software Defect",
            "url": "https://bloomberg.com/2024/01/18/tesla-recall-software",
            "domain": "bloomberg.com",
            "tone": "-3.2",
            "language": "English",
            "seendate": "20240118T110000Z",
            "_query": "Tesla",
        },
        {
            "title": "Semiconductor Industry Revenue Expected to Reach $600B in 2024",
            "url": "https://semiengineering.com/2024/01/14/semiconductor-revenue-2024-forecast",
            "domain": "semiengineering.com",
            "tone": "5.0",
            "language": "English",
            "seendate": "20240114T080000Z",
            "_query": "semiconductor",
        },
        {
            "title": "Artificial Intelligence Investment Surpasses $100 Billion Globally",
            "url": "https://ft.com/2024/01/13/ai-investment-100-billion",
            "domain": "ft.com",
            "tone": "5.5",
            "language": "English",
            "seendate": "20240113T070000Z",
            "_query": "artificial intelligence",
        },
    ]


# ================================================================== #
# SEC EDGAR mock records
# ================================================================== #
def get_mock_sec_records() -> list[dict]:
    return [
        {
            "company": {
                "ticker": "NVDA",
                "company_name": "NVIDIA Corporation",
                "cik": "0001045810",
            },
            "cik": "0001045810",
            "ticker": "NVDA",
            "company_name": "NVIDIA Corporation",
            "form": "10-K",
            "filing_date": "2024-01-10",
            "accession_number": "0001045810-24-000010",
            "primary_document": "nvda-20240128.htm",
            "description": "Annual Report",
            "filing_url": "https://www.sec.gov/Archives/edgar/data/1045810/000104581024000010/nvda-20240128.htm",
            "content": (
                "NVIDIA Corporation Annual Report on Form 10-K for the fiscal year ended January 28, 2024. "
                "NVIDIA designs and markets graphics processing units (GPUs) and system-on-chip units (SoCs). "
                "The company reported record revenue of $60.9 billion for fiscal year 2024, driven primarily "
                "by strong demand for its data center AI computing products including the H100 GPU. "
                "Data Center segment revenue grew 217% year-over-year to $47.5 billion. "
                "The company continues to invest heavily in AI infrastructure and next-generation GPU architectures."
            ),
        },
        {
            "company": {
                "ticker": "MSFT",
                "company_name": "Microsoft Corporation",
                "cik": "0000789019",
            },
            "cik": "0000789019",
            "ticker": "MSFT",
            "company_name": "Microsoft Corporation",
            "form": "8-K",
            "filing_date": "2024-01-12",
            "accession_number": "0000789019-24-000012",
            "primary_document": "msft-20240112.htm",
            "description": "Quarterly Earnings",
            "filing_url": "https://www.sec.gov/Archives/edgar/data/789019/000078901924000012/msft-20240112.htm",
            "content": (
                "Microsoft Corporation Form 8-K filed January 12, 2024. "
                "Microsoft reports second quarter fiscal year 2024 results. "
                "Revenue was $62.0 billion, increasing 18% year-over-year. "
                "Azure and other cloud services revenue grew 28%. "
                "AI-powered features including Copilot are being integrated across the Microsoft 365 product suite. "
                "The company raised its quarterly dividend by 10%."
            ),
        },
        {
            "company": {
                "ticker": "AAPL",
                "company_name": "Apple Inc.",
                "cik": "0000320193",
            },
            "cik": "0000320193",
            "ticker": "AAPL",
            "company_name": "Apple Inc.",
            "form": "10-Q",
            "filing_date": "2024-01-08",
            "accession_number": "0000320193-24-000008",
            "primary_document": "aapl-20231230.htm",
            "description": "Quarterly Report",
            "filing_url": "https://www.sec.gov/Archives/edgar/data/320193/000032019324000008/aapl-20231230.htm",
            "content": (
                "Apple Inc. Form 10-Q for the quarter ended December 30, 2023. "
                "Net sales for the quarter were $119.6 billion, up 2% from the prior-year quarter. "
                "iPhone revenue was $69.7 billion. Services revenue reached a record $23.1 billion. "
                "The company generated $39.9 billion in operating cash flow during the quarter. "
                "Apple Vision Pro, the company's spatial computing headset, will begin shipping in February 2024."
            ),
        },
    ]


# ================================================================== #
# Official company mock records
# ================================================================== #
def get_mock_official_records() -> list[dict]:
    nvidia_company = {
        "ticker": "NVDA",
        "company_name": "NVIDIA Corporation",
        "cik": "0001045810",
        "news_url": "https://nvidianews.nvidia.com/",
    }
    microsoft_company = {
        "ticker": "MSFT",
        "company_name": "Microsoft Corporation",
        "cik": "0000789019",
        "news_url": "https://news.microsoft.com/",
    }

    return [
        {
            "_source": "rss",
            "company": nvidia_company,
            "title": "NVIDIA Announces H200 Tensor Core GPU: World's Most Powerful for Generative AI",
            "url": "https://nvidianews.nvidia.com/news/nvidia-h200",
            "summary": (
                "NVIDIA today announced the H200 Tensor Core GPU, featuring HBM3e memory "
                "with 141GB capacity and 4.8TB/s bandwidth. The H200 delivers up to 2x faster "
                "inference for large language models compared to H100."
            ),
            "content": (
                "NVIDIA today announced the NVIDIA H200 Tensor Core GPU, the world's most powerful "
                "GPU for generative AI and high-performance computing workloads. Built on the Hopper "
                "architecture, the H200 features 141 gigabytes of HBM3e memory with 4.8 terabytes "
                "per second of memory bandwidth. The H200 delivers up to 2x faster inference performance "
                "on large language models compared to the NVIDIA H100 Tensor Core GPU. Systems featuring "
                "H200 GPUs are expected to be available from major cloud providers and server manufacturers "
                "in the second quarter of 2024."
            ),
            "published_at": _dt(2024, 1, 15),
            "author": "NVIDIA Press",
            "tags": ["GPU", "AI", "HBM3e", "Data Center"],
        },
        # Related article — same H200 announcement event, from company official source
        {
            "_source": "rss",
            "company": nvidia_company,
            "title": "NVIDIA H200 GPU: Technical Specifications and Partner Availability",
            "url": "https://nvidianews.nvidia.com/news/nvidia-h200-specs",
            "summary": "Detailed technical breakdown of the NVIDIA H200 GPU specifications and OEM partner availability.",
            "content": (
                "NVIDIA has released detailed technical specifications for the H200 Tensor Core GPU. "
                "The H200 uses the same GH100 die as the H100 but is paired with HBM3e memory instead of HBM3. "
                "Key specifications: 141GB HBM3e, 4.8TB/s bandwidth, 3.35TB/s for NVLink, 900GB/s for PCIe 5.0. "
                "Partners including Dell, HPE, Lenovo, and Supermicro have announced H200-based server platforms. "
                "Cloud providers AWS, Google Cloud, and Microsoft Azure are expected to offer H200 instances."
            ),
            "published_at": _dt(2024, 1, 15),
            "author": "NVIDIA Technical Team",
            "tags": ["GPU", "H200", "Specifications"],
        },
        {
            "_source": "rss",
            "company": microsoft_company,
            "title": "Microsoft Copilot: AI-Powered Assistance Now Available Across Microsoft 365",
            "url": "https://news.microsoft.com/2024/01/16/microsoft-copilot-m365",
            "summary": "Microsoft announces general availability of Copilot across Microsoft 365 commercial plans.",
            "content": (
                "Microsoft today announced that Microsoft 365 Copilot is now generally available across "
                "all Microsoft 365 commercial plans. Powered by large language models from OpenAI, Copilot "
                "integrates with Word, Excel, PowerPoint, Outlook, and Teams to provide AI-powered assistance. "
                "Early customer results show significant productivity improvements: users report saving on "
                "average 1.2 hours per week. More than 40% of Fortune 500 companies are now using Copilot."
            ),
            "published_at": _dt(2024, 1, 16),
            "author": "Microsoft Press",
            "tags": ["Copilot", "AI", "Microsoft 365", "Productivity"],
        },
    ]


# ================================================================== #
# Research / industry mock records
# ================================================================== #
def get_mock_research_records() -> list[dict]:
    mit_tr_cfg = {
        "source_name": "MIT Technology Review",
        "category": "technology",
        "base_url": "https://www.technologyreview.com",
    }
    venturebeat_cfg = {
        "source_name": "VentureBeat",
        "category": "ai_technology",
        "base_url": "https://venturebeat.com",
    }
    semi_eng_cfg = {
        "source_name": "Semiconductor Engineering",
        "category": "semiconductor",
        "base_url": "https://semiengineering.com",
    }

    return [
        {
            "_source_config": mit_tr_cfg,
            "title": "The Race to Build the Most Powerful AI Chip Has Only Just Begun",
            "url": "https://www.technologyreview.com/2024/01/14/ai-chip-race",
            "content": (
                "The competition among chip companies to build the most powerful processors for "
                "artificial intelligence is intensifying. NVIDIA currently dominates the market for "
                "AI training chips with its H100 and upcoming H200 GPUs. However, competitors including "
                "AMD, Intel, and a wave of AI-chip startups are challenging that dominance. Google's TPUs, "
                "Amazon's Trainium, and Microsoft's Maia chips are being deployed internally to reduce "
                "dependence on NVIDIA. Analysts estimate the AI chip market will exceed $100 billion by 2027."
            ),
            "summary": "Analysis of the intensifying competition in the AI chip market.",
            "published_at": _dt(2024, 1, 14),
            "authors": ["Rebecca Ackermann"],
            "tags": ["AI", "chips", "semiconductor", "NVIDIA"],
        },
        {
            "_source_config": venturebeat_cfg,
            "title": "Large Language Models Are Getting Cheaper: What That Means for Enterprise AI",
            "url": "https://venturebeat.com/2024/01/13/llm-cost-reduction-enterprise",
            "content": (
                "The cost to run large language model inference has fallen dramatically over the past year. "
                "OpenAI's GPT-4 API now costs approximately 30 times less per token than it did in early 2023. "
                "This cost reduction is enabling a new wave of enterprise AI applications that were previously "
                "economically unviable. Companies across healthcare, finance, and legal services are building "
                "LLM-powered workflows at scale. Analysts predict enterprise AI spending will reach $50 billion "
                "in 2024, up from $12 billion in 2022."
            ),
            "summary": "LLM inference costs have fallen dramatically, enabling enterprise AI adoption.",
            "published_at": _dt(2024, 1, 13),
            "authors": ["Sharon Goldman"],
            "tags": ["LLM", "enterprise AI", "cost", "GPT-4"],
        },
        {
            "_source_config": semi_eng_cfg,
            "title": "HBM3e Memory: Why High-Bandwidth Memory Is Critical for AI Acceleration",
            "url": "https://semiengineering.com/2024/01/12/hbm3e-ai-acceleration",
            "content": (
                "High Bandwidth Memory (HBM) has become one of the most critical components in modern "
                "AI accelerators. The latest generation, HBM3e, provides memory bandwidth of up to "
                "4.8 terabytes per second — essential for feeding the massive appetite of large AI models. "
                "SK Hynix and Samsung are the primary suppliers of HBM3e, with Micron entering the market. "
                "Memory bandwidth is increasingly the primary bottleneck for large language model inference, "
                "making HBM capacity and bandwidth key competitive differentiators in the AI chip market."
            ),
            "summary": "Technical analysis of HBM3e memory and its role in AI chip performance.",
            "published_at": _dt(2024, 1, 12),
            "authors": ["Brian Bailey"],
            "tags": ["HBM3e", "memory", "semiconductor", "AI chips"],
        },
        {
            "_source_config": venturebeat_cfg,
            "title": "Meta Open-Sources Llama 3: Implications for the AI Industry",
            "url": "https://venturebeat.com/2024/01/11/meta-llama-3-open-source",
            "content": (
                "Meta Platforms has open-sourced Llama 3, the latest version of its large language model. "
                "Llama 3 comes in 8B, 70B, and 400B parameter variants. Benchmarks show Llama 3-70B "
                "approaching GPT-4 performance on several tasks while remaining freely available for "
                "commercial use. The release has significant implications for the enterprise AI market: "
                "companies can now fine-tune powerful open-source models on proprietary data without "
                "sharing that data with a third-party API provider."
            ),
            "summary": "Meta releases Llama 3 open-source LLM, challenging proprietary models.",
            "published_at": _dt(2024, 1, 11),
            "authors": ["Carl Franzen"],
            "tags": ["Meta", "Llama", "open-source", "LLM"],
        },
    ]
