/**
 * @deprecated KULLANILMIYOR (2026-06-14) — hicbir yerden import edilmiyor; route/nav yok.
 * Referans icin tutuluyor; aktif uygulama akisinin parcasi DEGIL. Bkz: docs/DEPRECATED_MODULES.md
 */
import { useState, useEffect } from "react";
import { Dna, ChevronDown, X, Sparkles, ExternalLink } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { useNavigate } from "react-router-dom";
import api, { API } from "@/lib/api";


export default function StyleSelector({ value, onChange }) {
  const [profiles, setProfiles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedProfile, setSelectedProfile] = useState(null);
  const navigate = useNavigate();

  useEffect(() => {
    fetchProfiles();
  }, []);

  useEffect(() => {
    if (value && profiles.length > 0) {
      const profile = profiles.find((p) => p.id === value);
      setSelectedProfile(profile || null);
    } else {
      setSelectedProfile(null);
    }
  }, [value, profiles]);

  const fetchProfiles = async () => {
    try {
      const response = await api.get(`${API}/styles/list`);
      setProfiles(response.data || []);
    } catch (error) {
      console.error("Failed to fetch profiles:", error);
    } finally {
      setLoading(false);
    }
  };

  const handleSelect = (profile) => {
    onChange(profile?.id || null);
  };

  const handleClear = (e) => {
    e.stopPropagation();
    onChange(null);
  };

  if (loading) {
    return (
      <div className="h-10 w-full rounded-lg bg-secondary/50 animate-pulse" />
    );
  }

  return (
    <div className="space-y-2">
      <label className="text-sm font-medium flex items-center gap-2">
        <Dna className="h-4 w-4 text-purple-400" />
        Stil Klonlama
      </label>

      {selectedProfile ? (
        <div className="flex items-center gap-2 p-3 rounded-lg bg-gradient-to-r from-purple-500/10 to-pink-500/10 border border-purple-500/30">
          <div className="h-8 w-8 rounded-lg bg-gradient-to-br from-purple-500 to-pink-500 flex items-center justify-center">
            <Dna className="h-4 w-4 text-white" />
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium truncate">{selectedProfile.name}</p>
            <p className="text-xs text-muted-foreground">
              {selectedProfile.style_summary?.tweet_count || 0} tweet analiz edildi
            </p>
          </div>
          <Button
            variant="ghost"
            size="icon"
            onClick={handleClear}
            className="h-8 w-8 shrink-0"
          >
            <X className="h-4 w-4" />
          </Button>
        </div>
      ) : (
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button
              variant="outline"
              className={cn(
                "w-full justify-between h-auto py-3",
                "bg-secondary/30 border-dashed hover:border-purple-500/50 hover:bg-purple-500/5"
              )}
            >
              <div className="flex items-center gap-2">
                <Sparkles className="h-4 w-4 text-muted-foreground" />
                <span className="text-muted-foreground">Stil profili seç (opsiyonel)</span>
              </div>
              <ChevronDown className="h-4 w-4 text-muted-foreground" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="start" className="w-[300px]">
            {profiles.length === 0 ? (
              <div className="p-4 text-center">
                <Dna className="h-8 w-8 text-muted-foreground mx-auto mb-2" />
                <p className="text-sm text-muted-foreground mb-3">
                  Henüz stil profili yok
                </p>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => navigate("/dashboard/style-lab")}
                  className="gap-1"
                >
                  <ExternalLink className="h-3 w-3" />
                  Style Lab'a Git
                </Button>
              </div>
            ) : (
              <>
                {profiles.map((profile) => (
                  <DropdownMenuItem
                    key={profile.id}
                    onClick={() => handleSelect(profile)}
                    className="flex items-center gap-3 p-3 cursor-pointer"
                  >
                    <div className="h-8 w-8 rounded-lg bg-gradient-to-br from-purple-500 to-pink-500 flex items-center justify-center shrink-0">
                      <Dna className="h-4 w-4 text-white" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="font-medium truncate">{profile.name}</p>
                      <p className="text-xs text-muted-foreground">
                        Ort. {profile.style_summary?.avg_length || 0} karakter
                      </p>
                    </div>
                    <Badge variant="secondary" className="shrink-0">
                      {profile.style_summary?.avg_likes?.toFixed(0) || 0} ❤️
                    </Badge>
                  </DropdownMenuItem>
                ))}
                <DropdownMenuSeparator />
                <DropdownMenuItem
                  onClick={() => navigate("/dashboard/style-lab")}
                  className="flex items-center gap-2 text-muted-foreground"
                >
                  <ExternalLink className="h-4 w-4" />
                  Style Lab'da Yeni Profil Oluştur
                </DropdownMenuItem>
              </>
            )}
          </DropdownMenuContent>
        </DropdownMenu>
      )}

      {selectedProfile && (
        <p className="text-xs text-purple-400">
          Tweet'ler {selectedProfile.name} tarzında üretilecek
        </p>
      )}
    </div>
  );
}
