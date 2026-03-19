import * as vscode from 'vscode';
import { somaApi, Track, Recommendation } from './api';
import { TrackTreeProvider, TrackItem } from './trackTreeProvider';
import { MoodTreeProvider } from './moodTreeProvider';
import { SessionTreeProvider } from './sessionTreeProvider';
import { SessionPanel } from './sessionPanel';

let trackTree: TrackTreeProvider;
let moodTree: MoodTreeProvider;
let sessionTree: SessionTreeProvider;

export function activate(context: vscode.ExtensionContext) {
    trackTree = new TrackTreeProvider();
    moodTree = new MoodTreeProvider();
    sessionTree = new SessionTreeProvider();

    vscode.window.registerTreeDataProvider('somaTracks', trackTree);
    vscode.window.registerTreeDataProvider('somaMoods', moodTree);
    vscode.window.registerTreeDataProvider('somaSessions', sessionTree);

    context.subscriptions.push(
        vscode.commands.registerCommand('soma.refreshTracks', () => {
            trackTree.refresh();
            moodTree.refresh();
            vscode.window.showInformationMessage('SOMA: Refreshing track library…');
        }),

        vscode.commands.registerCommand('soma.showTrackDetails', showTrackDetails),
        vscode.commands.registerCommand('soma.recommendFromTrack', recommendFromTrack),
        vscode.commands.registerCommand('soma.compatibleKeys', compatibleKeys),
        vscode.commands.registerCommand('soma.scoreTransition', scoreTransition),
        vscode.commands.registerCommand('soma.startSession', () => startSession(context)),
        vscode.commands.registerCommand('soma.browseByMood', browseByMood),
        vscode.commands.registerCommand('soma.bpmJourney', bpmJourney),
        vscode.commands.registerCommand('soma.findBridge', findBridge),
        vscode.commands.registerCommand('soma.digCrate', digCrate),
        vscode.commands.registerCommand('soma.setApiUrl', setApiUrl),
    );
}

export function deactivate() {}

// ─── Commands ────────────────────────────────────────────────

async function showTrackDetails(trackOrItem?: Track | TrackItem) {
    const track = resolveTrack(trackOrItem);
    if (!track) {
        vscode.window.showWarningMessage('SOMA: Select a track first.');
        return;
    }

    const doc = await vscode.workspace.openTextDocument({
        language: 'markdown',
        content: trackToMarkdown(track),
    });
    await vscode.window.showTextDocument(doc, { preview: true });
}

async function recommendFromTrack(trackOrItem?: Track | TrackItem) {
    const track = resolveTrack(trackOrItem);
    if (!track) {
        vscode.window.showWarningMessage('SOMA: Select a track first.');
        return;
    }

    await vscode.window.withProgress(
        { location: vscode.ProgressLocation.Notification, title: `SOMA: Finding tracks similar to "${track.title}"…` },
        async () => {
            try {
                const result = await somaApi.getSimilar(track.id, 10);
                const lines = [
                    `# Similar to: ${result.source.title} — ${result.source.artist}`,
                    `> ${result.source.bpm} BPM · ${result.source.camelot || '?'} · Method: ${result.method || 'memory'}`,
                    '',
                    '| # | Artist | Title | BPM | Key | Score |',
                    '|---|--------|-------|-----|-----|-------|',
                    ...result.similar.map((s, i) =>
                        `| ${i + 1} | ${s.artist} | ${s.title} | ${s.bpm} | ${s.camelot || '?'} | ${s.score.toFixed(3)} |`
                    ),
                ];
                const doc = await vscode.workspace.openTextDocument({
                    language: 'markdown',
                    content: lines.join('\n'),
                });
                await vscode.window.showTextDocument(doc, { preview: true });
            } catch (err: unknown) {
                showError(err);
            }
        },
    );
}

async function compatibleKeys(trackOrItem?: Track | TrackItem) {
    const track = resolveTrack(trackOrItem);
    if (!track || !track.camelot) {
        vscode.window.showWarningMessage('SOMA: Track has no Camelot key.');
        return;
    }

    try {
        const result = await somaApi.getCompatibleKeys(track.camelot);
        vscode.window.showInformationMessage(
            `Compatible with ${result.camelot}: ${result.compatible_keys.join(', ')}`
        );
    } catch (err: unknown) {
        showError(err);
    }
}

