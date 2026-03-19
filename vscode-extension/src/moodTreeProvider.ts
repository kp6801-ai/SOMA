import * as vscode from 'vscode';
import { somaApi, Mood } from './api';

export class MoodTreeProvider implements vscode.TreeDataProvider<MoodItem> {
    private _onDidChangeTreeData = new vscode.EventEmitter<MoodItem | undefined>();
    readonly onDidChangeTreeData = this._onDidChangeTreeData.event;

    private moods: Mood[] = [];

    refresh(): void {
        this.moods = [];
        this._onDidChangeTreeData.fire(undefined);
    }

    getTreeItem(element: MoodItem): vscode.TreeItem {
        return element;
    }

    async getChildren(element?: MoodItem): Promise<MoodItem[]> {
        if (element) {
            return [];
        }

        if (this.moods.length === 0) {
            try {
                const result = await somaApi.getMoods();
                this.moods = result.moods;
            } catch (err: unknown) {
                const msg = err instanceof Error ? err.message : String(err);
                vscode.window.showWarningMessage(`SOMA: ${msg}`);
                return [];
            }
        }

        return this.moods.map((m) => {
            const [lo, hi] = m.bpm_range;
            const item = new MoodItem(
                m.name,
                `${lo}–${hi} BPM`,
                vscode.TreeItemCollapsibleState.None,
            );
            item.moodData = m;
            item.tooltip = new vscode.MarkdownString(
                `**${m.name}**  \n` +
                `${m.description}  \n\n` +
                `BPM: ${lo}–${hi}  \n` +
                (m.compatible_subgenres.length
                    ? `Compatible: ${m.compatible_subgenres.join(', ')}`
                    : '')
            );
            item.command = {
                command: 'soma.browseByMood',
                title: 'Browse by Mood',
                arguments: [m.name],
            };
            return item;
        });
    }
}

export class MoodItem extends vscode.TreeItem {
    moodData?: Mood;

    constructor(
        label: string,
        description: string,
        collapsibleState: vscode.TreeItemCollapsibleState,
    ) {
        super(label, collapsibleState);
        this.description = description;
        this.iconPath = new vscode.ThemeIcon('symbol-color');
    }
}
