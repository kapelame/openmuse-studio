"use client";

import { ChangeEvent, FormEvent, useEffect, useMemo, useState } from "react";

const API = process.env.NEXT_PUBLIC_API_BASE || "";

type AssetMetadata = {
  waveform?: number[];
  analysis?: {
    waveform?: number[];
    bpm?: number;
    key?: string;
    duration?: number;
    loudness?: { value?: number };
  };
  video_codec?: string;
  audio_codec?: string;
  pixel_format?: string;
  sample_rate?: number;
  channels?: number;
};

type Asset = {
  id: string;
  type: string;
  role: string;
  original_filename: string;
  duration?: number;
  width?: number;
  height?: number;
  metadata?: AssetMetadata;
  url: string;
};

type LyricCue = { start_ms: number; end_ms: number; text: string; style?: string };
type LyricsDocument = { id: string; canonical_text: string; structured_lyrics: LyricCue[]; title: string };
type Render = {
  id: string;
  status: string;
  template: string;
  aspect_ratio: string;
  resolution: string;
  fps: number;
  progress: number;
  output_asset_id?: string;
  error?: string;
  config?: Record<string, unknown>;
};
type ProjectJob = { id: string; kind: string; status: string; progress: number; error_message?: string };
type Project = {
  id: string;
  title: string;
  description?: string;
  creation_mode: string;
  status: string;
  assets: Asset[];
  lyrics?: LyricsDocument[];
  jobs?: ProjectJob[];
  renders?: Render[];
};
type RuntimeSettings = {
  default_music_provider: string;
  default_image_provider: string;
  minimax_api_base: string;
  minimax_music_model: string;
  minimax_cover_model: string;
  minimax_api_key_configured: boolean;
  custom_music_endpoint: string;
  custom_image_endpoint: string;
  enable_local_asr: boolean;
  enable_demucs: boolean;
  enable_basic_pitch: boolean;
  settings_file: string;
};
type ProviderInfo = { name: string; model: string; capabilities: Record<string, boolean> };
type SettingsResponse = {
  settings: RuntimeSettings;
  providers: { default: string; providers: { music: Record<string, ProviderInfo>; image: Record<string, ProviderInfo> } };
};
type AspectRatio = "1:1" | "16:9" | "9:16" | "4:5";

const capabilityRows: Array<[string, string]> = [
  ["text_to_music", "Text to song"],
  ["lyrics_to_music", "Lyrics to song"],
  ["reference_audio", "Reference audio"],
  ["continuation", "Continuation"],
  ["melody_conditioning", "Melody conditioning"],
  ["stems", "Stems"],
];

const entries = [
  ["01", "Describe a song", "Text to Song", "text"],
  ["02", "Record a melody", "Hum to Song", "hum"],
  ["03", "Upload a demo", "Demo to Song", "demo"],
  ["04", "Turn a song into an MV", "Song to MV", "mv"],
];

function formatTime(milliseconds: number) {
  return `${Math.floor(milliseconds / 60000)}:${String(Math.floor(milliseconds / 1000) % 60).padStart(2, "0")}`;
}

function statusLabel(value: string) {
  return value.replaceAll("_", " ");
}

