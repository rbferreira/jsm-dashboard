# HelpMe — JSM Service Desk Dashboard

Streamlit dashboard for monitoring and analyzing Jira Service Management (JSM) tickets. Provides real-time KPIs and interactive Plotly charts.

![Python 3.12](https://img.shields.io/badge/Python-3.12-blue)
![Streamlit](https://img.shields.io/badge/Streamlit-1.35+-red)
![License: MIT](https://img.shields.io/badge/License-MIT-green)

## Features

- **5 KPI cards** — total created, open, closed, avg resolution time, CSAT with star rating
- **8 interactive charts** — category/group/assignee distribution, opened vs closed, trend line, priority donut, open by month, CSAT by month
- **Switchable grid layout** — toggle between 3 and 4 column views
- **Filters** — period (today/week/month/custom), analyst, layout
- **Dark theme** with polished UI — shadows, gradients, hover effects
- **Containerized** — runs with Docker/Podman

## Quick Start

### 1. Clone and configure

```bash
git clone https://github.com/rbferreira/jsm-dashboard.git
cd jsm-dashboard
cp .env.example .env
# Edit .env with your Jira credentials
```

### 2. Run with Docker/Podman

```bash
docker-compose up --build -d
# or
podman-compose up --build -d
```

Dashboard available at **http://localhost:8501**

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `JIRA_BASE_URL` | Yes | — | Your Atlassian instance URL |
| `JIRA_EMAIL` | Yes | — | Jira account email |
| `JIRA_API_TOKEN` | Yes | — | Jira API token ([generate here](https://id.atlassian.com/manage-profile/security/api-tokens)) |
| `JIRA_PROJECT` | Yes | — | Jira project key |
| `CACHE_TTL_SECONDS` | No | `300` | Streamlit cache TTL |
| `JIRA_REQUEST_TYPE_FIELD` | No | `customfield_10700` | JSM request type custom field ID |
| `JIRA_CLOSED_STATUSES` | No | `Fechado,Resolvido` | Comma-separated status names treated as "closed" |

## Project Structure

```
.
├── app.py                  # Streamlit entry point
├── jira_client.py          # Jira REST API wrapper with retry logic
├── ui/
│   ├── styles.py           # Global CSS with dark theme
│   ├── charts.py           # 7 Plotly chart builders
│   └── components.py       # KPI cards, helpers
├── .streamlit/config.toml  # Streamlit theme config
├── Dockerfile              # Container with non-root user
├── podman-compose.yml      # Orchestration config
├── requirements.txt        # Python dependencies
├── test_jira.py            # Jira API diagnostic tool
└── .env.example            # Environment variable template
```

## Tech Stack

- **Python 3.12** + Streamlit + Plotly
- **Jira REST API v3** with cursor-based pagination
- **Docker/Podman** for containerization

## License

MIT
