import type { ProcessingSettings } from "../types";

export const DEFAULT_SETTINGS: ProcessingSettings = {
  output_language: "auto",
  detail_level: "comprehensive",
  include_transcript: true,
  include_timestamps: true,
  per_video_documents: true,
  combined_document: true,
  max_videos: null,
};

export default function SettingsForm({
  value,
  onChange,
  showPlaylistOptions = true,
}: {
  value: ProcessingSettings;
  onChange: (s: ProcessingSettings) => void;
  showPlaylistOptions?: boolean;
}) {
  const set = <K extends keyof ProcessingSettings>(k: K, v: ProcessingSettings[K]) => onChange({ ...value, [k]: v });
  return (
    <div className="settings-grid">
      <label>
        <span>Document language</span>
        <select value={value.output_language} onChange={(e) => set("output_language", e.target.value as ProcessingSettings["output_language"])}>
          <option value="auto">Auto (same as video)</option>
          <option value="en">English</option>
          <option value="ar">Arabic (العربية)</option>
          <option value="bilingual">Bilingual (Arabic + English terms)</option>
        </select>
      </label>
      <label>
        <span>Document detail</span>
        <select value={value.detail_level} onChange={(e) => set("detail_level", e.target.value as ProcessingSettings["detail_level"])}>
          <option value="comprehensive">Comprehensive (everything)</option>
          <option value="standard">Standard (faster, fewer AI calls)</option>
        </select>
      </label>
      <label className="check">
        <input type="checkbox" checked={value.include_transcript} onChange={(e) => set("include_transcript", e.target.checked)} />
        <span>Include complete transcript</span>
      </label>
      <label className="check">
        <input type="checkbox" checked={value.include_timestamps} onChange={(e) => set("include_timestamps", e.target.checked)} />
        <span>Clickable timestamps</span>
      </label>
      {showPlaylistOptions && (
        <>
          <label className="check">
            <input type="checkbox" checked={value.per_video_documents} onChange={(e) => set("per_video_documents", e.target.checked)} />
            <span>Separate document per video</span>
          </label>
          <label className="check">
            <input type="checkbox" checked={value.combined_document} onChange={(e) => set("combined_document", e.target.checked)} />
            <span>Combined playlist book</span>
          </label>
          <label>
            <span>Max videos from playlist</span>
            <input
              type="number"
              min={1}
              placeholder="All"
              value={value.max_videos ?? ""}
              onChange={(e) => set("max_videos", e.target.value ? Number(e.target.value) : null)}
            />
          </label>
        </>
      )}
    </div>
  );
}
