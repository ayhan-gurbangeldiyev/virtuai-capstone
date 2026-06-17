import { useState, useEffect } from "react";
import { useTranslation } from 'react-i18next';
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { 
  Heart, 
  Copy, 
  Send, 
  Trash2,
  Loader2,
  HeartOff,
  Calendar,
  CheckSquare,
  Square,
  X,
  Undo2,
  Clock,
  AlertTriangle,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { toast } from "sonner";
import api, { API } from "@/lib/api";


const TYPE_CONFIG = {
  tweet: { labelKey: "create.contentTypes.tweet", color: "bg-sky-500/10 text-sky-400 border-sky-500/20" },
  quote: { labelKey: "create.contentTypes.quote", color: "bg-purple-500/10 text-purple-400 border-purple-500/20" },
  reply: { labelKey: "create.contentTypes.reply", color: "bg-green-500/10 text-green-400 border-green-500/20" },
  article: { labelKey: "create.contentTypes.article", color: "bg-orange-500/10 text-orange-400 border-orange-500/20" },
};

function daysLeft(deletedAt) {
  if (!deletedAt) return 30;
  const deleted = new Date(deletedAt);
  const expiry = new Date(deleted.getTime() + 30 * 24 * 60 * 60 * 1000);
  const now = new Date();
  const diff = Math.ceil((expiry - now) / (1000 * 60 * 60 * 24));
  return Math.max(0, diff);
}

export default function FavoritesPage() {
  const { t } = useTranslation();
  const [favorites, setFavorites] = useState([]);
  const [trash, setTrash] = useState([]);
  const [loading, setLoading] = useState(true);
  const [accountAvatarUrl, setAccountAvatarUrl] = useState(null);

  useEffect(() => {
    (async () => {
      try {
        const res = await api.get(`${API}/accounts`);
        const accounts = res.data || [];
        const primary = accounts.find(a => a.is_primary) || accounts[0];
        if (primary?.username) {
          const avatars = { twitter: u => `https://unavatar.io/x/${u}`, instagram: u => `${API}/accounts/avatar/instagram/${u}`, youtube: u => `https://unavatar.io/youtube/${u}`, tiktok: u => `https://unavatar.io/tiktok/${u}` };
          const fn = avatars[primary.platform];
          if (fn) setAccountAvatarUrl(fn(primary.username));
        }
      } catch {}
    })();
  }, []);
  const [trashLoading, setTrashLoading] = useState(false);
  const [showTrash, setShowTrash] = useState(false);
  const [selectionMode, setSelectionMode] = useState(false);
  const [selectedIds, setSelectedIds] = useState(new Set());
  const [activeTab, setActiveTab] = useState("favorites"); // "favorites" | "trash"

  useEffect(() => {
    fetchFavorites();
  }, []);

  const fetchFavorites = async () => {
    try {
      const response = await api.get(`${API}/favorites`);
      setFavorites(response.data || []);
    } catch (error) {
      console.error("Favorites fetch error:", error);
      setFavorites([]);
    } finally {
      setLoading(false);
    }
  };

  const fetchTrash = async () => {
    setTrashLoading(true);
    try {
      const response = await api.get(`${API}/favorites/trash`);
      setTrash(response.data || []);
    } catch (error) {
      console.error("Trash fetch error:", error);
      setTrash([]);
    } finally {
      setTrashLoading(false);
    }
  };

  // Tab değişince trash'i yükle
  useEffect(() => {
    if (activeTab === "trash" && trash.length === 0) {
      fetchTrash();
    }
  }, [activeTab]);

  const toggleSelect = (id) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  // ── Favoriden Çıkar (hard delete, toggle off) ──
  const handleUnfavorite = async (id) => {
    try {
      await api.delete(`${API}/favorites/${id}`);
      setFavorites((prev) => prev.filter((f) => f.id !== id));
      toast.success(t('favorites.unfavorited'));
    } catch {
      toast.error(t('common.error'));
    }
  };

  // ── Sil (soft delete → çöp kutusuna) ──
  const handleSoftDelete = async (id) => {
    try {
      await api.post(`${API}/favorites/${id}/soft-delete`);
      const item = favorites.find((f) => f.id === id);
      setFavorites((prev) => prev.filter((f) => f.id !== id));
      if (item) setTrash((prev) => [{ ...item, deleted_at: new Date().toISOString() }, ...prev]);
      toast.success(t('favorites.movedToTrash'));
    } catch {
      toast.error(t('history.deleteError'));
    }
  };

  // ── Tümünü Sil (soft delete all) ──
  const handleDeleteAll = async () => {
    if (!window.confirm(t('favorites.moveAllToTrashConfirm'))) return;
    try {
      const res = await api.delete(`${API}/favorites/all`);
      // Taşınanları trash'e ekle
      setTrash((prev) => [...favorites.map(f => ({ ...f, deleted_at: new Date().toISOString() })), ...prev]);
      setFavorites([]);
      toast.success(t('favorites.allMovedToTrash', { count: res.data.deleted }));
    } catch {
      toast.error(t('history.deleteError'));
    }
  };

  // ── Seçilenleri Sil (soft delete bulk) ──
  const handleDeleteSelected = async () => {
    if (selectedIds.size === 0) return;
    if (!window.confirm(t('favorites.bulkMoveConfirm', { count: selectedIds.size }))) return;
    try {
      const ids = Array.from(selectedIds);
      await api.delete(`${API}/favorites/bulk`, { data: { ids } });
      const moved = favorites.filter((f) => selectedIds.has(f.id));
      setTrash((prev) => [...moved.map(f => ({ ...f, deleted_at: new Date().toISOString() })), ...prev]);
      setFavorites((prev) => prev.filter((f) => !selectedIds.has(f.id)));
      toast.success(t('favorites.allMovedToTrash', { count: ids.length }));
      setSelectedIds(new Set());
      setSelectionMode(false);
    } catch {
      toast.error(t('history.deleteError'));
    }
  };

  // ── Geri Al (restore) ──
  const handleRestore = async (id) => {
    try {
      await api.post(`${API}/favorites/${id}/restore`);
      const item = trash.find((f) => f.id === id);
      setTrash((prev) => prev.filter((f) => f.id !== id));
      if (item) setFavorites((prev) => [{ ...item, deleted_at: null }, ...prev]);
      toast.success(t('favorites.restored'));
    } catch {
      toast.error(t('favorites.restoreError'));
    }
  };

  // ── Kalıcı Sil (hard delete from trash) ──
  const handlePermanentDelete = async (id) => {
    if (!window.confirm(t('favorites.permanentDeleteConfirm'))) return;
    try {
      await api.delete(`${API}/favorites/${id}`);
      setTrash((prev) => prev.filter((f) => f.id !== id));
      toast.success(t('favorites.permanentlyDeleted'));
    } catch {
      toast.error(t('history.deleteError'));
    }
  };

  // ── Çöp Kutusunu Boşalt ──
  const handlePurgeTrash = async () => {
    if (!window.confirm(t('favorites.purgeConfirm'))) return;
    try {
      const res = await api.delete(`${API}/favorites/trash/purge`);
      setTrash([]);
      toast.success(t('favorites.purged', { count: res.data.purged }));
    } catch {
      toast.error(t('favorites.purgeError'));
    }
  };

  const handleCopy = (content) => {
    navigator.clipboard.writeText(content);
    toast.success(t('common.copied'));
  };

  const handleTweet = (content) => {
    const tweetUrl = `https://twitter.com/intent/tweet?text=${encodeURIComponent(content)}`;
    window.open(tweetUrl, "_blank");
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="max-w-4xl" data-testid="favorites-page">
      {/* Header */}
      <div className="mb-6">
        <h1 className="font-outfit text-4xl font-bold tracking-tight mb-2 flex items-center gap-3">
          <Heart className="h-10 w-10 text-red-500" />
          {t('favorites.title')}
        </h1>
        <p className="text-muted-foreground">
          {t('favorites.subtitle')}
        </p>
      </div>

      {/* Tabs: Favoriler / Çöp Kutusu */}
      <div className="flex items-center gap-2 mb-6">
        <button
          onClick={() => { setActiveTab("favorites"); setSelectionMode(false); setSelectedIds(new Set()); }}
          className={cn(
            "px-4 py-2 rounded-full text-sm font-medium transition-all border",
            activeTab === "favorites"
              ? "bg-foreground text-background border-transparent"
              : "bg-secondary text-muted-foreground hover:bg-secondary/80 border-border"
          )}
        >
          <Heart className="h-3.5 w-3.5 inline mr-1.5" />
          {t('favorites.title')} ({favorites.length})
        </button>
        <button
          onClick={() => { setActiveTab("trash"); setSelectionMode(false); setSelectedIds(new Set()); }}
          className={cn(
            "px-4 py-2 rounded-full text-sm font-medium transition-all border",
            activeTab === "trash"
              ? "bg-foreground text-background border-transparent"
              : "bg-secondary text-muted-foreground hover:bg-secondary/80 border-border"
          )}
        >
          <Trash2 className="h-3.5 w-3.5 inline mr-1.5" />
          {t('favorites.trashTab')} {trash.length > 0 && `(${trash.length})`}
        </button>
      </div>

      {/* ═══════════════════ FAVORİLER TAB ═══════════════════ */}
      {activeTab === "favorites" && (
        <>
          {/* Action bar */}
          {favorites.length > 0 && (
            <div className="flex items-center gap-2 mb-4">
              {!selectionMode ? (
                <>
                  <Button variant="outline" size="sm" onClick={() => { setSelectionMode(true); setSelectedIds(new Set()); }}>
                    <CheckSquare className="h-4 w-4 mr-1.5" /> {t('history.selectMode')}
                  </Button>
                  <Button variant="outline" size="sm" className="text-red-400 hover:text-red-300 hover:bg-red-500/10" onClick={handleDeleteAll}>
                    <Trash2 className="h-4 w-4 mr-1.5" /> {t('history.deleteAll')}
                  </Button>
                </>
              ) : (
                <>
                  <Button variant="outline" size="sm" onClick={() => { setSelectionMode(false); setSelectedIds(new Set()); }}>
                    <X className="h-4 w-4 mr-1.5" /> {t('common.cancel')}
                  </Button>
                  <Button variant="outline" size="sm" className="text-red-400 hover:text-red-300 hover:bg-red-500/10" onClick={handleDeleteSelected} disabled={selectedIds.size === 0}>
                    <Trash2 className="h-4 w-4 mr-1.5" /> {t('history.deleteSelected', { count: selectedIds.size })}
                  </Button>
                </>
              )}
            </div>
          )}

          {favorites.length === 0 ? (
            <Card className="bg-card border-border">
              <CardContent className="py-16 text-center">
                <HeartOff className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
                <h3 className="font-outfit text-xl font-semibold mb-2">{t('favorites.noFavorites')}</h3>
                <p className="text-muted-foreground">
                  {t('favorites.noFavoritesDesc')}
                </p>
              </CardContent>
            </Card>
          ) : (
            <div className="space-y-4">
              {favorites.map((fav) => {
                const typeConfig = TYPE_CONFIG[fav.type] || { labelKey: fav.type || "create.contentTypes.tweet", color: "bg-secondary text-muted-foreground" };
                return (
                  <Card key={fav.id} className={cn("bg-card border-border hover:border-primary/20 transition-colors", selectedIds.has(fav.id) && "border-primary/40 bg-primary/5")}>
                    <CardContent className="p-4">
                      <div className="flex items-start justify-between gap-4 mb-3">
                        <div className="flex items-center gap-2">
                          {selectionMode && (
                            <button onClick={() => toggleSelect(fav.id)} className="mr-1">
                              {selectedIds.has(fav.id) ? <CheckSquare className="h-5 w-5 text-primary" /> : <Square className="h-5 w-5 text-muted-foreground" />}
                            </button>
                          )}
                          {accountAvatarUrl && (
                            <img src={accountAvatarUrl} alt="" className="h-6 w-6 rounded-full object-cover" onError={(e) => { e.target.style.display = 'none'; }} />
                          )}
                          <Badge className={typeConfig.color}>{t(typeConfig.labelKey)}</Badge>
                          {fav.variant_index != null && fav.variant_index > 0 && (
                            <Badge variant="outline" className="text-xs">{t('common.variant')} {fav.variant_index + 1}</Badge>
                          )}
                          {fav.created_at && (
                            <span className="text-xs text-muted-foreground flex items-center gap-1">
                              <Calendar className="h-3 w-3" />
                              {new Date(fav.created_at).toLocaleDateString("tr-TR", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" })}
                            </span>
                          )}
                        </div>
                        {!selectionMode && (
                          <div className="flex items-center gap-1">
                            <Button variant="ghost" size="sm" className="h-8 gap-1.5" onClick={() => handleCopy(fav.content)}>
                              <Copy className="h-4 w-4" />
                              <span className="hidden sm:inline">{t('common.copy')}</span>
                            </Button>
                            <Button variant="ghost" size="sm" className="h-8 gap-1.5 text-sky-400 hover:text-sky-300" onClick={() => handleTweet(fav.content)}>
                              <Send className="h-4 w-4" />
                              <span className="hidden sm:inline">{t('common.tweetle')}</span>
                            </Button>
                            <Button
                              variant="ghost" size="sm"
                              className="h-8 text-muted-foreground hover:text-foreground"
                              onClick={() => handleUnfavorite(fav.id)}
                              title={t('favorites.removeFromFavorites')}
                            >
                              <HeartOff className="h-4 w-4" />
                            </Button>
                            <Button
                              variant="ghost" size="sm"
                              className="h-8 text-red-400 hover:text-red-300 hover:bg-red-500/10"
                              onClick={() => handleSoftDelete(fav.id)}
                              title={t('favorites.moveToTrash')}
                            >
                              <Trash2 className="h-4 w-4" />
                            </Button>
                          </div>
                        )}
                      </div>
                      
                      <p className="text-sm whitespace-pre-wrap">{fav.content}</p>
                      
                      <div className="flex items-center gap-2 mt-3">
                        <Badge variant="secondary" className="text-xs">
                          {t('common.nCharacters', { count: fav.content?.length || 0 })}
                        </Badge>
                      </div>
                    </CardContent>
                  </Card>
                );
              })}
            </div>
          )}
        </>
      )}

      {/* ═══════════════════ ÇÖP KUTUSU TAB ═══════════════════ */}
      {activeTab === "trash" && (
        <>
          {/* Info banner */}
          <div className="flex items-center gap-2 p-3 rounded-lg bg-amber-500/10 border border-amber-500/20 text-amber-400 text-sm mb-4">
            <AlertTriangle className="h-4 w-4 flex-shrink-0" />
            <span>{t('favorites.trashInfo')}</span>
          </div>

          {/* Actions */}
          {trash.length > 0 && (
            <div className="flex items-center gap-2 mb-4">
              <Button variant="outline" size="sm" className="text-red-400 hover:text-red-300 hover:bg-red-500/10" onClick={handlePurgeTrash}>
                <Trash2 className="h-4 w-4 mr-1.5" /> {t('favorites.emptyTrash')}
              </Button>
            </div>
          )}

          {trashLoading ? (
            <div className="flex items-center justify-center min-h-[200px]">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          ) : trash.length === 0 ? (
            <Card className="bg-card border-border">
              <CardContent className="py-16 text-center">
                <Trash2 className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
                <h3 className="font-outfit text-xl font-semibold mb-2">{t('favorites.trashEmpty')}</h3>
                <p className="text-muted-foreground">
                  {t('favorites.trashEmptyDesc')}
                </p>
              </CardContent>
            </Card>
          ) : (
            <div className="space-y-4">
              {trash.map((fav) => {
                const typeConfig = TYPE_CONFIG[fav.type] || { labelKey: fav.type || "create.contentTypes.tweet", color: "bg-secondary text-muted-foreground" };
                const remaining = daysLeft(fav.deleted_at);
                return (
                  <Card key={fav.id} className="bg-card border-border opacity-75 hover:opacity-100 transition-opacity">
                    <CardContent className="p-4">
                      <div className="flex items-start justify-between gap-4 mb-3">
                        <div className="flex items-center gap-2">
                          <Badge className={typeConfig.color}>{t(typeConfig.labelKey)}</Badge>
                          <Badge variant="outline" className={cn("text-xs gap-1", remaining <= 7 ? "text-red-400 border-red-500/30" : "text-amber-400 border-amber-500/30")}>
                            <Clock className="h-3 w-3" />
                            {t('favorites.daysLeft', { count: remaining })}
                          </Badge>
                        </div>
                        <div className="flex items-center gap-1">
                          <Button
                            variant="outline" size="sm"
                            className="h-8 gap-1.5 text-green-400 hover:text-green-300 hover:bg-green-500/10 border-green-500/30"
                            onClick={() => handleRestore(fav.id)}
                          >
                            <Undo2 className="h-4 w-4" />
                            <span className="hidden sm:inline">{t('favorites.restore')}</span>
                          </Button>
                          <Button
                            variant="ghost" size="sm"
                            className="h-8 text-red-400 hover:text-red-300 hover:bg-red-500/10"
                            onClick={() => handlePermanentDelete(fav.id)}
                            title={t('common.delete')}
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </div>
                      </div>
                      
                      <p className="text-sm whitespace-pre-wrap text-muted-foreground">{fav.content}</p>
                      
                      <div className="flex items-center gap-2 mt-3">
                        <Badge variant="secondary" className="text-xs">
                          {t('common.nCharacters', { count: fav.content?.length || 0 })}
                        </Badge>
                        {fav.deleted_at && (
                          <span className="text-xs text-muted-foreground">
                            {t('favorites.deletedAt', { date: new Date(fav.deleted_at).toLocaleDateString("tr-TR", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }) })}
                          </span>
                        )}
                      </div>
                    </CardContent>
                  </Card>
                );
              })}
            </div>
          )}
        </>
      )}
    </div>
  );
}
