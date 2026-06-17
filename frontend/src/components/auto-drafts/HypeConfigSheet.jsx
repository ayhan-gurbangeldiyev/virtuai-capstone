/**
 * HypeConfigSheet — right-slide settings drawer.
 *
 * Sections:
 *  1. Voice description
 *  2. Topics focus
 *  3. Forbidden topics (with presets)
 *  4. Watch accounts
 *  5. Schedule (daily quota)
 *  6. Safety (dry-run + auto-publish with confirm)
 */
import { useState, useEffect } from "react";
import { useTranslation } from "react-i18next";
import { Link as LinkIcon, Sparkles } from "lucide-react";
import { useNavigate } from "react-router-dom";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
  SheetFooter,
} from "@/components/ui/sheet";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { listStyleProfiles } from "@/services/hypeService";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Slider } from "@/components/ui/slider";
import { Label } from "@/components/ui/label";
import TagInput from "./TagInput";

const FORBIDDEN_PRESETS = ["politics", "religion", "medical_advice", "financial_advice"];

export default function HypeConfigSheet({
  open,
  config,
  accountUsername,
  onClose,
  onSave,
}) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [form, setForm] = useState(emptyForm());
  const [confirmAutoPublish, setConfirmAutoPublish] = useState(false);
  const [styleProfiles, setStyleProfiles] = useState([]);

  useEffect(() => {
    if (open && config) {
      setForm({
        forbidden_topics: config.forbidden_topics || [],
        daily_post_quota: config.daily_post_quota ?? 2,
        dry_run_mode: config.dry_run_mode !== false,
        auto_publish_enabled: config.auto_publish_enabled === true,
        active_style_profile_id: config.active_style_profile_id || "",
      });
    } else if (open && !config) {
      setForm(emptyForm());
    }
  }, [open, config]);

  // Phase 17.2 — load user's style profiles for the dropdown
  useEffect(() => {
    if (!open) return;
    listStyleProfiles()
      .then((r) => setStyleProfiles(r.items || []))
      .catch(() => setStyleProfiles([]));
  }, [open]);

  const set = (key, value) => setForm((f) => ({ ...f, [key]: value }));

  const handleSave = () => onSave(form);

  const handleAutoPublishToggle = (next) => {
    if (next === true && !form.auto_publish_enabled) {
      setConfirmAutoPublish(true);
      return;
    }
    set("auto_publish_enabled", next);
  };

  const confirmAutoPublishOn = () => {
    set("auto_publish_enabled", true);
    set("dry_run_mode", false);
    setConfirmAutoPublish(false);
  };

  const estimatedMonthlyCost = (form.daily_post_quota * 0.01 * 30).toFixed(2);

  return (
    <>
      <Sheet open={open} onOpenChange={(v) => !v && onClose()}>
        <SheetContent
          side="right"
          className="w-full sm:max-w-lg overflow-y-auto"
        >
          <SheetHeader>
            <SheetTitle className="font-outfit">{t("autoDrafts.config.title")}</SheetTitle>
            <SheetDescription>
              {accountUsername ? `@${accountUsername} · ` : ""}
              {t("autoDrafts.config.subtitle")}
            </SheetDescription>
          </SheetHeader>

          <div className="space-y-7 py-5">
            {/* Style Profile (Phase 17.2) */}
            <Section title={t("autoDrafts.config.sections.styleProfile")}>
              <Label className="text-xs text-muted-foreground">
                {t("autoDrafts.config.styleProfile")}
              </Label>
              {styleProfiles.length === 0 ? (
                <div className="rounded-lg bg-purple-500/5 border border-purple-500/20 p-3 space-y-2">
                  <p className="text-xs text-foreground/85 leading-relaxed">
                    {t("autoDrafts.config.styleProfileEmptyTitle")}
                  </p>
                  <div className="flex flex-col sm:flex-row gap-2">
                    <Button
                      size="sm"
                      onClick={() => { onClose(); navigate("/dashboard/style-lab"); }}
                      className="bg-purple-600 hover:bg-purple-700 text-white gap-1.5"
                    >
                      <Sparkles className="h-3.5 w-3.5" />
                      {t("autoDrafts.config.styleProfileEmptyCtaStyleLab")}
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => { onClose(); navigate("/dashboard/creator-hub"); }}
                    >
                      {t("autoDrafts.config.styleProfileEmptyCtaCreatorHub")}
                    </Button>
                  </div>
                </div>
              ) : (
                <>
                  <Select
                    value={form.active_style_profile_id || "__none__"}
                    onValueChange={(v) => set("active_style_profile_id", v === "__none__" ? null : v)}
                  >
                    <SelectTrigger className="text-sm">
                      <SelectValue placeholder={t("autoDrafts.config.styleProfilePlaceholder")} />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="__none__">
                        <span className="text-muted-foreground italic">
                          {t("autoDrafts.config.styleProfileNone")}
                        </span>
                      </SelectItem>
                      {styleProfiles.map((p) => (
                        <SelectItem key={p.id} value={p.id}>
                          <span className="flex items-center gap-2">
                            <Sparkles className="h-3 w-3 text-purple-500" />
                            {p.name}
                            <span className="text-[10px] text-muted-foreground font-mono">
                              · {p.tweet_count} tw
                            </span>
                          </span>
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <p className="text-[11px] text-muted-foreground leading-relaxed">
                    {t("autoDrafts.config.styleProfileHint")}
                  </p>
                  <button
                    type="button"
                    onClick={() => { onClose(); navigate("/dashboard/style-lab"); }}
                    className="inline-flex items-center gap-1.5 text-[11px] text-purple-600 dark:text-purple-400 hover:underline"
                  >
                    <LinkIcon className="h-3 w-3" />
                    {t("autoDrafts.config.styleProfileCta")}
                  </button>
                </>
              )}
            </Section>

            {/* Forbidden topics */}
            <Section title={t("autoDrafts.config.sections.forbidden")}>
              <Label className="text-xs text-muted-foreground">
                {t("autoDrafts.config.forbiddenTopics")}
              </Label>
              <TagInput
                value={form.forbidden_topics}
                onChange={(v) => set("forbidden_topics", v)}
                placeholder={t("autoDrafts.config.forbiddenTopicsPlaceholder")}
                presets={FORBIDDEN_PRESETS}
              />
            </Section>

            {/* Schedule */}
            <Section title={t("autoDrafts.config.sections.schedule")}>
              <Label className="text-xs text-muted-foreground">
                {t("autoDrafts.config.dailyQuota")}
              </Label>
              <div className="px-1 pt-1">
                <Slider
                  value={[form.daily_post_quota]}
                  onValueChange={([v]) => set("daily_post_quota", v)}
                  min={0}
                  max={10}
                  step={1}
                />
              </div>
              <p className="text-[11px] text-muted-foreground">
                {t("autoDrafts.config.dailyQuotaHint", {
                  count: form.daily_post_quota,
                  cost: estimatedMonthlyCost,
                })}
              </p>
            </Section>

            {/* Safety */}
            <Section title={t("autoDrafts.config.sections.safety")}>
              <SwitchRow
                label={t("autoDrafts.config.dryRunMode")}
                hint={t("autoDrafts.config.dryRunModeHint")}
                checked={form.dry_run_mode}
                onChange={(v) => set("dry_run_mode", v)}
              />
              <SwitchRow
                label={t("autoDrafts.config.autoPublishEnabled")}
                hint={t("autoDrafts.config.autoPublishHint")}
                checked={form.auto_publish_enabled}
                onChange={handleAutoPublishToggle}
                danger
              />
            </Section>
          </div>

          <SheetFooter className="sticky bottom-0 bg-background/95 backdrop-blur border-t border-border/50 -mx-6 px-6 py-4 gap-2 sm:gap-2">
            <Button variant="ghost" onClick={onClose}>{t("common.cancel")}</Button>
            <Button onClick={handleSave} className="bg-purple-600 hover:bg-purple-700 text-white">
              {t("autoDrafts.config.save")}
            </Button>
          </SheetFooter>
        </SheetContent>
      </Sheet>

      <AlertDialog open={confirmAutoPublish} onOpenChange={setConfirmAutoPublish}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t("autoDrafts.config.autoPublishConfirmTitle")}</AlertDialogTitle>
            <AlertDialogDescription>
              {t("autoDrafts.config.autoPublishConfirmBody")}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{t("autoDrafts.config.autoPublishConfirmNo")}</AlertDialogCancel>
            <AlertDialogAction
              onClick={confirmAutoPublishOn}
              className="bg-rose-600 hover:bg-rose-700 text-white"
            >
              {t("autoDrafts.config.autoPublishConfirmYes")}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}

function emptyForm() {
  return {
    forbidden_topics: [...FORBIDDEN_PRESETS],
    daily_post_quota: 2,
    dry_run_mode: true,
    auto_publish_enabled: false,
    active_style_profile_id: "",
  };
}

function Section({ title, children }) {
  return (
    <section className="space-y-2">
      <h3 className="text-[11px] font-semibold uppercase tracking-widest text-muted-foreground">
        {title}
      </h3>
      <div className="space-y-2">{children}</div>
    </section>
  );
}

function SwitchRow({ label, hint, checked, onChange, danger }) {
  return (
    <div className="flex items-start justify-between gap-3 py-2">
      <div className="flex-1 min-w-0">
        <p className={`text-sm font-medium ${danger && checked ? "text-rose-600 dark:text-rose-400" : ""}`}>
          {label}
        </p>
        <p className="text-[11px] text-muted-foreground mt-0.5">{hint}</p>
      </div>
      <Switch checked={checked} onCheckedChange={onChange} />
    </div>
  );
}
