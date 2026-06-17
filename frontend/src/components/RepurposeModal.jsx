import { useState, useEffect } from "react";
import { useTranslation } from 'react-i18next';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { toast } from "sonner";

const platforms = [
  { id: "reels", label: "Instagram Reels", icon: "📸" },
  { id: "tiktok", label: "TikTok", icon: "🎵" },
  { id: "shorts", label: "YouTube Shorts", icon: "▶️" },
];

const durations = [
  { id: "15", label: "15s" },
  { id: "30", label: "30s" },
  { id: "60", label: "60s" },
];

const pillStyle = (active) => ({
  padding: "8px 16px",
  borderRadius: "20px",
  border: active ? "none" : "1px solid var(--m-border-light)",
  background: active ? "linear-gradient(135deg, #8b5cf6, #a855f7)" : "transparent",
  color: active ? "#fff" : "var(--m-text-soft)",
  cursor: "pointer",
  fontSize: "13px",
  fontWeight: active ? 600 : 400,
  fontFamily: "inherit",
  transition: "all 0.2s ease",
  display: "inline-flex",
  alignItems: "center",
  gap: "6px",
});

export default function RepurposeModal({ open, onClose, content, mode, api, API }) {
  const { t } = useTranslation();
  const [platform, setPlatform] = useState("reels");
  const [duration, setDuration] = useState("30");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [step, setStep] = useState("config"); // config | loading | result

  useEffect(() => {
    if (open) {
      setResult(null);
      setLoading(false);
      setStep("config");
      setPlatform("reels");
      setDuration("30");
    }
  }, [open, mode]);

  const generateVideo = async () => {
    setStep("loading");
    setLoading(true);
    try {
      const res = await api.post(`${API}/repurpose/video-script`, { content, duration, platform });
      if (res.data.success) {
        setResult({ type: "video", data: res.data });
        setStep("result");
      } else {
        toast.error(res.data.error || "Hata oluştu");
        setStep("config");
      }
    } catch {
      toast.error(t('repurpose.videoScriptError'));
      setStep("config");
    } finally {
      setLoading(false);
    }
  };

  const generateImage = async () => {
    setLoading(true);
    try {
      const res = await api.post(`${API}/repurpose/image-prompt`, { content, platform: "twitter" });
      if (res.data.success) {
        setResult({ type: "image", data: res.data });
        setStep("result");
      } else {
        toast.error(res.data.error || "Hata oluştu");
        onClose();
      }
    } catch {
      toast.error(t('repurpose.imagePromptError'));
      onClose();
    } finally {
      setLoading(false);
    }
  };

  const handleRegenerate = () => {
    setResult(null);
    if (mode === "video") {
      setStep("config");
    } else {
      setStep("loading");
      generateImage();
    }
  };

  const copyVideoScript = () => {
    const d = result.data;
    const scriptText = d.script.map(s => `[${s.time}] ${s.spoken_text}\n📝 ${s.text_overlay}\n🎬 ${s.visual_note}`).join("\n\n");
    const pl = platforms.find(p => p.id === platform)?.label || platform;
    const fullText = `🎬 Video Script (${duration}s ${pl})\n\n${scriptText}\n\n🎵 Müzik: ${d.music_mood}\n${d.caption ? `💬 ${d.caption}\n` : ""}#️⃣ ${d.hashtags?.join(" ") || ""}`;
    navigator.clipboard.writeText(fullText);
    toast.success(t('repurpose.scriptCopied'));
  };

  const copyImagePrompt = () => {
    navigator.clipboard.writeText(JSON.stringify(result.data.prompt_json, null, 2));
    toast.success(t('repurpose.promptCopied'));
  };

  const sectionStyle = {
    marginBottom: "16px",
  };

  const labelStyle = {
    fontSize: "12px",
    color: "var(--m-text-muted)",
    marginBottom: "8px",
    display: "block",
    fontWeight: 500,
  };

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent style={{ maxWidth: "480px", background: "var(--m-surface)", border: "1px solid var(--m-border-light)", color: "var(--m-text)" }}>
        <DialogHeader>
          <DialogTitle style={{ color: "var(--m-text)", fontSize: "16px" }}>
            {mode === "video" ? t('repurpose.videoScriptTitle') : t('repurpose.imagePromptTitle')}
          </DialogTitle>
        </DialogHeader>

        {/* Video Config Step */}
        {mode === "video" && step === "config" && (
          <div style={{ animation: "fadeIn 0.2s ease" }}>
            <div style={sectionStyle}>
              <span style={labelStyle}>{t('repurpose.platform')}</span>
              <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
                {platforms.map(p => (
                  <button key={p.id} style={pillStyle(platform === p.id)} onClick={() => setPlatform(p.id)}>
                    {p.icon} {p.label}
                  </button>
                ))}
              </div>
            </div>
            <div style={sectionStyle}>
              <span style={labelStyle}>{t('repurpose.duration')}</span>
              <div style={{ display: "flex", gap: "8px" }}>
                {durations.map(d => (
                  <button key={d.id} style={pillStyle(duration === d.id)} onClick={() => setDuration(d.id)}>
                    {d.label}
                  </button>
                ))}
              </div>
            </div>
            <button
              onClick={generateVideo}
              style={{
                width: "100%",
                padding: "12px",
                borderRadius: "10px",
                border: "none",
                background: "linear-gradient(135deg, #8b5cf6, #a855f7)",
                color: "#fff",
                fontSize: "14px",
                fontWeight: 600,
                cursor: "pointer",
                fontFamily: "inherit",
                marginTop: "8px",
              }}
            >
              {t('repurpose.createVideoScript')}
            </button>
          </div>
        )}

        {/* Image Config Step */}
        {mode === "image" && step === "config" && (
          <div style={{ animation: "fadeIn 0.2s ease", textAlign: "center", padding: "20px 0" }}>
            <div style={{ fontSize: "48px", marginBottom: "16px" }}>🎨</div>
            <p style={{ color: "var(--m-text-soft)", fontSize: "14px", marginBottom: "8px", lineHeight: "1.5" }}>
              {t('repurpose.imagePromptDesc')}
            </p>
            <p style={{ color: "var(--m-text-muted)", fontSize: "12px", marginBottom: "24px", lineHeight: "1.5", maxWidth: "320px", margin: "0 auto 24px" }}>
              {t('repurpose.imagePromptUsage')}
            </p>
            <button
              onClick={() => { setStep("loading"); generateImage(); }}
              style={{
                width: "100%",
                padding: "12px",
                borderRadius: "10px",
                border: "none",
                background: "linear-gradient(135deg, #8b5cf6, #a855f7)",
                color: "#fff",
                fontSize: "14px",
                fontWeight: 600,
                cursor: "pointer",
                fontFamily: "inherit",
              }}
            >
              {t('repurpose.createImagePrompt')}
            </button>
          </div>
        )}

        {/* Loading */}
        {step === "loading" && (
          <div style={{ padding: "40px 0", textAlign: "center", animation: "fadeIn 0.2s ease" }}>
            <div style={{ fontSize: "32px", marginBottom: "12px", animation: "spin 1s linear infinite" }}>⏳</div>
            <p style={{ color: "var(--m-text-soft)", fontSize: "14px" }}>
              {mode === "video" ? t('repurpose.preparingVideoScript') : t('repurpose.preparingImagePrompt')}
            </p>
          </div>
        )}

        {/* Video Result */}
        {step === "result" && result?.type === "video" && (
          <div style={{ animation: "fadeIn 0.3s ease", maxHeight: "60vh", overflowY: "auto" }}>
            <div style={{ display: "flex", flexDirection: "column", gap: "8px", marginBottom: "16px" }}>
              {result.data.script?.map((seg, i) => (
                <div key={i} style={{ background: "var(--m-card-bg, rgba(255,255,255,0.03))", border: "1px solid var(--m-border-light)", borderRadius: "10px", padding: "12px" }}>
                  <div style={{ fontSize: "11px", color: "var(--m-text-muted)", marginBottom: "6px", fontWeight: 600 }}>{seg.time}</div>
                  <div style={{ fontSize: "13px", color: "var(--m-text)", marginBottom: "4px" }}>🎤 "{seg.spoken_text}"</div>
                  <div style={{ fontSize: "12px", color: "var(--m-text-soft)", marginBottom: "2px" }}>📝 {seg.text_overlay}</div>
                  <div style={{ fontSize: "12px", color: "var(--m-text-muted)" }}>🎬 {seg.visual_note}</div>
                </div>
              ))}
            </div>
            {(result.data.music_mood || result.data.hashtags || result.data.caption) && (
              <div style={{ background: "var(--m-card-bg, rgba(255,255,255,0.03))", border: "1px solid var(--m-border-light)", borderRadius: "10px", padding: "12px", marginBottom: "16px", fontSize: "12px", color: "var(--m-text-soft)" }}>
                {result.data.music_mood && <div>🎵 Müzik: {result.data.music_mood}</div>}
                {result.data.caption && <div style={{ marginTop: "4px" }}>💬 {result.data.caption}</div>}
                {result.data.hashtags?.length > 0 && <div style={{ marginTop: "4px" }}>#{result.data.hashtags.join(" #")}</div>}
              </div>
            )}
            <div style={{ display: "flex", gap: "8px" }}>
              <button onClick={copyVideoScript} style={{ flex: 1, padding: "10px", borderRadius: "8px", border: "none", background: "linear-gradient(135deg, #8b5cf6, #a855f7)", color: "#fff", fontSize: "13px", fontWeight: 600, cursor: "pointer", fontFamily: "inherit" }}>
                {t('repurpose.copy')}
              </button>
              <button onClick={handleRegenerate} style={{ flex: 1, padding: "10px", borderRadius: "8px", border: "1px solid var(--m-border-light)", background: "transparent", color: "var(--m-text-soft)", fontSize: "13px", cursor: "pointer", fontFamily: "inherit" }}>
                {t('repurpose.regenerate')}
              </button>
            </div>
          </div>
        )}

        {/* Image Result */}
        {step === "result" && result?.type === "image" && (
          <div style={{ animation: "fadeIn 0.3s ease" }}>
            <div style={{ background: "var(--m-card-bg, rgba(255,255,255,0.03))", border: "1px solid var(--m-border-light)", borderRadius: "10px", padding: "16px", marginBottom: "16px" }}>
              {result.data.prompt_json && Object.entries(result.data.prompt_json).map(([key, value]) => (
                <div key={key} style={{ marginBottom: "10px" }}>
                  <div style={{ fontSize: "11px", color: "var(--m-text-muted)", fontWeight: 600, marginBottom: "2px", textTransform: "capitalize" }}>
                    {key.replace(/_/g, " ")}
                  </div>
                  <div style={{ fontSize: "13px", color: "var(--m-text)" }}>
                    {typeof value === "object" ? JSON.stringify(value, null, 2) : String(value)}
                  </div>
                </div>
              ))}
            </div>
            <div style={{ display: "flex", gap: "8px" }}>
              <button onClick={copyImagePrompt} style={{ flex: 1, padding: "10px", borderRadius: "8px", border: "none", background: "linear-gradient(135deg, #8b5cf6, #a855f7)", color: "#fff", fontSize: "13px", fontWeight: 600, cursor: "pointer", fontFamily: "inherit" }}>
                {t('repurpose.copyPrompt')}
              </button>
              <button onClick={handleRegenerate} style={{ flex: 1, padding: "10px", borderRadius: "8px", border: "1px solid var(--m-border-light)", background: "transparent", color: "var(--m-text-soft)", fontSize: "13px", cursor: "pointer", fontFamily: "inherit" }}>
                {t('repurpose.regenerate')}
              </button>
            </div>
          </div>
        )}

        <style>{`
          @keyframes fadeIn { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }
          @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
        `}</style>
      </DialogContent>
    </Dialog>
  );
}
