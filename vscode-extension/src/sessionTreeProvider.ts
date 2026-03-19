import * as vscode from 'vscode';

interface SessionEntry {
    sessionId: number;
    arcType: string;
    arcLabel: string;
    totalTracks: number;
    status: string;
}

export class SessionTreeProvider implements vscode.TreeDataProvider<SessionItem> {
    private _onDidChangeTreeData = new vscode.EventEmitter<SessionItem | undefined>();
    readonly onDidChangeTreeData = this._onDidChangeTreeData.event;

    private sessions: SessionEntry[] = [];

    addSession(entry: SessionEntry): void {
        this.sessions.unshift(entry);
        this._onDidChangeTreeData.fire(undefined);
    }

    updateStatus(sessionId: number, status: string): void {
        const s = this.sessions.find((x) => x.sessionId === sessionId);
        if (s) {
            s.status = status;
            this._onDidChangeTreeData.fire(undefined);
        }
    }

    getTreeItem(element: SessionItem): vscode.TreeItem {
        return element;
    }

    async getChildren(element?: SessionItem): Promise<SessionItem[]> {
        if (element) { return []; }

        if (this.sessions.length === 0) {
            const placeholder = new SessionItem(
                'No sessions yet',
                'Use "SOMA: Start DJ Session" to begin',
                vscode.TreeItemCollapsibleState.None,
            );
            return [placeholder];
        }

        return this.sessions.map((s) => {
            const icon = s.status === 'completed'
                ? new vscode.ThemeIcon('check')
                : new vscode.ThemeIcon('play');
            const item = new SessionItem(
                `#${s.sessionId} — ${s.arcLabel}`,
                `${s.totalTracks} tracks · ${s.status}`,
                vscode.TreeItemCollapsibleState.None,
            );
            item.iconPath = icon;
            item.sessionData = s;
            return item;
        });
    }
}

export class SessionItem extends vscode.TreeItem {
    sessionData?: SessionEntry;

    constructor(
        label: string,
        description: string,
        collapsibleState: vscode.TreeItemCollapsibleState,
    ) {
        super(label, collapsibleState);
        this.description = description;
    }
}
