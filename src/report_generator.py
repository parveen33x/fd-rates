"""
HTML Comparison Report Generator.
Builds an interactive, searchable HTML report comparing ET Money vs Official bank FD rates.
"""

from typing import List
from src.models import BankRecord, AuditSummary


def generate_html_report(dataset: List[BankRecord], summary: AuditSummary) -> str:
    """Generates a complete standalone HTML comparison dashboard."""
    cards_html = []

    for b in dataset:
        tables_html = []
        for tbl in b.tables:
            rows_html = []
            for r in tbl.rows:
                status_class = ""
                badge_class = ""
                if r.status == "RATE_HIKE":
                    status_class = "row-hike"
                    badge_class = "badge badge-hike"
                elif r.status == "RATE_CUT":
                    status_class = "row-cut"
                    badge_class = "badge badge-cut"
                elif r.status == "NEW_SLAB":
                    status_class = "row-new"
                    badge_class = "badge badge-new"

                g_off = f"{r.off_gen:.2f}%" if r.off_gen is not None else "--"
                s_off = f"{r.off_sr:.2f}%" if r.off_sr is not None else "--"
                g_etm = f"{r.etm_gen:.2f}%" if r.etm_gen is not None else "--"
                s_etm = f"{r.etm_sr:.2f}%" if r.etm_sr is not None else "--"

                rows_html.append(f"""
                <tr class="{status_class}">
                    <td><span class="{badge_class}">{r.status}</span></td>
                    <td><strong>{r.tenure}</strong></td>
                    <td>{g_etm}</td>
                    <td>{s_etm}</td>
                    <td><strong>{g_off}</strong></td>
                    <td><strong>{s_off}</strong></td>
                    <td><small>{r.change_details}</small></td>
                </tr>
                """)

            tables_html.append(f"""
            <div class="table-wrapper">
                <h4>{tbl.table_title}</h4>
                <div class="meta-dates">
                    <span>📌 {tbl.etm_updated or 'ET Money'}</span>
                    <span>⚡ {tbl.official_updated or 'Official Update Date'}</span>
                    {f'<a href="{tbl.official_link}" target="_blank" rel="noopener">🔗 Official Source</a>' if tbl.official_link else ''}
                </div>
                <table>
                    <thead>
                        <tr>
                            <th>Status</th>
                            <th>Tenure / Slab</th>
                            <th>ETM Gen</th>
                            <th>ETM Sr</th>
                            <th>Official Gen</th>
                            <th>Official Sr</th>
                            <th>Diff Details</th>
                        </tr>
                    </thead>
                    <tbody>
                        {''.join(rows_html)}
                    </tbody>
                </table>
            </div>
            """)

        cards_html.append(f"""
        <div class="bank-card">
            <div class="bank-header">
                <h3>{b.bank_name} <span class="category">({b.category})</span></h3>
                <div class="links">
                    {f'<a href="{b.etm_url}" target="_blank">ET Money Page</a>' if b.etm_url else ''}
                    {f'<a href="{b.official_url_retail}" target="_blank">Official Portal</a>' if b.official_url_retail else ''}
                </div>
            </div>
            {''.join(tables_html)}
        </div>
        """)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>FD Rates Comparison Report (2026)</title>
  <style>
    :root {{
      --primary: #064e3b;
      --secondary: #1e3a8a;
      --bg: #f8fafc;
      --card: #ffffff;
      --border: #e2e8f0;
      --hike-bg: #dcfce7;
      --hike-text: #166534;
      --cut-bg: #fee2e2;
      --cut-text: #991b1b;
      --new-bg: #fef3c7;
      --new-text: #92400e;
    }}
    * {{ box-sizing: border-box; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }}
    body {{ margin: 0; padding: 24px; background: var(--bg); color: #0f172a; }}
    .header-box {{
      background: linear-gradient(135deg, #064e3b, #0d9488);
      color: #fff;
      padding: 24px;
      border-radius: 12px;
      margin-bottom: 24px;
      box-shadow: 0 4px 16px rgba(0,0,0,0.06);
    }}
    .header-box h1 {{ margin: 0 0 8px 0; font-size: 24px; }}
    .stats-bar {{
      display: flex; gap: 16px; flex-wrap: wrap; margin-top: 16px;
    }}
    .stat-pill {{
      background: rgba(255,255,255,0.18);
      padding: 8px 16px;
      border-radius: 20px;
      font-size: 14px;
      font-weight: 500;
    }}
    .bank-card {{
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 20px;
      margin-bottom: 20px;
      box-shadow: 0 2px 8px rgba(0,0,0,0.02);
    }}
    .bank-header {{
      display: flex; justify-content: space-between; align-items: center;
      border-bottom: 1px solid var(--border);
      padding-bottom: 12px; margin-bottom: 16px;
    }}
    .bank-header h3 {{ margin: 0; font-size: 18px; }}
    .bank-header .category {{ font-size: 13px; color: #64748b; font-weight: normal; }}
    .bank-header .links a {{ margin-left: 12px; font-size: 13px; color: #0284c7; text-decoration: none; }}
    .table-wrapper {{ margin-bottom: 20px; }}
    .table-wrapper h4 {{ margin: 0 0 8px 0; font-size: 15px; color: #334155; }}
    .meta-dates {{ font-size: 12px; color: #64748b; display: flex; gap: 14px; margin-bottom: 10px; }}
    .meta-dates a {{ color: #0284c7; text-decoration: none; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
    th, td {{ padding: 10px 12px; text-align: left; border-bottom: 1px solid var(--border); }}
    th {{ background: #f1f5f9; color: #475569; font-weight: 600; }}
    .row-hike {{ background-color: var(--hike-bg); }}
    .row-cut {{ background-color: var(--cut-bg); }}
    .row-new {{ background-color: var(--new-bg); }}
    .badge {{ display: inline-block; padding: 3px 8px; border-radius: 4px; font-size: 11px; font-weight: 700; }}
    .badge-hike {{ background: #bbf7d0; color: var(--hike-text); }}
    .badge-cut {{ background: #fecaca; color: var(--cut-text); }}
    .badge-new {{ background: #fde68a; color: var(--new-text); }}
  </style>
</head>
<body>
  <div class="header-box">
    <h1>Autonomous FD Rate Audit & Diff Dashboard (2026)</h1>
    <p>Last Crawled & Audited: {summary.generated_at}</p>
    <div class="stats-bar">
      <div class="stat-pill">🏦 Total Banks: {summary.total_banks}</div>
      <div class="stat-pill">⚠️ Changed Banks: {len(summary.changed_banks)}</div>
      <div class="stat-pill">🟢 Rate Hikes: {summary.total_hikes}</div>
      <div class="stat-pill">🔴 Rate Cuts: {summary.total_cuts}</div>
      <div class="stat-pill">🟡 New Slabs: {summary.total_new_slabs}</div>
    </div>
  </div>

  <div class="content-body">
    {''.join(cards_html)}
  </div>
</body>
</html>
"""
