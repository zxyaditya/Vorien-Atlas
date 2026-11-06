import React, { useState } from "react";
import axios from "axios";
import { API } from "../../lib/helpers";

export function ProjectReport({ project }) {
  const [reportText, setReportText] = useState("");
  const [loading, setLoading] = useState(false);

  const generateReport = async () => {
    setLoading(true);
    try {
      // Fetch data for the report
      const [notesRes, expRes, btRes] = await Promise.all([
        axios.get(`${API}/projects/${project._id}/notes`),
        axios.get(`${API}/learning/experiments`),
        axios.get(`${API}/learning/backtest/list`)
      ]);

      const notes = notesRes.data || [];
      const exps = (expRes.data || []).slice(0, 3); // top 3 experiments
      const bts = (btRes.data || []).slice(0, 3);   // top 3 backtests

      let md = `# Research Report: ${project.name}\n\n`;
      md += `*Generated: ${new Date().toLocaleString()}*\n\n`;
      
      md += `## 1. Project Overview\n\n`;
      md += `${project.description || "No description provided."}\n\n`;
      
      md += `## 2. Research Notes & Findings\n\n`;
      if (notes.length === 0) {
        md += `*No research notes recorded.*\n\n`;
      } else {
        notes.forEach(n => {
          md += `### [${n.type}] ${n.title}\n`;
          if (n.body) md += `${n.body}\n`;
          if (n.resolution_status === "Resolved") {
            md += `**Resolution:** ${n.resolution_note || "Resolved"}\n`;
          }
          md += `\n`;
        });
      }

      md += `## 3. Top Model Experiments\n\n`;
      if (exps.length === 0) {
        md += `*No experiments recorded.*\n\n`;
      } else {
        md += `| Experiment | Model | Accuracy | F1 Score |\n`;
        md += `|------------|-------|----------|----------|\n`;
        exps.forEach(e => {
          const acc = e.aggregate?.accuracy_mean ? (e.aggregate.accuracy_mean * 100).toFixed(1) + "%" : "N/A";
          const f1 = e.aggregate?.f1_macro_mean ? (e.aggregate.f1_macro_mean * 100).toFixed(1) + "%" : "N/A";
          md += `| ${e.name} | ${e.model?.kind || "unknown"} | ${acc} | ${f1} |\n`;
        });
        md += `\n`;
      }

      md += `## 4. Backtest Simulations\n\n`;
      if (bts.length === 0) {
        md += `*No backtests recorded.*\n\n`;
      } else {
        bts.forEach(b => {
          md += `### Backtest ID: ${b.backtest_id.substring(0,8)}\n`;
          md += `- **Universe:** ${b.spec?.symbol} (${b.spec?.provider})\n`;
          md += `- **Period:** ${b.spec?.period} @ ${b.spec?.interval}\n`;
          if (b.metrics) {
            md += `- **Return:** ${(b.metrics.total_return_pct * 100).toFixed(2)}%\n`;
            md += `- **Sharpe:** ${b.metrics.sharpe_ratio?.toFixed(2) || "N/A"}\n`;
            md += `- **Max Drawdown:** ${(b.metrics.max_drawdown_pct * 100).toFixed(2)}%\n`;
          }
          md += `\n`;
        });
      }
      
      md += `## 5. Conclusions\n\n`;
      md += `*(Edit this section to provide your final conclusions and next steps for the research project)*\n`;

      setReportText(md);
    } catch (err) {
      console.error(err);
      alert("Failed to generate report");
    } finally {
      setLoading(false);
    }
  };

  const copyToClipboard = () => {
    navigator.clipboard.writeText(reportText).then(() => {
      alert("Report copied to clipboard!");
    });
  };

  const downloadReport = () => {
    const blob = new Blob([reportText], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `atlas_report_${project.name.replace(/\s+/g, "_").toLowerCase()}.md`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div style={{ padding: 32, maxWidth: 1000, margin: "0 auto", height: "100%", display: "flex", flexDirection: "column" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", marginBottom: 24, flexShrink: 0 }}>
        <div>
          <h2 style={{ fontSize: 24, fontWeight: 400, color: "var(--text-primary)", margin: "0 0 8px 0" }}>Project Report</h2>
          <div style={{ fontSize: 13, color: "var(--text-secondary)" }}>Synthesize notes, experiments, and backtests into a shareable research document.</div>
        </div>
        <div style={{ display: "flex", gap: 12 }}>
          {reportText && (
            <>
              <button className="btn btn-secondary" onClick={copyToClipboard}>
                Copy to Clipboard
              </button>
              <button className="btn btn-secondary" onClick={downloadReport}>
                Download .md
              </button>
            </>
          )}
          <button className="btn btn-primary" onClick={generateReport} disabled={loading}>
            {loading ? "Gathering Data..." : reportText ? "Regenerate Template" : "Generate Template"}
          </button>
        </div>
      </div>

      {reportText ? (
        <div style={{ flex: 1, overflow: "hidden", display: "flex", flexDirection: "column" }}>
          <textarea
            className="input"
            style={{ flex: 1, resize: "none", fontFamily: "var(--font-mono)", fontSize: 13, lineHeight: 1.6, padding: 24 }}
            value={reportText}
            onChange={(e) => setReportText(e.target.value)}
          />
        </div>
      ) : (
        <div className="page-empty" style={{ flex: 1, display: "flex", flexDirection: "column", justifyContent: "center" }}>
          <div className="page-empty-title">Ready to Publish?</div>
          <div className="page-empty-desc">Click "Generate Report" to automatically compile your research findings.</div>
        </div>
      )}
    </div>
  );
}