async function scoreTransition() {
    let tracks: Track[];
    try {
        const result = await somaApi.getTracks();
        tracks = result.tracks;
    } catch (err: unknown) {
        showError(err);
        return;
    }

    if (tracks.length < 2) {
        vscode.window.showWarningMessage('SOMA: Need at least 2 tracks to score a transition.');
        return;
    }

    const pickItems = tracks.map((t) => ({
        label: `${t.artist} — ${t.title}`,
        description: `${t.bpm ? Math.round(t.bpm) : '?'} BPM · ${t.camelot || '?'}`,
        track: t,
    }));

    const trackA = await vscode.window.showQuickPick(pickItems, { placeHolder: 'Select Track A (outgoing)' });
    if (!trackA) { return; }

    const trackB = await vscode.window.showQuickPick(
        pickItems.filter((p) => p.track.id !== trackA.track.id),
        { placeHolder: 'Select Track B (incoming)' },
    );
    if (!trackB) { return; }

    await vscode.window.withProgress(
        { location: vscode.ProgressLocation.Notification, title: 'SOMA: Scoring transition…' },
        async () => {
            try {
                const result = await somaApi.scoreTransition(trackA.track.id, trackB.track.id);
                const lines = [
                    `# Transition Score`,
                    '',
                    `**${trackA.label}** &rarr; **${trackB.label}**`,
                    '',
                    `| Metric | Value |`,
                    `|--------|-------|`,
                    `| Overall Score | **${result.score.toFixed(3)}** |`,
                    `| BPM Difference | ${result.bpm_diff.toFixed(1)} |`,
                    `| Camelot Distance | ${result.camelot_distance} |`,
                    `| Harmonic Score | ${result.harmonic_score.toFixed(2)} |`,
                    '',
                    '## Reasons',
                    ...result.reasons.map((r: string) => `- ${r}`),
                ];
                const doc = await vscode.workspace.openTextDocument({
                    language: 'markdown',
                    content: lines.join('\n'),
                });
                await vscode.window.showTextDocument(doc, { preview: true });
            } catch (err: unknown) {
                showError(err);
            }
        },
    );
}

async function startSession(context: vscode.ExtensionContext) {
    let arcTypes;
    try {
        arcTypes = (await somaApi.getArcTypes()).arc_types;
    } catch (err: unknown) {
        showError(err);
        return;
    }

    const arcPick = await vscode.window.showQuickPick(
        arcTypes.map((a) => ({
            label: a.label,
            description: `${a.bpm_start}–${a.bpm_peak} BPM`,
            detail: a.description,
            arc: a,
        })),
        { placeHolder: 'Choose session arc type' },
    );
    if (!arcPick) { return; }

    const durStr = await vscode.window.showInputBox({
        prompt: 'Session duration in minutes (15–180)',
        value: '60',
        validateInput: (v) => {
            const n = parseInt(v, 10);
            if (isNaN(n) || n < 5 || n > 480) { return 'Enter a number between 5 and 480'; }
            return undefined;
        },
    });
    if (!durStr) { return; }

    const duration = parseInt(durStr, 10);

    await vscode.window.withProgress(
        { location: vscode.ProgressLocation.Notification, title: `SOMA: Planning ${arcPick.label} session…` },
        async () => {
            try {
                const session = await somaApi.createSession(arcPick.arc.key, duration);
                sessionTree.addSession({
                    sessionId: session.session_id,
                    arcType: session.arc_type,
                    arcLabel: session.arc_label,
                    totalTracks: session.total_tracks,
                    status: session.status,
                });
                SessionPanel.show(context.extensionUri, session);
                vscode.window.showInformationMessage(
                    `SOMA: Session #${session.session_id} created — ${session.total_tracks} tracks planned.`
                );
            } catch (err: unknown) {
                showError(err);
            }
        },
    );
}

