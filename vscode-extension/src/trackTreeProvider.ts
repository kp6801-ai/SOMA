import * as vscode from 'vscode';
import { somaApi, Track } from './api';

export class TrackTreeProvider implements vscode.TreeDataProvider<TrackItem> {
    private _onDidChangeTreeData = new vscode.EventEmitter<TrackItem | undefined>();
    readonly onDidChangeTreeData = this._onDidChangeTreeData.event;

    private tracks: Track[] = [];
    private groupBy: 'none' | 'artist' | 'bpm' | 'camelot' = 'none';

    refresh(): void {
        this.tracks = [];
        this._onDidChangeTreeData.fire(undefined);
    }

    setGroupBy(mode: 'none' | 'artist' | 'bpm' | 'camelot'): void {
        this.groupBy = mode;
        this._onDidChangeTreeData.fire(undefined);
    }

    getTreeItem(element: TrackItem): vscode.TreeItem {
        return element;
    }

    async getChildren(element?: TrackItem): Promise<TrackItem[]> {
        if (element) {
            return element.children || [];
        }

        if (this.tracks.length === 0) {
            try {
                const result = await somaApi.getTracks();
                this.tracks = result.tracks;
            } catch (err: unknown) {
                const msg = err instanceof Error ? err.message : String(err);
                vscode.window.showWarningMessage(`SOMA: ${msg}`);
                return [new TrackItem('Could not load tracks', '', vscode.TreeItemCollapsibleState.None)];
            }
        }

        if (this.tracks.length === 0) {
            return [new TrackItem('No tracks in library', '', vscode.TreeItemCollapsibleState.None)];
        }

        if (this.groupBy === 'none') {
            return this.tracks.map((t) => trackToItem(t));
        }

        return this.grouped();
    }

    private grouped(): TrackItem[] {
        const groups = new Map<string, Track[]>();
        for (const t of this.tracks) {
            let key: string;
            switch (this.groupBy) {
                case 'artist':
                    key = t.artist || 'Unknown';
                    break;
                case 'bpm':
                    key = t.bpm ? `${Math.round(t.bpm / 5) * 5} BPM` : 'Unknown BPM';
                    break;
                case 'camelot':
                    key = t.camelot || 'Unknown Key';
                    break;
                default:
                    key = 'All';
            }
            if (!groups.has(key)) { groups.set(key, []); }
            groups.get(key)!.push(t);
        }

        const sorted = [...groups.entries()].sort((a, b) => a[0].localeCompare(b[0]));
        return sorted.map(([label, tracks]) => {
            const item = new TrackItem(
                `${label}  (${tracks.length})`,
                '',
                vscode.TreeItemCollapsibleState.Collapsed,
            );
            item.children = tracks.map((t) => trackToItem(t));
            return item;
        });
    }
}

function trackToItem(t: Track): TrackItem {
    const bpmStr = t.bpm ? `${Math.round(t.bpm)}` : '?';
    const camelotStr = t.camelot || '?';
    const label = `${t.artist} — ${t.title}`;
    const desc = `${bpmStr} BPM · ${camelotStr}`;

    const item = new TrackItem(label, desc, vscode.TreeItemCollapsibleState.None);
    item.contextValue = 'track';
    item.trackData = t;
    item.tooltip = new vscode.MarkdownString(
        `**${t.title}**  \n` +
        `${t.artist}  \n\n` +
        `| | |\n|---|---|\n` +
        `| BPM | ${bpmStr} |\n` +
        `| Key | ${t.key || '?'} (${camelotStr}) |\n` +
        `| Energy | ${t.energy ?? '?'} |\n` +
        `| Duration | ${t.duration ? `${Math.round(t.duration)}s` : '?'} |\n` +
        (t.energy_tag ? `| Tag | ${t.energy_tag} |\n` : '') +
        (t.label ? `| Label | ${t.label} |\n` : '') +
        (t.era ? `| Era | ${t.era} |\n` : '')
    );
    item.command = {
        command: 'soma.showTrackDetails',
        title: 'Show Track Details',
        arguments: [t],
    };
    return item;
}

export class TrackItem extends vscode.TreeItem {
    children?: TrackItem[];
    trackData?: Track;

    constructor(
        label: string,
        description: string,
        collapsibleState: vscode.TreeItemCollapsibleState,
    ) {
        super(label, collapsibleState);
        this.description = description;
    }
}
