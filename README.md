# 📦 End-to-End SAP Supply Chain Control Tower

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://ogola-supply-chain-tower.streamlit.app)

An enterprise-grade **Supply Chain Control Tower** integrating cloud data pipelines, machine learning demand forecasting, embedded SQL analytics, and automated alerting.

---

## 🚀 Live Demo
🔗 **Access Dashboard:** [ogola-supply-chain-tower.streamlit.app](https://ogola-supply-chain-tower.streamlit.app)

---

## 🏗️ System Architecture

```text
┌─────────────────────────┐
│      Google Colab       │
│  • Data Cleaning        │
│  • Holt-Winters ML      │
│  • Newsvendor / ABC-XYZ │
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐      ┌───────────────────────────┐
│     AWS S3 Data Lake    │ ───► │ Streamlit Dashboard +     │
│   (Raw, Silver, Gold)   │      │ DuckDB SQL Engine         │
└────────────┬────────────┘      └───────────────────────────┘
             │
             ▼
┌────────────────────────────────────────────────────────────┐
│                  Automated Event Monitoring                │
│   EventBridge (Schedule) ──► Lambda ──► SNS Email Alerts   │
│                          └─► CloudWatch (Health Check)     │
└────────────────────────────────────────────────────────────┘