async function browseByMood(moodName?: string) {
    if (!moodName) {
        try {
            const moods = (await somaApi.getMoods()).moods;
            const pick = await vscode.window.showQuickPick(
                moods.map((m) => ({
                    label: m.name,
                    description: `${m.bpm_range[0]}–${m.bpm_range[1]} BPM`,
                    detail: m.description,
                })),
                { placeHolder: 'Select a mood / subgenre' },
            );
            if (!pick) { return; }
            moodName = pick.label;
        } catch (err: unknown) {
            showError(err);
            return;
        }
    }

    await vscode.window.withProgress(
        { location: vscode.ProgressLocation.Notification, title: `SOMA: Loading ${moodName} tracks…` },
        async () => {
            try {
                const result = await somaApi.getTracksByMood(moodName!, 20);
                const lines = [
                    `# ${moodName} Tracks`,
                    '',
                    '| # | Artist | Title | BPM | Key | Score | Reasons |',
                    '|---|--------|-------|-----|-----|-------|---------|',
                    ...result.recommendations.map((r: Recommendation, i: number) =>
                        `| ${i + 1} | ${r.artist} | ${r.title} | ${r.bpm} | ${r.camelot || '?'} | ${r.score.toFixed(3)} | ${r.reasons.join('; ')} |`
                    ),
                ];
                const doc = await vscode.workspace.openTextDocument({
                    language: 'markdown',
                    content: lines.join('\n'),
                });
                await vscode.window.showTextDocument(doc, { preview: true });
            } catch (err: unknown) {
                showError(err);
            }
        },
    );
}

async function bpmJourney() {
    const startBpm = await vscode.window.showInputBox({
        prompt: 'Starting BPM (60–200)',
        value: '120',
        validateInput: (v) => {
            const n = parseFloat(v);
            if (isNaN(n) || n < 60 || n > 200) { return 'Enter a BPM between 60 and 200'; }
            return undefined;
        },
    });
    if (!startBpm) { return; }

    const endBpm = await vscode.window.showInputBox({
        prompt: 'Target BPM (60–200)',
        value: '145',
        validateInput: (v) => {
            const n = parseFloat(v);
            if (isNaN(n) || n < 60 || n > 200) { return 'Enter a BPM between 60 and 200'; }
            return undefined;
        },
    });
    if (!endBpm) { return; }

    const stepsStr = await vscode.window.showInputBox({
        prompt: 'Number of steps (2–30)',
        value: '10',
        validateInput: (v) => {
            const n = parseInt(v, 10);
            if (isNaN(n) || n < 2 || n > 30) { return 'Enter a number between 2 and 30'; }
            return undefined;
        },
    });
    if (!stepsStr) { return; }

    await vscode.window.withProgress(
        { location: vscode.ProgressLocation.Notification, title: `SOMA: Planning BPM journey ${startBpm} → ${endBpm}…` },
        async () => {
            try {
                const result = await somaApi.bpmJourney(
                    parseFloat(startBpm), parseFloat(endBpm), parseInt(stepsStr, 10),
                );
                const lines = [
                    `# BPM Journey: ${result.start_bpm} → ${result.end_bpm}`,
                    '',
                    '| Step | Artist | Title | BPM | Key |',
                    '|------|--------|-------|-----|-----|',
                    ...result.journey.map((s, i) =>
                        `| ${i + 1} | ${s.artist} | ${s.title} | ${Math.round(s.bpm)} | ${s.camelot || '?'} |`
                    ),
                ];
                const doc = await vscode.workspace.openTextDocument({
                    language: 'markdown',
                    content: lines.join('\n'),
                });
                await vscode.window.showTextDocument(doc, { preview: true });
            } catch (err: unknown) {
                showError(err);
            }
        },
    );
}

async function findBridge() {
    let tracks: Track[];
    try {
        tracks = (await somaApi.getTracks()).tracks;
    } catch (err: unknown) {
        showError(err);
        return;
    }

    const pickItems = tracks.map((t) => ({
        label: `${t.artist} — ${t.title}`,
        description: `${t.bpm ? Math.round(t.bpm) : '?'} BPM · ${t.camelot || '?'}`,
        track: t,
    }));

    const source = await vscode.window.showQuickPick(pickItems, { placeHolder: 'Select the source track' });
    if (!source) { return; }

    const moods = (await somaApi.getMoods()).moods;
    const targetMood = await vscode.window.showQuickPick(
        [{ label: '(none)', description: 'No subgenre target' }, ...moods.map((m) => ({
            label: m.name,
            description: m.description,
        }))],
        { placeHolder: 'Target subgenre (optional)' },
    );

    const subgenre = targetMood && targetMood.label !== '(none)' ? targetMood.label : undefined;

    await vscode.window.withProgress(
        { location: vscode.ProgressLocation.Notification, title: 'SOMA: Finding bridge tracks…' },
        async () => {
            try {
                const result = await somaApi.findBridge(source.track.id, subgenre);
                const bridges = result.bridge_tracks || [];
                const lines = [
                    `# Bridge from: ${source.label}`,
                    subgenre ? `> Target subgenre: ${subgenre}` : '',
                    '',
                    '| Step | Artist | Title | BPM | Key |',
                    '|------|--------|-------|-----|-----|',
                    ...bridges.map((b, i) =>
                        `| ${i + 1} | ${b.artist} | ${b.title} | ${b.bpm} | ${b.camelot || '?'} |`
                    ),
                ];
                if (bridges.length === 0) {
                    lines.push('', '*No bridge tracks found.*');
                }
                const doc = await vscode.workspace.openTextDocument({
                    language: 'markdown',
                    content: lines.join('\n'),
                });
                await vscode.window.showTextDocument(doc, { preview: true });
            } catch (err: unknown) {
                showError(err);
            }
        },
    );
}