export default function Home() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [selected, setSelected] = useState<Project | null>(null);
  const [modal, setModal] = useState<string | null>(null);
  const [toast, setToast] = useState("");
  const [loading, setLoading] = useState(true);
  const [command, setCommand] = useState("");
  const [job, setJob] = useState<{ id: string; kind?: string; status: string; progress: number } | null>(null);
  const [settings, setSettings] = useState<SettingsResponse | null>(null);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [renderTemplate, setRenderTemplate] = useState("editorial-lyrics");
  const [renderAspect, setRenderAspect] = useState<AspectRatio>("1:1");

  async function selectProject(projectId: string) {
    const response = await fetch(`${API}/api/projects/${projectId}`);
    if (!response.ok) throw new Error("Project unavailable");
    setSelected(await response.json());
  }

  async function loadProjects() {
    const response = await fetch(`${API}/api/projects`);
    if (!response.ok) throw new Error("Projects unavailable");
    const list: Project[] = await response.json();
    setProjects(list);
    if (selected) await selectProject(selected.id);
    else if (list[0]) await selectProject(list[0].id);
    setLoading(false);
  }

  async function loadSettings() {
    const response = await fetch(`${API}/api/settings`);
    if (!response.ok) throw new Error("Settings unavailable");
    setSettings(await response.json());
  }

  useEffect(() => {
    loadProjects().catch(() => { setToast("API unavailable. Start OpenMuse with ./start.sh."); setLoading(false); });
    loadSettings().catch(() => setToast("Provider settings are unavailable until the API is running."));
  }, []);

  useEffect(() => {
    if (!job || ["succeeded", "failed", "cancelled"].includes(job.status)) return;
    const timer = window.setInterval(async () => {
      const response = await fetch(`${API}/api/jobs/${job.id}`);
      if (!response.ok) return;
      const next = await response.json();
      setJob(next);
      if (["succeeded", "failed", "cancelled"].includes(next.status)) await loadProjects();
    }, 1000);
    return () => window.clearInterval(timer);
  }, [job]);

  async function createProject(title: string, description: string, mode: string) {
    const response = await fetch(`${API}/api/projects`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title, description, creation_mode: mode, rights_confirmed: true }),
    });
    if (!response.ok) { setToast(await response.text()); return; }
    const project: Project = await response.json();
    setProjects((previous) => [project, ...previous]);
    setSelected(project);
    setModal(null);
    setToast("Project created in the API.");
  }

  async function upload(file: File, role?: string) {
    if (!selected) return;
    const data = new FormData();
    data.append("file", file);
    if (role) data.append("role", role);
    const response = await fetch(`${API}/api/projects/${selected.id}/assets`, { method: "POST", body: data });
    if (!response.ok) { setToast(await response.text()); return; }
    await loadProjects();
    setToast(`${file.name} added to the project.`);
  }

  async function render() {
    if (!selected) { setToast("Create a project first."); return; }
    const response = await fetch(`${API}/api/projects/${selected.id}/render`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ template: renderTemplate, aspect_ratio: renderAspect, fps: 24, subtitle_alignment: "left" }),
    });
    const result = await response.json();
    if (!response.ok) { setToast(result.detail || "Render could not start."); return; }
    setJob(result.job);
    setToast(`${renderTemplate} ${renderAspect} render queued.`);
  }

  async function analyze() {
    if (!selected || !audio) { setToast("Upload audio before analysis."); return; }
    const response = await fetch(`${API}/api/projects/${selected.id}/assets/${audio.id}/analyze`, { method: "POST" });
    const result = await response.json();
    if (!response.ok) { setToast(result.detail || "Analysis could not start."); return; }
    setJob(result.job);
    setToast("Audio analysis queued. Results will be stored on the asset.");
  }

  async function cancelActiveJob() {
    if (!activeJob) return;
    const response = await fetch(`${API}/api/jobs/${activeJob.id}/cancel`, { method: "POST" });
    if (!response.ok) { setToast("The job could not be cancelled."); return; }
    setJob(await response.json());
    await loadProjects();
    setToast("Job cancelled.");
  }

  async function plan() {
    if (!selected || !command.trim()) return;
    const response = await fetch(`${API}/api/projects/${selected.id}/edit-plan`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ command }),
    });
    const result = await response.json();
    if (!response.ok) { setToast(result.detail || "The edit plan could not be created."); return; }
    setToast(`${result.intent}: ${result.jobs.join(" -> ")}`);
    setCommand("");
  }

  async function openSettings() {
    setSettingsOpen(true);
    try { await loadSettings(); } catch { setToast("Could not load provider settings."); }
  }

  function handleSettingsSaved(next: SettingsResponse) {
    setSettings(next);
    setSettingsOpen(false);
    setToast("Provider settings saved. New jobs use the updated configuration.");
  }

  function updateCues(next: LyricCue[]) {
    if (!selected || !selected.lyrics?.[0]) return;
    setSelected({ ...selected, lyrics: [{ ...selected.lyrics[0], structured_lyrics: next }, ...selected.lyrics.slice(1)] });
  }

  async function saveCues(next: LyricCue[]) {
    if (!selected || !selected.lyrics?.[0]) return;
    const response = await fetch(`${API}/api/projects/${selected.id}/lyrics/${selected.lyrics[0].id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ structured_lyrics: next }),
    });
    if (!response.ok) { setToast(await response.text()); return; }
    updateCues(next);
    setToast("Lyrics timing saved to the API.");
  }

  function nudgeCue(index: number, delta: number) {
    const next = cues.map((cue, cueIndex) => cueIndex === index
      ? { ...cue, start_ms: Math.max(0, cue.start_ms + delta), end_ms: Math.max(1, cue.end_ms + delta) }
      : cue);
    updateCues(next);
    void saveCues(next);
  }

  const audio = useMemo(() => selected?.assets?.find((asset) => asset.type === "audio"), [selected]);
  const cover = useMemo(() => selected?.assets?.find((asset) => asset.type === "image"), [selected]);
  const subtitle = useMemo(() => selected?.assets?.find((asset) => asset.type === "subtitle"), [selected]);
  const rendered = useMemo(() => selected?.assets?.find((asset) => asset.type === "video"), [selected]);
  const lyricDocument = selected?.lyrics?.[0];
  const cues = lyricDocument?.structured_lyrics || [];
  const latestRender = selected?.renders?.[0];
  const activeJob = job || selected?.jobs?.[0] || null;
  const activeMusicProvider = settings?.providers.providers.music[settings.settings.default_music_provider];
  const musicCapabilities = activeMusicProvider?.capabilities || {};
  const analysis = audio?.metadata?.analysis;
  const waveform = analysis?.waveform || audio?.metadata?.waveform || [];
  const pipeline = [
    { label: "Ingest", state: selected?.assets?.length ? "done" : "ready" },
    { label: "Analyze", state: analysis ? "done" : activeJob?.kind === "analyze_audio" ? activeJob.status : "ready" },
    { label: "Align", state: cues.length ? "done" : "ready" },
    { label: "Subtitle", state: subtitle || cues.length ? "done" : "ready" },
    { label: "Render", state: rendered ? "done" : latestRender?.status || (activeJob?.kind === "render_video" ? activeJob.status : "ready") },
    { label: "Validate", state: rendered?.metadata?.video_codec && rendered?.metadata?.audio_codec ? "done" : "ready" },
  ];

  return (
    <div className="shell">
      <aside className="icon-rail" aria-label="Primary navigation">
        <div className="icon-rail-brand"><span className="mark" /></div>
        <nav className="icon-nav">
          <button className="icon-button active" aria-label="Workspace" title="Workspace"><span>⌂</span></button>
          <button className="icon-button" aria-label="Projects" title="Projects"><span>▦</span></button>
          <button className="icon-button" aria-label="Jobs" title="Jobs"><span>◌</span>{activeJob && <i />}</button>
          <button className="icon-button" aria-label="Templates" title="Templates"><span>✦</span></button>
        </nav>
        <div className="icon-nav icon-nav-bottom">
          <button className="icon-button" aria-label="Providers" title="Providers" onClick={openSettings}><span>⚙</span></button>
          <button className="avatar-button" aria-label="OpenMuse local workspace" title="OpenMuse local workspace">O</button>
        </div>
      </aside>

      <aside className="rail navigator">
        <div className="navigator-header"><div className="wordmark"><span className="mark" /> <span>OpenMuse</span></div><button className="mini-button" aria-label="Collapse navigator" title="Collapse navigator">‹</button></div>
        <div className="navigator-title"><div><strong>Music workspace</strong><span>Local project library</span></div><button className="mini-button" onClick={() => setModal("new")} aria-label="Create project" title="Create project">+</button></div>
        <button className="new-project-row" onClick={() => setModal("new")}><span>+</span> New project</button>
        <div className="navigator-section"><div className="eyebrow">Projects from API</div><div className="project-list">{projects.map((project) => <button key={project.id} className={`project-item ${selected?.id === project.id ? "active" : ""}`} onClick={() => void selectProject(project.id)}><span className="project-dot" /><span className="project-name">{project.title}</span><small>{statusLabel(project.status)}</small></button>)}</div>{!projects.length && <div className="navigator-empty">Your projects will appear here.</div>}</div>
      </aside>

      <main className="main studio-main">
        <header className="topbar">
          <div className="title-stack">
            <span className="eyebrow">Studio / {selected ? selected.creation_mode : "new session"}</span>
            <h1>{selected?.title || "New music workspace"}</h1>
            <small>{selected ? `Saved in the local API · ${selected.status}` : "Start from an idea, demo, or finished song"}</small>
          </div>
          <div className="top-actions">
            <button className="button ghost" onClick={openSettings}>Settings</button>
            <span className={`status ${settings?.settings.default_music_provider === "minimax" && !settings.settings.minimax_api_key_configured ? "warn" : ""}`}>
              {activeMusicProvider ? `${activeMusicProvider.name} · ${activeMusicProvider.model}` : settings ? `${settings.settings.default_music_provider} provider` : "Provider loading"}
            </span>
            <button className="button primary" onClick={() => setModal("new")}>New project</button>
          </div>
        </header>

        {!selected && !loading && (
          <div className="welcome-stage">
            <section className="hero"><div className="eyebrow">OpenMuse Studio / API workspace</div><h2>What should we make today?</h2><p>Start with a description, a melody, a demo, or a finished song.</p></section>
            <section className="entry-grid">{entries.map(([number, title, sub, mode]) => <button className="entry" key={mode} onClick={() => setModal(mode)}><span>{number}</span><b>{title}</b><em>{sub}</em></button>)}</section>
          </div>
        )}

        {selected && (
          <>
            <section className="workspace">
              <div>
                <div className="panel">
                  <div className="panel-header"><strong>Current output</strong><span>{rendered ? "MV ready" : latestRender?.status || "Not rendered"}</span></div>
                  {rendered ? <video controls className="preview" src={`${API}${rendered.url}`} /> : <div className="preview">{cover ? <img className="preview-art preview-image" src={`${API}${cover.url}`} alt={selected.title} /> : <div className="preview-art" />}<div className="preview-copy"><small>{latestRender ? `${latestRender.template} · ${latestRender.resolution} · ${latestRender.fps}fps` : "No render yet"}</small><h3>{selected.title}</h3><p>{latestRender?.error || (latestRender ? `Render ${latestRender.status} at ${latestRender.progress}%` : "Upload source assets and start a render")}</p></div></div>}
                  {audio && <audio controls className="audio-player" src={`${API}${audio.url}`} />}
                  <div className="timeline">
                    <div className="wave">{waveform.length ? waveform.slice(0, 72).map((value, index) => <i key={index} style={{ height: `${12 + Math.round(Math.max(0, Math.min(1, value)) * 40)}px` }} />) : <span className="wave-empty">Analyze audio to build a waveform</span>}</div>
                    {cues.length ? cues.slice(0, 6).map((cue, index) => <div className={`cue ${index === 0 ? "current" : ""}`} key={`${cue.start_ms}-${index}`}><time>{formatTime(cue.start_ms)}</time><input aria-label={`Lyric cue ${index + 1}`} value={cue.text} onChange={(event) => updateCues(cues.map((item, cueIndex) => cueIndex === index ? { ...item, text: event.target.value } : item))} onBlur={() => void saveCues(cues)} style={{ flex: 1, minWidth: 0, border: 0, background: "transparent", color: "inherit", outline: 0 }} /><button className="button ghost" onClick={() => nudgeCue(index, -50)}>-50</button><button className="button ghost" onClick={() => nudgeCue(index, 50)}>+50</button></div>) : <div className="cue"><time>00:00</time><span>Upload SRT or LRC to populate the lyric timeline.</span></div>}
                  </div>
                  <div className="command"><input aria-label="Describe what you want to change" placeholder="Describe what you want to change..." value={command} onChange={(event) => setCommand(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter") void plan(); }} /><button className="button" onClick={() => void plan()}>Plan</button></div>
                </div>
              </div>

              <aside>
                <div className="panel">
                  <div className="panel-header"><strong>Assets from API</strong><span>{selected.assets?.length || 0}</span></div>
                  <div className="asset-list">{selected.assets?.map((asset) => <div className="asset" key={asset.id}><span>{asset.role.replaceAll("_", " ")}</span><span>{asset.original_filename.slice(0, 18)}</span></div>)}</div>
                  <div style={{ display: "grid", gap: 8, marginTop: 16 }}>
                    <label className="button upload">Add asset<input type="file" accept="audio/*,image/*,.srt,.lrc,.ass,.vtt" onChange={(event: ChangeEvent<HTMLInputElement>) => event.target.files?.[0] && void upload(event.target.files[0])} /></label>
                    <button className="button" onClick={() => void analyze()} disabled={!audio}>{activeJob?.kind === "analyze_audio" && ["queued", "running"].includes(activeJob.status) ? `Analyzing ${activeJob.progress}%` : "Analyze audio"}</button>
                    <div className="render-controls"><select aria-label="Video template" value={renderTemplate} onChange={(event) => setRenderTemplate(event.target.value)}><option value="editorial-lyrics">Editorial Lyrics</option><option value="album-cover">Album Cover</option><option value="kinetic-lyrics">Kinetic Lyrics</option></select><select aria-label="Video aspect ratio" value={renderAspect} onChange={(event) => setRenderAspect(event.target.value as AspectRatio)}><option value="1:1">1:1</option><option value="16:9">16:9</option><option value="9:16">9:16</option><option value="4:5">4:5</option></select></div>
                    <button className="button primary" onClick={() => void render()} disabled={!audio}>{activeJob?.kind === "render_video" && ["queued", "running"].includes(activeJob.status) ? `Rendering ${activeJob.progress}%` : "Render video"}</button>
                    {activeJob && ["queued", "running"].includes(activeJob.status) && <button className="button ghost" onClick={() => void cancelActiveJob()}>Cancel current job</button>}
                  </div>
                </div>
                <div className="panel" style={{ marginTop: 30 }}>
                  <div className="panel-header"><strong>Pipeline</strong><span>{activeJob ? statusLabel(activeJob.status) : "idle"}</span></div>
                  {pipeline.map((stage, index) => <div className="stat" key={stage.label}><span>{String(index + 1).padStart(2, "0")} / {stage.label}</span><b>{statusLabel(stage.state)}</b></div>)}
                </div>
              </aside>
            </section>

            <section style={{ maxWidth: 850, margin: "26px auto 0", display: "flex", gap: 8, flexWrap: "wrap" }}>
              <label className="button upload">Upload song<input type="file" accept="audio/*" onChange={(event: ChangeEvent<HTMLInputElement>) => event.target.files?.[0] && void upload(event.target.files[0], "source_audio")} /></label>
              <label className="button upload">Upload cover<input type="file" accept="image/*" onChange={(event: ChangeEvent<HTMLInputElement>) => event.target.files?.[0] && void upload(event.target.files[0], "cover")} /></label>
              <label className="button upload">Upload SRT / LRC<input type="file" accept=".srt,.lrc,.ass,.vtt,.txt" onChange={(event: ChangeEvent<HTMLInputElement>) => event.target.files?.[0] && void upload(event.target.files[0], "lyrics_timing")} /></label>
              {lyricDocument && <><a className="button" href={`${API}/api/projects/${selected.id}/lyrics/${lyricDocument.id}/export/srt`} download>Download SRT</a><a className="button" href={`${API}/api/projects/${selected.id}/lyrics/${lyricDocument.id}/export/ass`} download>Download ASS</a></>}
              {rendered && <a className="button primary" href={`${API}${rendered.url}`} download>Download MP4</a>}
              <a className="button" href={`${API}/api/projects/${selected.id}/manifest`} download={`openmuse-${selected.id}.json`}>Download project.json</a>
            </section>
          </>
        )}
      </main>

      <aside className="side context-pane">
        <div className="eyebrow" style={{ marginBottom: 22 }}>Live API state</div>
        <div className="side-section"><h4>Project</h4><div className="stat"><span>Mode</span><b>{selected?.creation_mode || "-"}</b></div><div className="stat"><span>Status</span><b>{selected ? statusLabel(selected.status) : "idle"}</b></div><div className="stat"><span>Provider</span><b>{activeMusicProvider ? `${activeMusicProvider.name} / ${activeMusicProvider.model}` : "loading"}</b></div><div className="stat"><span>Audio</span><b>{audio ? `${Math.round(audio.duration || 0)} sec` : "missing"}</b></div></div>
        <div className="side-section"><h4>Analysis</h4><div className="stat"><span>BPM</span><b>{analysis?.bpm ?? "-"}</b></div><div className="stat"><span>Key</span><b>{analysis?.key ?? "-"}</b></div><div className="stat"><span>Waveform</span><b>{waveform.length ? `${waveform.length} points` : "not analyzed"}</b></div></div>
        <div className="side-section"><h4>Provider capabilities</h4>{capabilityRows.map(([key, label]) => <div className="stat" key={key}><span>{label}</span><b>{musicCapabilities[key] ? "ready" : "gated"}</b></div>)}</div>
        <div className="side-section"><h4>Latest export</h4><div className="stat"><span>Aspect</span><b>{latestRender?.aspect_ratio || "-"}</b></div><div className="stat"><span>Resolution</span><b>{latestRender?.resolution || "-"}</b></div><div className="stat"><span>Codec</span><b>{rendered?.metadata?.video_codec ? `${rendered.metadata.video_codec} / ${rendered.metadata.audio_codec || "-"}` : "-"}</b></div><div className="stat"><span>Subtitle</span><b>{subtitle ? subtitle.original_filename.split(".").pop()?.toUpperCase() : "pending"}</b></div></div>
      </aside>

      {modal && <NewProjectModal mode={modal} onClose={() => setModal(null)} onCreate={createProject} />}
      {settingsOpen && settings && <ProviderSettingsModal initial={settings} onClose={() => setSettingsOpen(false)} onSaved={handleSettingsSaved} />}
      {toast && <button className="toast" onClick={() => setToast("")}>{toast}</button>}
    </div>
  );
}

function NewProjectModal({ mode, onClose, onCreate }: { mode: string; onClose: () => void; onCreate: (title: string, description: string, mode: string) => void }) {
  const [title, setTitle] = useState(mode === "mv" ? "Untitled lyric film" : "Untitled song");
  const [description, setDescription] = useState("");
  const [consent, setConsent] = useState(false);
  return <div className="modal-backdrop" role="presentation" onMouseDown={(event) => { if (event.currentTarget === event.target) onClose(); }}><form className="modal" onSubmit={(event) => { event.preventDefault(); if (consent) onCreate(title, description, mode === "new" ? "mv" : mode); }}><div className="eyebrow">Create / {mode === "new" ? "workspace" : mode}</div><h3>Start with an idea.</h3><p>This creates a versioned project in the API. Upload source audio, cover and timing files after creation.</p><input autoFocus value={title} onChange={(event) => setTitle(event.target.value)} placeholder="Project title" /><textarea value={description} onChange={(event) => setDescription(event.target.value)} placeholder="Describe the song, scene or change..." /><label style={{ display: "flex", gap: 9, alignItems: "flex-start", color: "#6f6a62", fontSize: 11, lineHeight: 1.4, marginBottom: 16 }}><input type="checkbox" checked={consent} onChange={(event) => setConsent(event.target.checked)} style={{ width: 15, margin: "1px 0 0" }} />I confirm that I own this material or have permission to use it.</label><div className="modal-actions"><button type="button" className="button" onClick={onClose}>Cancel</button><button type="submit" className="button primary" disabled={!consent}>Create project</button></div></form></div>;
}

function ProviderSettingsModal({ initial, onClose, onSaved }: { initial: SettingsResponse; onClose: () => void; onSaved: (next: SettingsResponse) => void }) {
  const [draft, setDraft] = useState({ ...initial.settings, minimax_api_key: "", clear_minimax_api_key: false });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  function update<K extends keyof typeof draft>(key: K, value: (typeof draft)[K]) {
    setDraft((current) => ({ ...current, [key]: value }));
  }

  async function save(event: FormEvent) {
    event.preventDefault();
    setSaving(true);
    setError("");
    const payload: Record<string, unknown> = { ...draft };
    delete payload.minimax_api_key_configured;
    delete payload.settings_file;
    if (!draft.minimax_api_key) delete payload.minimax_api_key;
    try {
      const response = await fetch(`${API}/api/settings`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail || "Could not save settings");
      onSaved(result);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not save settings");
    } finally {
      setSaving(false);
    }
  }

  return <div className="modal-backdrop" role="presentation" onMouseDown={(event) => { if (event.currentTarget === event.target) onClose(); }}><form className="modal settings-modal" onSubmit={save}><div className="eyebrow">Settings / Providers</div><h3>Change the engine anytime.</h3><p>These settings are stored locally in a permissions-restricted runtime file. API keys are write-only here and never returned to the browser.</p><div className="settings-grid"><label>Music Provider<select value={draft.default_music_provider} onChange={(event) => update("default_music_provider", event.target.value)}><option value="mock">Mock Provider</option><option value="minimax">MiniMax</option><option value="custom-http">Custom HTTP</option></select></label><label>Image Provider<select value={draft.default_image_provider} onChange={(event) => update("default_image_provider", event.target.value)}><option value="mock">Mock Image</option><option value="custom-http">Custom HTTP</option></select></label><label className="settings-wide">MiniMax API Key<input type="password" value={draft.minimax_api_key} onChange={(event) => { update("minimax_api_key", event.target.value); update("clear_minimax_api_key", false); }} placeholder={initial.settings.minimax_api_key_configured ? "Configured · leave blank to keep" : "Paste key (hidden)"} autoComplete="new-password" /></label><div className="settings-wide settings-inline"><span className={`key-state ${initial.settings.minimax_api_key_configured ? "ready" : ""}`}>{initial.settings.minimax_api_key_configured ? "MiniMax key configured" : "No MiniMax key configured"}</span><button type="button" className="button ghost" onClick={() => update("clear_minimax_api_key", true)}>Clear stored key</button></div><label>MiniMax API Base<input value={draft.minimax_api_base} onChange={(event) => update("minimax_api_base", event.target.value)} /></label><label>Music Model<input value={draft.minimax_music_model} onChange={(event) => update("minimax_music_model", event.target.value)} /></label><label>Cover Model<input value={draft.minimax_cover_model} onChange={(event) => update("minimax_cover_model", event.target.value)} /></label><label>Custom Music Endpoint<input value={draft.custom_music_endpoint} onChange={(event) => update("custom_music_endpoint", event.target.value)} placeholder="https://..." /></label><label>Custom Image Endpoint<input value={draft.custom_image_endpoint} onChange={(event) => update("custom_image_endpoint", event.target.value)} placeholder="https://..." /></label></div><div className="settings-capabilities"><strong>Optional local capabilities</strong><label><input type="checkbox" checked={draft.enable_local_asr} onChange={(event) => update("enable_local_asr", event.target.checked)} /> Local ASR / faster-whisper</label><label><input type="checkbox" checked={draft.enable_demucs} onChange={(event) => update("enable_demucs", event.target.checked)} /> Demucs stem separation</label><label><input type="checkbox" checked={draft.enable_basic_pitch} onChange={(event) => update("enable_basic_pitch", event.target.checked)} /> Basic Pitch MIDI</label></div>{error && <div className="settings-error">{error}</div>}<div className="modal-actions"><button type="button" className="button" onClick={onClose}>Cancel</button><button type="submit" className="button primary" disabled={saving}>{saving ? "Saving..." : "Save settings"}</button></div></form></div>;
}
