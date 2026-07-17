"use client";

import { ChangeEvent, useEffect, useMemo, useState } from "react";

// Keep browser requests same-origin so localhost, Docker and Codespaces all work.
const API = process.env.NEXT_PUBLIC_API_BASE || "";

type Asset = { id: string; type: string; role: string; original_filename: string; duration?: number; url: string };
type LyricCue = { start_ms: number; end_ms: number; text: string; style?: string };
type LyricsDocument = { id: string; canonical_text: string; structured_lyrics: LyricCue[]; title: string };
type Project = { id: string; title: string; description?: string; creation_mode: string; status: string; assets: Asset[]; lyrics?: LyricsDocument[]; renders?: Array<{ status: string; output_asset_id?: string }> };

const entries = [
  ["01", "Describe a song", "Text to Song", "text"],
  ["02", "Record a melody", "Hum to Song", "hum"],
  ["03", "Upload a demo", "Demo to Song", "demo"],
  ["04", "Turn a song into an MV", "Song to MV", "mv"],
];

export default function Home() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [selected, setSelected] = useState<Project | null>(null);
  const [modal, setModal] = useState<string | null>(null);
  const [toast, setToast] = useState("");
  const [loading, setLoading] = useState(true);
  const [command, setCommand] = useState("");
  const [job, setJob] = useState<{ id: string; kind?: string; status: string; progress: number } | null>(null);

  async function loadProjects() {
    const response = await fetch(`${API}/api/projects`);
    const list = await response.json();
    setProjects(list);
    if (selected) {
      const current = await fetch(`${API}/api/projects/${selected.id}`);
      setSelected(await current.json());
    } else if (list[0]) {
      const current = await fetch(`${API}/api/projects/${list[0].id}`);
      setSelected(await current.json());
    }
    setLoading(false);
  }

  useEffect(() => { loadProjects().catch(() => { setToast("API unavailable. Start the FastAPI service on port 8000."); setLoading(false); }); }, []);

  useEffect(() => {
    if (!job || job.status === "succeeded" || job.status === "failed" || job.status === "cancelled") return;
    const timer = window.setInterval(async () => {
      const response = await fetch(`${API}/api/jobs/${job.id}`);
      const next = await response.json();
      setJob(next);
      if (["succeeded", "failed", "cancelled"].includes(next.status)) { await loadProjects(); }
    }, 1000);
    return () => window.clearInterval(timer);
  }, [job]);

  async function createProject(title: string, description: string, mode: string) {
    const response = await fetch(`${API}/api/projects`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ title, description, creation_mode: mode, rights_confirmed: true }) });
    if (!response.ok) { setToast(await response.text()); return; }
    const project = await response.json();
    setProjects((previous) => [project, ...previous]); setSelected(project); setModal(null); setToast("Project created.");
  }

  async function upload(file: File, role?: string) {
    if (!selected) return;
    const data = new FormData(); data.append("file", file); if (role) data.append("role", role);
    const response = await fetch(`${API}/api/projects/${selected.id}/assets`, { method: "POST", body: data });
    if (!response.ok) { setToast(await response.text()); return; }
    await loadProjects(); setToast(`${file.name} added.`);
  }

  async function render() {
    if (!selected) { setToast("Create a project first."); return; }
    const response = await fetch(`${API}/api/projects/${selected.id}/render`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ template: "editorial-lyrics", aspect_ratio: "1:1", fps: 24, subtitle_alignment: "left" }) });
    const result = await response.json();
    if (!response.ok) { setToast(result.detail || "Render could not start."); return; }
    setJob(result.job); setToast("Render queued. The frame stays stable by design.");
  }

  async function plan() {
    if (!selected || !command.trim()) return;
    const response = await fetch(`${API}/api/projects/${selected.id}/edit-plan`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ command }) });
    const result = await response.json(); setToast(`${result.intent}: ${result.jobs.join(" → ")}`); setCommand("");
  }

  async function analyze() {
    if (!selected || !audio) { setToast("Upload audio before analysis."); return; }
    const response = await fetch(`${API}/api/projects/${selected.id}/assets/${audio.id}/analyze`, { method: "POST" });
    const result = await response.json();
    if (!response.ok) { setToast(result.detail || "Analysis could not start."); return; }
    setJob(result.job); setToast("Audio analysis queued. Estimates keep their confidence labels.");
  }

  function updateCues(next: LyricCue[]) {
    if (!selected || !selected.lyrics?.[0]) return;
    setSelected({ ...selected, lyrics: [{ ...selected.lyrics[0], structured_lyrics: next }, ...selected.lyrics.slice(1)] });
  }

  async function saveCues(next: LyricCue[]) {
    if (!selected || !selected.lyrics?.[0]) return;
    const response = await fetch(`${API}/api/projects/${selected.id}/lyrics/${selected.lyrics[0].id}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ structured_lyrics: next }) });
    if (!response.ok) { setToast(await response.text()); return; }
    updateCues(next); setToast("Lyrics timing saved.");
  }

  function nudgeCue(index: number, delta: number) {
    const next = cues.map((cue, cueIndex) => cueIndex === index ? { ...cue, start_ms: Math.max(0, cue.start_ms + delta), end_ms: Math.max(1, cue.end_ms + delta) } : cue);
    updateCues(next); void saveCues(next);
  }

  const audio = useMemo(() => selected?.assets?.find((asset) => asset.type === "audio"), [selected]);
  const cover = useMemo(() => selected?.assets?.find((asset) => asset.type === "image"), [selected]);
  const subtitle = useMemo(() => selected?.assets?.find((asset) => asset.type === "subtitle"), [selected]);
  const rendered = useMemo(() => selected?.assets?.find((asset) => asset.type === "video"), [selected]);
  const lyricDocument = selected?.lyrics?.[0];
  const cues = lyricDocument?.structured_lyrics || [];

  return <div className="shell">
    <aside className="rail">
      <div className="wordmark"><span className="mark" /> <span>OpenMuse</span></div>
      <nav className="rail-nav"><button className="active">Workspace</button><button>Jobs <span className="eyebrow">{job ? "active" : ""}</span></button><button>Templates</button><button>Providers</button></nav>
      <div><div className="eyebrow" style={{ marginBottom: 10 }}>Projects</div><div className="project-list">{projects.map((project) => <button key={project.id} className={`project-item ${selected?.id === project.id ? "active" : ""}`} onClick={() => fetch(`${API}/api/projects/${project.id}`).then((r) => r.json()).then(setSelected)}><span className="project-dot" /><span className="project-name">{project.title}</span></button>)}</div></div>
      <div className="rail-footer"><span>Open-source music workspace</span><span>v0.1 · mock-ready</span></div>
    </aside>
    <main className="main">
      <header className="topbar"><div><h1>{selected?.title || "New music workspace"}</h1><small>{selected ? "Autosaved locally · portable by default" : "Start from an idea, demo, or finished song"}</small></div><div className="top-actions"><span className="status">Mock provider ready</span><button className="button primary" onClick={() => setModal("new")}>New project</button></div></header>
      {!selected && !loading && <><section className="hero"><div className="eyebrow">OpenMuse Studio / Music 3.0 interface</div><h2>Make the song, then make the world around it.</h2><p>Turn text, humming, demos and songs into a finished track, synchronized lyrics, cover art and a stable lyric video. Every output remains a version you can revisit.</p></section><section className="entry-grid">{entries.map(([number, title, sub, mode]) => <button className="entry" key={mode} onClick={() => setModal(mode)}><span>{number}</span><b>{title}</b><em>{sub}</em></button>)}</section><div className="empty" style={{ maxWidth: 850, margin: "0 auto" }}>The working demo uses a deterministic Mock Provider and local FFmpeg renderer. Upload an audio file, cover and SRT/LRC to complete the first vertical loop.</div></>}
      {selected && <><section className="workspace"><div><div className="panel"><div className="panel-header"><strong>Current output</strong><span>{rendered ? "MV ready" : "Not rendered"}</span></div>{rendered ? <video controls className="preview" src={`${API}${rendered.url}`} /> : <div className="preview"><div className="preview-art" /><div className="preview-copy"><small>Editorial Lyrics · 1:1 · 24fps</small><h3>{selected.title}</h3><p>Stable crop · restrained typography · no random motion</p></div></div>}<div className="timeline"><div className="wave">{Array.from({ length: 72 }).map((_, index) => <i key={index} style={{ height: `${12 + ((index * 17) % 40)}px` }} />)}</div>{cues.length ? cues.slice(0, 6).map((cue, index) => <div className={`cue ${index === 0 ? "current" : ""}`} key={`${cue.start_ms}-${index}`}><time>{`${Math.floor(cue.start_ms / 60000)}:${String(Math.floor(cue.start_ms / 1000) % 60).padStart(2, "0")}`}</time><input aria-label={`Lyric cue ${index + 1}`} value={cue.text} onChange={(event) => updateCues(cues.map((item, cueIndex) => cueIndex === index ? { ...item, text: event.target.value } : item))} onBlur={() => void saveCues(cues)} style={{ flex: 1, minWidth: 0, border: 0, background: "transparent", color: "inherit", outline: 0 }} /><button className="button ghost" onClick={() => nudgeCue(index, -50)}>-50</button><button className="button ghost" onClick={() => nudgeCue(index, 50)}>+50</button></div>) : <div className="cue"><time>00:00</time><span>Upload SRT or LRC to populate the lyric timeline.</span></div>}</div><div className="command"><input aria-label="Describe what you want to change" placeholder="Describe what you want to change…" value={command} onChange={(event) => setCommand(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter") plan(); }} /><button className="button" onClick={plan}>Plan</button></div></div></div><aside><div className="panel"><div className="panel-header"><strong>Assets</strong><span>{selected.assets?.length || 0}</span></div><div className="asset-list">{selected.assets?.map((asset) => <div className="asset" key={asset.id}><span>{asset.role.replaceAll("_", " ")}</span><span>{asset.original_filename.slice(0, 18)}</span></div>)}</div><div style={{ display: "grid", gap: 8, marginTop: 16 }}><label className="button upload">Add asset<input type="file" accept="audio/*,image/*,.srt,.lrc,.ass,.vtt" onChange={(event: ChangeEvent<HTMLInputElement>) => event.target.files?.[0] && upload(event.target.files[0])} /></label><button className="button" onClick={analyze}>{job?.kind === "analyze_audio" && job.status === "running" ? `Analyzing ${job.progress}%` : "Analyze audio"}</button><button className="button primary" onClick={render}>{job?.kind === "render_video" && job.status === "running" ? `Rendering ${job.progress}%` : "Render Editorial MV"}</button></div></div><div className="panel" style={{ marginTop: 30 }}><div className="panel-header"><strong>Pipeline</strong><span>async</span></div>{["Ingest", "Analyze", "Align", "Subtitle", "Render", "Validate"].map((stage, index) => <div className="stat" key={stage}><span>{String(index + 1).padStart(2, "0")} / {stage}</span><b>{index < (rendered ? 6 : selected.assets?.length ? 2 : 0) ? "done" : "ready"}</b></div>)}</div></aside></section><section style={{ maxWidth: 850, margin: "26px auto 0", display: "flex", gap: 8, flexWrap: "wrap" }}><label className="button upload">Upload song<input type="file" accept="audio/*" onChange={(event: ChangeEvent<HTMLInputElement>) => event.target.files?.[0] && upload(event.target.files[0], "source_audio")} /></label><label className="button upload">Upload cover<input type="file" accept="image/*" onChange={(event: ChangeEvent<HTMLInputElement>) => event.target.files?.[0] && upload(event.target.files[0], "cover")} /></label><label className="button upload">Upload SRT / LRC<input type="file" accept=".srt,.lrc,.ass,.vtt,.txt" onChange={(event: ChangeEvent<HTMLInputElement>) => event.target.files?.[0] && upload(event.target.files[0], "lyrics_timing")} /></label>{lyricDocument && <><a className="button" href={`${API}/api/projects/${selected.id}/lyrics/${lyricDocument.id}/export/srt`} download>Download SRT</a><a className="button" href={`${API}/api/projects/${selected.id}/lyrics/${lyricDocument.id}/export/ass`} download>Download ASS</a></>}{rendered && <a className="button primary" href={`${API}${rendered.url}`} download>Download MP4</a>}<a className="button" href={`${API}/api/projects/${selected.id}/manifest`} download={`openmuse-${selected.id}.json`}>Download project.json</a></section></>}
    </main>
    <aside className="side"><div className="eyebrow" style={{ marginBottom: 22 }}>Studio status</div><div className="side-section"><h4>Project</h4><div className="stat"><span>Mode</span><b>{selected?.creation_mode || "—"}</b></div><div className="stat"><span>Provider</span><b>Mock / tone-v1</b></div><div className="stat"><span>Audio</span><b>{audio ? `${Math.round(audio.duration || 0)} sec` : "missing"}</b></div></div><div className="side-section"><h4>Capabilities</h4>{["Text to song", "Lyrics to song", "Reference audio", "Continuation"].map((label, index) => <div className="stat" key={label}><span>{label}</span><b>{index === 3 ? "gated" : "ready"}</b></div>)}</div><div className="side-section"><h4>Export</h4><div className="stat"><span>Square</span><b>1080 × 1080</b></div><div className="stat"><span>Codec</span><b>H.264 / AAC</b></div><div className="stat"><span>Subtitle</span><b>{subtitle ? subtitle.original_filename.split(".").pop()?.toUpperCase() : "pending"}</b></div></div></aside>
    {modal && <NewProjectModal mode={modal} onClose={() => setModal(null)} onCreate={createProject} />}
    {toast && <button className="toast" onClick={() => setToast("")}>{toast}</button>}
  </div>;
}

function NewProjectModal({ mode, onClose, onCreate }: { mode: string; onClose: () => void; onCreate: (title: string, description: string, mode: string) => void }) {
  const [title, setTitle] = useState(mode === "mv" ? "Untitled lyric film" : "Untitled song");
  const [description, setDescription] = useState("");
  const [consent, setConsent] = useState(false);
  return <div className="modal-backdrop" role="presentation" onMouseDown={(event) => { if (event.currentTarget === event.target) onClose(); }}><form className="modal" onSubmit={(event) => { event.preventDefault(); if (consent) onCreate(title, description, mode === "new" ? "mv" : mode); }}><div className="eyebrow">Create / {mode === "new" ? "workspace" : mode}</div><h3>Start with an idea.</h3><p>This creates a versioned project. Upload your source audio, cover and timing file after creation; nothing is overwritten.</p><input autoFocus value={title} onChange={(event) => setTitle(event.target.value)} placeholder="Project title" /><textarea value={description} onChange={(event) => setDescription(event.target.value)} placeholder="Describe the song, scene or change…" /><label style={{ display: "flex", gap: 9, alignItems: "flex-start", color: "#6f6a62", fontSize: 11, lineHeight: 1.4, marginBottom: 16 }}><input type="checkbox" checked={consent} onChange={(event) => setConsent(event.target.checked)} style={{ width: 15, margin: "1px 0 0" }} />I confirm that I own this material or have permission to use it.</label><div className="modal-actions"><button type="button" className="button" onClick={onClose}>Cancel</button><button type="submit" className="button primary" disabled={!consent}>Create project</button></div></form></div>;
}