async function digCrate() {
    const label = await vscode.window.showInputBox({ prompt: 'Label name (optional)', placeHolder: 'e.g. Drumcode' });
    const bpmMinStr = await vscode.window.showInputBox({ prompt: 'Min BPM (optional)', placeHolder: 'e.g. 128' });
    const bpmMaxStr = await vscode.window.showInputBox({ prompt: 'Max BPM (optional)', placeHolder: 'e.g. 140' });
    const energyTag = await vscode.window.showInputBox({ prompt: 'Energy tag (optional)', placeHolder: 'e.g. peak, warmup, cooldown' });

    await vscode.window.withProgress(
        { location: vscode.ProgressLocation.Notification, title: 'SOMA: Digging crate…' },
        async () => {
            try {
                const result = await somaApi.digCrate({
                    label: label || undefined,
                    bpm_min: bpmMinStr ? parseFloat(bpmMinStr) : undefined,
                    bpm_max: bpmMaxStr ? parseFloat(bpmMaxStr) : undefined,
                    energy_tag: energyTag || undefined,
                    limit: 50,
                });
                const lines = [
                    `# Dig Crate — ${result.count} results`,
                    '',
                    '| # | Artist | Title | BPM | Key | Energy | Label | Era |',
                    '|---|--------|-------|-----|-----|--------|-------|-----|',
                    ...result.tracks.map((t, i) =>
                        `| ${i + 1} | ${t.artist} | ${t.title} | ${t.bpm ? Math.round(t.bpm) : '?'} | ${t.camelot || '?'} | ${t.energy_tag || ''} | ${t.label || ''} | ${t.era || ''} |`
                    ),
                ];
                const doc = await vscode.workspace.openTextDocument({
                    language: 'markdown',
                    content: lines.join('\n'),
                });
                await vscode.window.showTextDocument(doc, { preview: true });
            } catch (err: unknown) {
                showError(err);
            }
        },
    );
}

async function setApiUrl() {
    const current = vscode.workspace.getConfiguration('soma').get<string>('apiUrl') || 'http://localhost:8000/api';
    const url = await vscode.window.showInputBox({
        prompt: 'SOMA API base URL',
        value: current,
        placeHolder: 'http://localhost:8000/api',
    });
    if (url) {
        await vscode.workspace.getConfiguration('soma').update('apiUrl', url, vscode.ConfigurationTarget.Global);
        trackTree.refresh();
        moodTree.refresh();
        vscode.window.showInformationMessage(`SOMA: API URL set to ${url}`);
    }
}

// ─── Helpers ─────────────────────────────────────────────────

function resolveTrack(input?: Track | TrackItem): Track | undefined {
    if (!input) { return undefined; }
    if ('trackData' in input) { return input.trackData; }
    if ('id' in input) { return input as Track; }
    return undefined;
}

function trackToMarkdown(t: Track): string {
    return [
        `# ${t.title}`,
        `### ${t.artist}`,
        '',
        '| Property | Value |',
        '|----------|-------|',
        `| BPM | ${t.bpm ?? '?'} |`,
        `| Key | ${t.key || '?'} |`,
        `| Camelot | ${t.camelot || '?'} |`,
        `| Energy | ${t.energy ?? '?'} |`,
        `| Danceability | ${t.danceability ?? '?'} |`,
        `| Brightness | ${t.brightness ?? '?'} |`,
        `| Duration | ${t.duration ? `${Math.round(t.duration)}s` : '?'} |`,
        t.energy_tag ? `| Energy Tag | ${t.energy_tag} |` : '',
        t.label ? `| Label | ${t.label} |` : '',
        t.era ? `| Era | ${t.era} |` : '',
    ].filter(Boolean).join('\n');
}

function showError(err: unknown): void {
    const msg = err instanceof Error ? err.message : String(err);
    vscode.window.showErrorMessage(`SOMA: ${msg}`);
}
