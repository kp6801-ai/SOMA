import * as vscode from 'vscode';
import * as https from 'https';
import * as http from 'http';
import { URL } from 'url';

function getBaseUrl(): string {
    return vscode.workspace.getConfiguration('soma').get<string>('apiUrl')
        || 'http://localhost:8000/api';
}

function request<T>(method: string, path: string, body?: unknown): Promise<T> {
    const base = getBaseUrl();
    const url = new URL(`${base}${path}`);
    const transport = url.protocol === 'https:' ? https : http;

    return new Promise((resolve, reject) => {
        const options: http.RequestOptions = {
            hostname: url.hostname,
            port: url.port,
            path: url.pathname + url.search,
            method,
            headers: { 'Content-Type': 'application/json' },
        };

        const req = transport.request(options, (res) => {
            let data = '';
            res.on('data', (chunk) => (data += chunk));
            res.on('end', () => {
                if (res.statusCode && res.statusCode >= 400) {
                    reject(new Error(`SOMA API ${res.statusCode}: ${data}`));
                    return;
                }
                try {
                    resolve(JSON.parse(data));
                } catch {
                    reject(new Error(`Invalid JSON from SOMA API: ${data.slice(0, 200)}`));
                }
            });
        });

        req.on('error', (err) =>
            reject(new Error(`Cannot reach SOMA API at ${base}. Is the backend running? (${err.message})`))
        );

        if (body) {
            req.write(JSON.stringify(body));
        }
        req.end();
    });
}

function get<T>(path: string): Promise<T> {
    return request('GET', path);
}

function post<T>(path: string, body: unknown): Promise<T> {
    return request('POST', path, body);
}

// ─── Types ───────────────────────────────────────────────────

export interface Track {
    id: number;
    title: string;
    artist: string;
    bpm: number | null;
    key: string | null;
    camelot: string | null;
    energy: number | null;
    danceability: number | null;
    brightness: number | null;
    duration: number | null;
    energy_tag: string | null;
    label: string | null;
    era: string | null;
}

export interface Recommendation extends Track {
    score: number;
    meets_threshold: boolean;
    reasons: string[];
}

export interface SimilarResult {
    source: Track;
    similar: (Track & { score: number })[];
    method?: string;
}

export interface ArcType {
    key: string;
    label: string;
    bpm_start: number;
    bpm_peak: number;
    bpm_end: number;
    description: string;
}

export interface SessionTrack {
    position: number;
    target_bpm: number;
    track_id: number;
    title: string;
    artist: string;
    bpm: number;
    camelot: string | null;
    energy: number | null;
    score?: number;
    status?: string;
}

export interface Session {
    session_id: number;
    arc_type: string;
    arc_label: string;
    duration_min: number;
    bpm_start: number;
    bpm_peak: number;
    bpm_end: number;
    total_tracks: number;
    status: string;
    tracks: SessionTrack[];
}

export interface Mood {
    name: string;
    bpm_range: [number, number];
    description: string;
    compatible_subgenres: string[];
}

export interface TransitionResult {
    track_a: Track;
    track_b: Track;
    score: number;
    bpm_diff: number;
    camelot_distance: number;
    harmonic_score: number;
    reasons: string[];
}

export interface JourneyStep {
    id: number;
    title: string;
    artist: string;
    bpm: number;
    camelot: string | null;
    energy: number | null;
}

export interface JourneyResult {
    journey: JourneyStep[];
    start_bpm: number;
    end_bpm: number;
}

export interface BridgeResult {
    from_track: Track;
    bridge_tracks: Track[];
    target_subgenre?: string;
}

// ─── API ─────────────────────────────────────────────────────

export const somaApi = {
    getTracks: () => get<{ tracks: Track[]; count: number }>('/tracks'),

    getTrackRecommendations: (params: {
        bpm?: number; camelot?: string; energy?: number; mood?: string; limit?: number;
    }) => {
        const qs = new URLSearchParams();
        if (params.bpm) { qs.set('bpm', String(params.bpm)); }
        if (params.camelot) { qs.set('camelot', params.camelot); }
        if (params.energy) { qs.set('energy', String(params.energy)); }
        if (params.mood) { qs.set('mood', params.mood); }
        if (params.limit) { qs.set('limit', String(params.limit)); }
        return get<{ recommendations: Recommendation[]; count: number }>(
            `/recommend?${qs.toString()}`
        );
    },

    getSimilar: (trackId: number, limit = 5) =>
        get<SimilarResult>(`/similar/${trackId}?limit=${limit}`),

    getCompatibleKeys: (camelot: string) =>
        get<{ camelot: string; compatible_keys: string[] }>(`/compatible/${camelot}`),

    getMoods: () => get<{ moods: Mood[] }>('/moods'),

    getTracksByMood: (mood: string, limit = 10) =>
        get<{ mood: string; recommendations: Recommendation[]; count: number }>(
            `/mood/${mood}?limit=${limit}`
        ),

    scoreTransition: (trackA: number, trackB: number) =>
        get<TransitionResult>(`/transition?track_a=${trackA}&track_b=${trackB}`),

    getArcTypes: () => get<{ arc_types: ArcType[] }>('/sessions/arc-types'),

    createSession: (arcType: string, durationMin: number) =>
        post<Session>('/sessions', { arc_type: arcType, duration_min: durationMin }),

    getSession: (id: number) => get<Session>(`/sessions/${id}`),

    bpmJourney: (startBpm: number, endBpm: number, steps: number, subgenre?: string) => {
        const qs = new URLSearchParams({
            start_bpm: String(startBpm),
            end_bpm: String(endBpm),
            steps: String(steps),
        });
        if (subgenre) { qs.set('subgenre', subgenre); }
        return get<JourneyResult>(`/journey?${qs.toString()}`);
    },

    findBridge: (fromId: number, targetSubgenre?: string, targetBpm?: number) =>
        post<BridgeResult>('/bridge', {
            from_id: fromId,
            target_subgenre: targetSubgenre,
            target_bpm: targetBpm,
        }),

    digCrate: (params: {
        label?: string; era?: string; subgenre?: string;
        bpm_min?: number; bpm_max?: number; energy_tag?: string; limit?: number;
    }) => {
        const qs = new URLSearchParams();
        if (params.label) { qs.set('label', params.label); }
        if (params.era) { qs.set('era', params.era); }
        if (params.subgenre) { qs.set('subgenre', params.subgenre); }
        if (params.bpm_min) { qs.set('bpm_min', String(params.bpm_min)); }
        if (params.bpm_max) { qs.set('bpm_max', String(params.bpm_max)); }
        if (params.energy_tag) { qs.set('energy_tag', params.energy_tag); }
        if (params.limit) { qs.set('limit', String(params.limit)); }
        return get<{ tracks: Track[]; count: number }>(`/dig?${qs.toString()}`);
    },
};
