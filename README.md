# Autonomous Data Analyst Agent

**Turn raw spreadsheets into executive-ready PowerPoint reports—automatically.**

A production-grade, serverless data analyst that ingests spreadsheets from Google Drive, cleans and interprets the data, generates insights and charts, and ships a branded PowerPoint deck for each relevant department. It is designed for non-technical stakeholders who need decision-ready summaries without manual analysis.

---

## What This Project Does

- Monitors a Google Drive **Clean_Data** folder for new datasets.
- Self-heals schema changes (renamed or new columns) and adapts on the fly.
- Computes KPIs, trends, outliers, and data-quality metrics.
- Generates structured, executive-grade narratives using AI prompts.
- Builds a **branded PPTX** report per department, only when relevant.
- Stores and compares historical results using Supabase to enable variance analysis.
- Runs serverlessly on Modal with cron scheduling and webhook support.

---

## Why It Matters For Businesses

- **Faster decisions:** Executives receive structured insights without waiting on manual analysis.
- **Consistency:** Every report follows a standardized business narrative and brand style.
- **Scalable analytics:** Multiple departments receive tailored insights from the same dataset.
- **Operational efficiency:** Data ingestion, analysis, visualization, and delivery are fully automated.
- **Comparative intelligence:** Past vs. current performance is captured for trend analysis.

---

## Key Capabilities

- **Automated ingestion** from Google Drive with failed/processed workflows.
- **Schema self-healing** that adapts to evolving datasets.
- **Department routing** so only relevant reports are generated.
- **Executive narrative generation** that follows a structured business flow.
- **QuickChart visualizations** embedded directly into slides.
- **Branded PPTX output** aligned with provided brand guidelines.
- **Serverless execution** with Modal cron and on-demand runs.

---

## Output Format

Each report follows a structured narrative:

- Cover Page
- Executive Summary
- Objectives / Business Questions
- Data Overview
- Methodology
- Key Findings
- Insights & Interpretation
- Department-Specific Analysis
- Variance / Comparative Analysis
- Risks & Limitations
- Recommendations
- Conclusion
- Next Steps
- Appendix

---

## Tech Stack

<table>
  <tr>
    <td align="center" valign="middle">
  <img src="https://www.python.org/static/img/python-logo.png" alt="Python" width="56" height="56" /><br/>
  <strong>Python</strong>
</td>
    <td align="center" valign="middle">
  <img src="https://pandas.pydata.org/static/img/pandas_white.svg" alt="Pandas" width="56" height="56" /><br/>
  <strong>Pandas</strong>
</td>
    <td align="center" valign="middle">
  <img src="https://duckdb.org/images/logo-dl/DuckDB_Logo-horizontal.svg" alt="DuckDB" width="56" height="56" /><br/>
  <strong>DuckDB</strong>
</td>
  </tr>
  <tr>
    <td align="center" valign="middle">
  <img src="https://www.python.org/static/img/python-logo.png" alt="python-pptx" width="56" height="56" /><br/>
  <strong>python-pptx</strong>
</td>
    <td align="center" valign="middle">
  <img src="https://ssl.gstatic.com/images/branding/product/2x/drive_2020q4_48dp.png" alt="Google Drive API" width="56" height="56" /><br/>
  <strong>Google Drive API</strong>
</td>
    <td align="center" valign="middle">
  <img src="https://play-lh.googleusercontent.com/Eh-N9HKWJgQ4Oa5wmhaE5RbHkB3m3Ud9tsW6saUHis05BL7Xnpubi5iamR5lDKd-Ew=w480-h960-rw" alt="Google Auth / OAuth" width="56" height="56" /><br/>
  <strong>Google Auth / OAuth</strong>
</td>
    <td align="center" valign="middle">
  <img src="https://console.groq.com/groq-logo.svg" alt="Groq API" width="56" height="56" /><br/>
  <strong>Groq API</strong>
</td>
  </tr>
  <tr>
    <td align="center" valign="middle">
  <img src="https://fastapi.tiangolo.com/img/logo-margin/logo-teal.png" alt="FastAPI" width="56" height="56" /><br/>
  <strong>FastAPI</strong>
</td>
    <td align="center" valign="middle">
  <img src="https://uvicorn.dev/uvicorn.png" alt="Uvicorn" width="56" height="56" /><br/>
  <strong>Uvicorn</strong>
</td>
    <td align="center" valign="middle">
  <img src="https://rwqqrnsxhishecvdnalx.supabase.co/storage/v1/object/public/assets/ab2659bd-e948-4236-a6eb-57f254741e11/9f2b47cc-81fd-4acb-9470-e2c84b058181.svg" alt="Modal" width="56" height="56" /><br/>
  <strong>Modal</strong>
</td>
    <td align="center" valign="middle">
  <img src="https://miro.medium.com/1*pnSzmFJRCJztS7tkSJXYuQ.jpeg" alt="Supabase" width="56" height="56" /><br/>
  <strong>Supabase</strong>
</td>
  </tr>
  <tr>
    <td align="center" valign="middle">
  <img src="https://quickchart.io/images/bar_chart_logo.svg" alt="QuickChart" width="56" height="56" /><br/>
  <strong>QuickChart</strong>
</td>
    <td align="center" valign="middle">
  <img src="https://git-scm.com/images/logos/downloads/Git-Icon-1788C.png" alt="Git" width="56" height="56" /><br/>
  <strong>Git</strong>
</td>
    <td align="center" valign="middle">
  <img src="https://github.githubassets.com/images/modules/logos_page/GitHub-Mark.png" alt="GitHub" width="56" height="56" /><br/>
  <strong>GitHub</strong>
</td>
    <td></td>
  </tr>
</table>

### Supporting Libraries

- Requests
- OpenPyXL
- python-dotenv

---

## Special Thanks

This project stands on the shoulders of these excellent tools and platforms:

- Python
- Pandas
- DuckDB
- python-pptx
- Google Drive API
- Google Auth / OAuth
- Groq API
- FastAPI
- Uvicorn
- Modal
- Supabase
- QuickChart
- Requests
- OpenPyXL
- python-dotenv
- Git
- GitHub

---

## Author

**Sein Muwana**

---

If you want a live demo deck or want to adapt this agent to your organization, just reach out.
