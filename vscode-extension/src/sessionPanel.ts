import * as vscode from 'vscode';
import { Session, SessionTrack } from './api';

export class SessionPanel {
    public static currentPanel: SessionPanel | undefined;
    private static readonly viewType = 'somaSession';

    private readonly panel: vscode.WebviewPanel;
    private session: Session;
    private disposables: vscode.Disposable[] = [];

    private constructor(panel: vscode.WebviewPanel, session: Session) {
        this.panel = panel;
        this.session = session;

        this.update();

        this.panel.onDidDispose(() => this.dispose(), null, this.disposables);
    }

    public static show(extensionUri: vscode.Uri, session: Session): SessionPanel {
        if (SessionPanel.currentPanel) {
            SessionPanel.currentPanel.session = session;
            SessionPanel.currentPanel.update();
            SessionPanel.currentPanel.panel.reveal(vscode.ViewColumn.Beside);
            return SessionPanel.currentPanel;
        }

        const panel = vscode.window.createWebviewPanel(
            SessionPanel.viewType,
            `SOMA Session #${session.session_id}`,
            vscode.ViewColumn.Beside,
            { enableScripts: false },
        );

        SessionPanel.currentPanel = new SessionPanel(panel, session);
        return SessionPanel.currentPanel;
    }

    public updateSession(session: Session): void {
        this.session = session;
        this.update();
    }

    private update(): void {
        this.panel.title = `SOMA #${this.session.session_id} — ${this.session.arc_label}`;
        this.panel.webview.html = this.getHtml();
    }

    private getHtml(): string {
        const s = this.session;
        const trackRows = s.tracks.map((t: SessionTrack) => {
            const statusIcon = t.status === 'completed' ? '&#9745;'
                : t.status === 'skipped' ? '&#9744;'
                : t.status === 'playing' ? '&#9654;'
                : '&middot;';
            const scoreStr = t.score !== undefined ? t.score.toFixed(3) : '';
            return `<tr>
                <td style="text-align:center">${statusIcon}</td>
                <td>${t.position}</td>
                <td><strong>${esc(t.title)}</strong><br><span class="dim">${esc(t.artist)}</span></td>
                <td>${Math.round(t.bpm)}</td>
                <td>${Math.round(t.target_bpm)}</td>
                <td>${t.camelot || '?'}</td>
                <td>${scoreStr}</td>
            </tr>`;
        }).join('\n');

        return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
    body { font-family: var(--vscode-font-family); color: var(--vscode-foreground); padding: 16px; }
    h1 { font-size: 1.4em; margin-bottom: 4px; }
    .meta { opacity: 0.7; margin-bottom: 16px; font-size: 0.9em; }
    .badge { display: inline-block; padding: 2px 8px; border-radius: 4px;
             background: var(--vscode-badge-background); color: var(--vscode-badge-foreground);
             font-size: 0.8em; margin-right: 6px; }
    table { width: 100%; border-collapse: collapse; font-size: 0.85em; }
    th { text-align: left; padding: 6px 8px; border-bottom: 1px solid var(--vscode-panel-border);
         opacity: 0.7; font-weight: 600; font-size: 0.78em; text-transform: uppercase; letter-spacing: 0.05em; }
    td { padding: 5px 8px; border-bottom: 1px solid var(--vscode-panel-border); vertical-align: top; }
    .dim { opacity: 0.6; font-size: 0.88em; }
    .arc-bar { height: 6px; border-radius: 3px; background: var(--vscode-progressBar-background); margin: 8px 0 16px; }
</style>
</head>
<body>
    <h1>Session #${s.session_id}</h1>
    <div class="meta">
        <span class="badge">${esc(s.arc_label)}</span>
        <span class="badge">${s.duration_min} min</span>
        <span class="badge">${s.total_tracks} tracks</span>
        <span class="badge">${s.status}</span>
    </div>
    <div class="meta">BPM arc: ${s.bpm_start} &rarr; ${s.bpm_peak} &rarr; ${s.bpm_end}</div>
    <div class="arc-bar" style="width:100%"></div>
    <table>
        <thead>
            <tr>
                <th></th>
                <th>#</th>
                <th>Track</th>
                <th>BPM</th>
                <th>Target</th>
                <th>Key</th>
                <th>Score</th>
            </tr>
        </thead>
        <tbody>${trackRows}</tbody>
    </table>
</body>
</html>`;
    }

    private dispose(): void {
        SessionPanel.currentPanel = undefined;
        this.panel.dispose();
        for (const d of this.disposables) { d.dispose(); }
    }
}

function esc(s: string): string {
    return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}
