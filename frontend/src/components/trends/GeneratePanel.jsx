import { useState, useEffect, useCallback } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import {
  ExternalLink, Zap, Copy, Heart, RotateCcw, Loader2, Wand2,
} from "lucide-react";
import StyleChip from "@/components/StyleChip";
import { useStylePalette } from "@/contexts/StylePaletteContext";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import api, { API } from "@/lib/api";
import { PILLAR_CONFIG, TIER_COLORS, PLATFORMS, formatEngagement } from "@/lib/trend-helpers";

export default function GeneratePanel({ open, onOpenChange, trend }) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [platform, setPlatform] = useState("twitter");
  const [additionalContext, setAdditionalContext] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [isFavorited, setIsFavorited] = useState(false);
  const [drafts, setDrafts] = useState([]);
  const [draftsLoading, setDraftsLoading] = useState(false);

  const { palette } = useStylePalette();
  const [styleOverrideOpen, setStyleOverrideOpen] = useState(false);
  const [lastUsedStyle, setLastUsedStyle] = useState(null);

  const normalizeStyleObj = useCallback((styleObj) => {
    if (!styleObj || typeof styleObj !== "object") return null;
    if (styleObj.type === "own_voice") return { type: "own_voice" };
    if (styleObj.type === "cloned") {
      const profileId = styleObj.profile_id || styleObj.style_profile_id || styleObj.active_profile_id || styleObj.id;
      if (!profileId) return null;
      return { type: "cloned", profile_id: profileId };
    }
    if (styleObj.type === "archetype") {
      const key = styleObj.key || styleObj.archetype_key;
      if (!key) return null;
      return { type: "archetype", key };
    }
    return null;
  }, []);

  const extractBackendStyle = useCallback((data) => {
    const candidates = [
      data?.style_used, data?.used_style, data?.style,
      data?.style_override, data?.metadata?.style_used,
      data?.meta?.style_used, data?.generation?.style_used,
      data?.generation_metadata?.style_used,
    ];
    for (const candidate of candidates) {
      const normalized = normalizeStyleObj(candidate);
      if (normalized) return normalized;
    }
    return null;
  }, [normalizeStyleObj]);

  const canRegenerateWithStyle = Boolean(palette && (result?.generation_id || result?.draft_id || result?.id));

  const PLATFORM_ROUTES = {
    twitter: "/dashboard/create?platform=twitter",
    blog: "/dashboard/create?platform=blog",
    linkedin: "/dashboard/create?platform=linkedin",
    instagram: "/dashboard/create?platform=instagram",
    youtube: "/dashboard/create?platform=youtube",
    tiktok: "/dashboard/create?platform=tiktok",
  };

  const handleGoToModule = () => {
    if (!trend) return;
    const route = PLATFORM_ROUTES[platform] || PLATFORM_ROUTES.twitter;
    const parts = [trend.topic];
    if (trend.content_angle) parts.push(trend.content_angle);
    if (trend.summary) parts.push(trend.summary);
    if (trend.key_angles?.length) {
      const angles = trend.key_angles.slice(0, 2).map(a => a.replace(/^A\u00e7\u0131 \d+:\s*/, '')).join("; ");
      parts.push(`A\u00e7\u0131lar: ${angles}`);
    }
    if (additionalContext) parts.push(additionalContext);
    else if (trend.keywords?.length) parts.push(trend.keywords.slice(0, 5).join(", "));
    let combined = parts.join(" | ");
    if (combined.length > 790) combined = combined.slice(0, 787) + "...";
    const topic = encodeURIComponent(combined);
    onOpenChange(false);
    navigate(`${route}&topic=${topic}`);
  };

  useEffect(() => {
    if (trend?.id && open) {
      setResult(null);
      setPlatform("twitter");
      setAdditionalContext("");
      setIsFavorited(false);
      setLastUsedStyle(null);
      setStyleOverrideOpen(false);
      setDrafts([]);
      setDraftsLoading(true);
      api.get(`${API}/trends/${trend.id}/drafts`).then(res => {
        setDrafts(res.data?.drafts || []);
      }).catch(() => {
        setDrafts([]);
      }).finally(() => {
        setDraftsLoading(false);
      });
    }
  }, [trend?.id, open]);

  const handleGenerate = async () => {
    if (!trend) return;
    setLoading(true);
    setResult(null);
    setLastUsedStyle(null);
    setStyleOverrideOpen(false);
    try {
      const res = await api.post(`${API}/trends/${trend.id}/generate`, {
        platform,
        additional_context: additionalContext || undefined,
        language: "tr",
      });
      const data = res.data;
      if (data.success === false) {
        toast.error(data.error || t('trends.generatePanel.generateError'));
      } else {
        setResult(data);
        setLastUsedStyle(extractBackendStyle(data));
      }
    } catch (err) {
      toast.error(err.response?.data?.detail || err.response?.data?.error || t('trends.generatePanel.generateError'));
    } finally {
      setLoading(false);
    }
  };

  const handleRegenerateWithStyle = async (styleObj) => {
    const draftId = result?.generation_id || result?.draft_id || result?.id;
    setStyleOverrideOpen(false);
    if (!draftId) {
      toast.error(t('trends.generatePanel.noDraftId'));
      return;
    }
    setLoading(true);
    try {
      const res = await api.post(`${API}/drafts/${draftId}/regenerate`, {
        style_override: styleObj,
      });
      const data = res.data;
      if (data.content || data.generated_content || data.variants?.[0]?.content) {
        setResult(prev => ({
          ...prev,
          ...data,
          variants: data.variants || [{ content: data.content || data.generated_content }],
        }));
        setLastUsedStyle(extractBackendStyle(data));
        toast.success(t('trends.generatePanel.regenerated'));
      } else if (data.error) {
        toast.error(data.error);
      }
    } catch (err) {
      toast.error(err.response?.data?.detail || t('trends.generatePanel.regenerateError'));
    } finally {
      setLoading(false);
    }
  };

  const getStyleDisplay = (styleObj) => {
    if (!styleObj || !palette) return null;
    if (styleObj.type === "own_voice") return { type: "own_voice", name: t('trends.styles.ownVoice') };
    if (styleObj.type === "cloned") {
      const p = palette.cloned?.find(c => c.profile_id === styleObj.profile_id);
      return { type: "cloned", name: p?.name || t('trends.styles.cloned') };
    }
    if (styleObj.type === "archetype") {
      const a = palette.archetypes?.find(ar => ar.key === styleObj.key);
      return { type: "archetype", name: a?.name || styleObj.key };
    }
    return null;
  };

  const handleCopy = () => {
    const text = result?.content || result?.generated_content || "";
    if (!text) return;
    navigator.clipboard.writeText(text);
    toast.success(t('common.copied'));
  };

  const handleFavorite = async () => {
    const text = result?.content || result?.generated_content || "";
    if (!text) return;
    try {
      const res = await api.post(`${API}/favorites/toggle`, {
        content: text,
        type: platform,
        generation_id: result?.generation_id || result?.id || null,
      });
      setIsFavorited(res.data.action === "added");
      toast.success(res.data.action === "added" ? t('generation.favoriteAdded') : t('generation.favoriteRemoved'));
    } catch {
      toast.error(t('generation.favoriteError'));
    }
  };

  const handleUseDraft = (draft) => {
    setResult({
      content: draft.content || draft.generated_content,
      generation_id: draft.id,
      character_count: (draft.content || draft.generated_content || "").length,
    });
    setLastUsedStyle(extractBackendStyle(draft));
  };

  const firstVariant = result?.variants?.[0];
  const content = firstVariant?.content || result?.content || result?.generated_content || "";

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="w-full sm:max-w-lg overflow-y-auto">
        <SheetHeader>
          <SheetTitle className="flex items-center gap-2">
            <Zap className="h-5 w-5 text-purple-500" />
            {t('trends.generateContent')}
          </SheetTitle>
        </SheetHeader>

        {trend && (
          <div className="space-y-5 mt-4">
            {/* Trend summary */}
            <div className="p-3 rounded-lg bg-secondary/30 border border-border/50">
              <div className="flex items-center gap-2 mb-1.5 flex-wrap">
                <h4 className="font-semibold text-sm">{trend.topic}</h4>
                {formatEngagement(trend.engagement_total) && (
                  <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-pink-500/20 text-pink-400">
                    {t('trends.signal.engagement', { count: formatEngagement(trend.engagement_total) })}
                  </span>
                )}
              </div>
              <p className="text-xs text-muted-foreground line-clamp-3">{trend.summary}</p>
            </div>

            {/* Key Angles */}
            {trend.key_angles && trend.key_angles.length > 0 && (
              <div className="space-y-2">
                <label className="text-sm font-medium flex items-center gap-1.5">
                  {t('trends.enrichment.keyAngles')}
                </label>
                <div className="space-y-1.5">
                  {trend.key_angles.map((angle, i) => (
                    <button
                      key={i}
                      onClick={() => setAdditionalContext(prev => prev ? `${prev}\n${angle.replace(/^A\u00e7\u0131 \d+:\s*/, '')}` : angle.replace(/^A\u00e7\u0131 \d+:\s*/, ''))}
                      className="w-full text-left p-2.5 rounded-lg bg-purple-500/5 border border-purple-500/10 hover:border-purple-500/30 hover:bg-purple-500/10 transition-all group/angle"
                    >
                      <div className="flex items-start gap-2">
                        <span className="text-purple-400 text-xs mt-0.5 flex-shrink-0">*</span>
                        <span className="text-xs text-foreground/80 group-hover/angle:text-foreground leading-relaxed">
                          {angle.replace(/^A\u00e7\u0131 \d+:\s*/, '')}
                        </span>
                      </div>
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Suggested Hooks */}
            {trend.suggested_hooks && typeof trend.suggested_hooks === 'object' && Object.keys(trend.suggested_hooks).length > 0 && (
              <div className="space-y-2">
                <label className="text-sm font-medium flex items-center gap-1.5">
                  {t('trends.enrichment.suggestedHooks')}
                </label>
                <div className="grid grid-cols-1 gap-2">
                  {Object.entries(trend.suggested_hooks).map(([pillar, hookText]) => {
                    const cfg = PILLAR_CONFIG[pillar] || { emoji: "\ud83d\udcdd", gradient: "from-gray-500 to-gray-600" };
                    return (
                      <button
                        key={pillar}
                        onClick={() => setAdditionalContext(hookText)}
                        className="text-left p-3 rounded-lg border border-border/50 hover:border-purple-500/30 bg-card/50 hover:bg-card transition-all group/hook"
                      >
                        <div className="flex items-center gap-2 mb-1.5">
                          <span className={cn("text-xs font-bold px-2 py-0.5 rounded-full text-white bg-gradient-to-r", cfg.gradient)}>
                            {cfg.emoji} {t(`trends.enrichment.${pillar}`)}
                          </span>
                          <span className="text-[10px] text-muted-foreground">
                            {t(`trends.enrichment.${pillar}Desc`)}
                          </span>
                        </div>
                        <p className="text-xs text-foreground/70 group-hover/hook:text-foreground leading-relaxed line-clamp-2">
                          {hookText}
                        </p>
                      </button>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Source Tweets */}
            {trend.source_tweets && trend.source_tweets.length > 0 && (
              <div className="space-y-2">
                <label className="text-sm font-medium flex items-center gap-1.5">
                  <span className="text-sky-400 text-xs">X</span>
                  {t('trends.signal.sourceTweets')}
                  <span className="text-xs text-muted-foreground font-normal">({trend.source_tweets.length})</span>
                </label>
                <div className="space-y-2 max-h-48 overflow-y-auto pr-1">
                  {trend.source_tweets.slice(0, 5).map((tw, i) => (
                    <div key={i} className="p-2.5 rounded-lg bg-sky-500/5 border border-sky-500/10">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-xs font-medium text-sky-400">@{tw.username}</span>
                        <span className={cn("text-[10px] px-1.5 py-0.5 rounded-full border", TIER_COLORS[tw.tier] || TIER_COLORS[3])}>
                          {tw.tier === 1 ? t('trends.enrichment.tier1') : tw.tier === 2 ? t('trends.enrichment.tier2') : t('trends.enrichment.tier3')}
                        </span>
                        {tw.likes > 0 && (
                          <span className="text-[10px] text-pink-400">{formatEngagement(tw.likes)}</span>
                        )}
                      </div>
                      <p className="text-xs text-muted-foreground line-clamp-2">{tw.text}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Content Pillars */}
            {trend.content_pillars && trend.content_pillars.length > 0 && (
              <div className="flex items-center gap-1.5 flex-wrap">
                <span className="text-xs text-muted-foreground">{t('trends.enrichment.contentPillars')}:</span>
                {trend.content_pillars.map((p, i) => (
                  <span key={i} className="text-[10px] px-2 py-0.5 rounded-full bg-secondary text-muted-foreground border border-border/50">
                    {p}
                  </span>
                ))}
              </div>
            )}

            {/* Drafts section */}
            {!draftsLoading && drafts.length > 0 && !result && (
              <div className="space-y-2">
                <label className="text-sm font-medium">{t('trends.generatePanel.readyDrafts')}</label>
                <div className="space-y-2">
                  {drafts.map((draft, i) => (
                    <div key={draft.id || i} className="p-3 rounded-lg border border-border/50 bg-secondary/20">
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-xs font-medium text-purple-400">{draft.platform || "twitter"}</span>
                        <Button variant="ghost" size="sm" className="h-6 text-xs text-purple-400 hover:text-purple-300" onClick={() => handleUseDraft(draft)}>
                          {t('trends.generatePanel.useDraft')}
                        </Button>
                      </div>
                      <p className="text-xs text-muted-foreground line-clamp-2">{draft.content || draft.generated_content}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Platform selector */}
            <div className="space-y-2">
              <label className="text-sm font-medium">{t('trends.generatePanel.platform')}</label>
              <div className="flex flex-wrap gap-2">
                {PLATFORMS.map((p) => (
                  <button
                    key={p.id}
                    onClick={() => setPlatform(p.id)}
                    className={cn(
                      "px-3 py-1.5 rounded-full text-sm font-medium transition-all border",
                      platform === p.id
                        ? "bg-gradient-to-r from-purple-600 to-indigo-600 text-white border-transparent"
                        : "bg-card border-border text-muted-foreground hover:text-foreground hover:border-purple-500/30"
                    )}
                  >
                    {p.emoji} {p.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Additional context */}
            <div className="space-y-2">
              <label className="text-sm font-medium">{t('trends.generatePanel.additionalContext')} <span className="text-muted-foreground font-normal">{t('trends.generatePanel.additionalContextOptional')}</span></label>
              <textarea
                value={additionalContext}
                onChange={(e) => setAdditionalContext(e.target.value)}
                placeholder={t('trends.generatePanel.additionalContextPlaceholder')}
                rows={3}
                className="w-full rounded-lg border border-border bg-secondary/30 px-3 py-2 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-purple-500/50 resize-none"
              />
            </div>

            {/* Action buttons */}
            <div className="flex gap-2">
              <Button
                onClick={handleGenerate}
                disabled={loading}
                className="flex-1 bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-700 hover:to-indigo-700 text-white"
              >
                {loading ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <Zap className="h-4 w-4 mr-2" />}
                {loading ? t('trends.generatePanel.generating') : t('trends.generatePanel.quickGenerate')}
              </Button>
              <Button
                onClick={handleGoToModule}
                variant="outline"
                className="flex-1"
              >
                <ExternalLink className="h-4 w-4 mr-2" />
                {t('trends.generatePanel.goToModule')}
              </Button>
            </div>

            {/* Loading skeleton */}
            {loading && (
              <div className="space-y-2 animate-pulse">
                <div className="h-4 bg-secondary rounded w-full" />
                <div className="h-4 bg-secondary rounded w-5/6" />
                <div className="h-4 bg-secondary rounded w-4/6" />
                <div className="h-4 bg-secondary rounded w-3/6" />
              </div>
            )}

            {/* Result */}
            {content && !loading && (
              <div className="rounded-lg border border-border p-4 space-y-3">
                {(() => {
                  const sd = getStyleDisplay(lastUsedStyle);
                  return sd ? (
                    <div className="flex items-center gap-2">
                      <span className="text-[10px] text-muted-foreground">{t('trends.styles.label')}:</span>
                      <StyleChip styleType={sd.type} styleName={sd.name} />
                    </div>
                  ) : null;
                })()}

                <p className="text-sm whitespace-pre-wrap">{content}</p>

                {result?.character_count && (
                  <Badge variant="secondary" className="text-xs">
                    {t('common.nCharacters', { count: result.character_count })}
                  </Badge>
                )}

                <div className="flex items-center gap-2 pt-2 border-t border-border flex-wrap">
                  <Button variant="ghost" size="sm" onClick={handleCopy} className="gap-1.5">
                    <Copy className="h-4 w-4" /> {t('common.copy')}
                  </Button>
                  <Button
                    variant="ghost" size="sm"
                    onClick={handleFavorite}
                    className={cn("gap-1.5", isFavorited && "text-red-500")}
                  >
                    <Heart className={cn("h-4 w-4", isFavorited && "fill-current")} />
                  </Button>
                  <Button variant="ghost" size="sm" onClick={handleGenerate} className="gap-1.5">
                    <RotateCcw className="h-4 w-4" /> {t('trends.generatePanel.regenerate')}
                  </Button>

                  {palette && (
                    <div className="relative ml-auto">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => {
                          if (!canRegenerateWithStyle) return;
                          setStyleOverrideOpen(prev => !prev);
                        }}
                        disabled={!canRegenerateWithStyle}
                        className={cn(
                          "gap-1.5 text-violet-400 hover:text-violet-300 hover:bg-violet-500/10",
                          !canRegenerateWithStyle && "opacity-40 cursor-not-allowed"
                        )}
                      >
                        <Wand2 className="h-4 w-4" />
                        {t('trends.styles.regenerateWith')}
                      </Button>

                      {styleOverrideOpen && canRegenerateWithStyle && (
                        <>
                          <div
                            className="fixed inset-0 z-40"
                            onClick={() => setStyleOverrideOpen(false)}
                          />
                          <div className="absolute bottom-full right-0 mb-2 w-52 rounded-xl border border-border bg-popover shadow-2xl z-50 overflow-hidden animate-[fadeIn_0.15s_ease-out]">
                            <p className="text-[9px] uppercase tracking-[0.15em] text-muted-foreground px-3 pt-3 pb-1.5 font-semibold">{t('trends.styles.selectStyle')}</p>

                            {palette.own_voice && (
                              <button
                                className="w-full flex items-center gap-2 px-3 py-2 hover:bg-accent text-left transition-colors"
                                onClick={() => handleRegenerateWithStyle({ type: "own_voice" })}
                              >
                                <span>\ud83c\udfa4</span>
                                <span className="text-[11px] text-foreground">{t('trends.styles.ownVoice')}</span>
                              </button>
                            )}

                            {(palette.cloned || []).map(p => (
                              <button
                                key={p.profile_id}
                                className="w-full flex items-center gap-2 px-3 py-2 hover:bg-accent text-left transition-colors"
                                onClick={() => handleRegenerateWithStyle({ type: "cloned", profile_id: p.profile_id })}
                              >
                                <span>\ud83d\udc64</span>
                                <span className="text-[11px] text-foreground truncate">{p.name}</span>
                              </button>
                            ))}

                            {(palette.archetypes || []).length > 0 && (
                              <div className="border-t border-border mt-1 pt-1">
                                {palette.archetypes.map(a => (
                                  <button
                                    key={a.key}
                                    className="w-full flex items-center gap-2 px-3 py-2 hover:bg-accent text-left transition-colors"
                                    onClick={() => handleRegenerateWithStyle({ type: "archetype", key: a.key })}
                                  >
                                    <span>{a.emoji}</span>
                                    <span className="text-[11px] text-foreground truncate">{a.name}</span>
                                  </button>
                                ))}
                              </div>
                            )}

                            <div className="h-2" />
                          </div>
                        </>
                      )}
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        )}
      </SheetContent>
    </Sheet>
  );
}
