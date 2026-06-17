/**
 * @deprecated KULLANILMIYOR (2026-06-14) — hicbir yerden import edilmiyor; route/nav yok.
 * Referans icin tutuluyor; aktif uygulama akisinin parcasi DEGIL. Bkz: docs/DEPRECATED_MODULES.md
 */
import { useState, useEffect } from "react";
import { Outlet, NavLink, useLocation, useNavigate } from "react-router-dom";
import {
  Sun, Moon, Settings, Layers, LogOut, User, History, Heart,
  ChevronDown, Sparkles, Dna, TrendingUp, BarChart3, FileText, Zap, Send,
  ShieldCheck, Activity, Workflow
} from "lucide-react";
import { FaXTwitter, FaYoutube, FaInstagram, FaTiktok, FaLinkedinIn } from "react-icons/fa6";
import { HiDocumentText } from "react-icons/hi2";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useTheme } from "@/components/ThemeProvider";
import { useAuth } from "@/contexts/AuthContext";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
} from "@/components/ui/dialog";
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem,
  DropdownMenuSeparator, DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { cn } from "@/lib/utils";
import { toast } from "sonner";
import api, { API } from "@/lib/api";

/* Brand icon wrappers (react-icons → Lucide-compatible className) */
const BrandIcon = ({ Icon, className = "" }) => (
  <Icon className={className} style={{ width: "1em", height: "1em" }} />
);
const XIcon = (props) => <BrandIcon Icon={FaXTwitter} {...props} />;
const YTIcon = (props) => <BrandIcon Icon={FaYoutube} {...props} />;
const IGIcon = (props) => <BrandIcon Icon={FaInstagram} {...props} />;
const TTIcon = (props) => <BrandIcon Icon={FaTiktok} {...props} />;
const LIIcon = (props) => <BrandIcon Icon={FaLinkedinIn} {...props} />;
const BlogIcon = (props) => <BrandIcon Icon={HiDocumentText} {...props} />;

const moduleItems = [
  { path: "/dashboard/create?platform=twitter", label: "X", icon: XIcon, color: "text-foreground" },
  { path: "/dashboard/create?platform=youtube", label: "YouTube", icon: YTIcon, color: "text-red-500" },
  { path: "/dashboard/create?platform=instagram", label: "Instagram", icon: IGIcon, color: "text-pink-500" },
  { path: "/dashboard/create?platform=tiktok", label: "TikTok", icon: TTIcon, color: "text-foreground" },
  { path: "/dashboard/create?platform=linkedin", label: "LinkedIn", icon: LIIcon, color: "text-[#0A66C2]" },
  { path: "/dashboard/create?platform=blog", label: "Blog", icon: BlogIcon, color: "text-orange-500" },
];

const toolItems = [
  { path: "/dashboard/auto-drafts", label: "Auto-Drafts", icon: Zap, color: "text-purple-400" },
  { path: "/dashboard/crew-flow", label: "Crew Akışı", icon: Workflow, color: "text-purple-400" },
  { path: "/dashboard/quality-audit", label: "Kalite Denetimi", icon: ShieldCheck, color: "text-emerald-400" },
  { path: "/dashboard/autonomy-score", label: "Otonomi Skoru", icon: BarChart3, color: "text-amber-400" },
  { path: "/dashboard/edit-elevations", label: "Düzenleme Önerileri", icon: Sparkles, color: "text-yellow-400" },
  { path: "/dashboard/system-health", label: "Sistem Sağlığı", icon: Activity, color: "text-rose-400" },
  { path: "/dashboard/social", label: "Sosyal Manager", icon: Send, color: "text-sky-400" },
  { path: "/dashboard/style-lab", label: "Style Lab", icon: Dna, color: "text-purple-400" },
  { path: "/dashboard/trends", label: "Trendler", icon: TrendingUp, color: "text-orange-500" },
  { path: "/dashboard/account-analysis", label: "Hesap Analizi", icon: BarChart3, color: "text-blue-400" },
  { path: "/dashboard/coach", label: "AI Coach", icon: Sparkles, color: "text-emerald-400" },
];

function MiniSparkline() {
  return (
    <svg width="80" height="24" viewBox="0 0 80 24" fill="none" className="text-purple-500">
      <polyline
        points="0,20 10,16 20,18 30,10 40,14 50,6 60,8 70,4 80,2"
        stroke="currentColor"
        strokeWidth="2"
        fill="none"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export default function DashboardLayout() {
  const { theme, setTheme } = useTheme();
  const { user, signOut, isAuthenticated } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [stats, setStats] = useState({ generations: 0, tweets: 0, favorites: 0 });

  useEffect(() => {
    const fetchStats = async () => {
      try {
        const response = await api.get(`${API}/user/stats`);
        if (response.data) setStats(response.data);
      } catch (error) { /* ignore */ }
    };
    if (isAuthenticated) fetchStats();
  }, [isAuthenticated, location.pathname]);

  const handleSignOut = async () => {
    try {
      await signOut();
      toast.success("Çıkış yapıldı");
      navigate("/");
    } catch (error) {
      toast.error("Çıkış yapılamadı");
    }
  };

  const isActive = (path) => {
    if (path === "/dashboard" && location.pathname === "/dashboard") return true;
    if (path !== "/dashboard") return location.pathname.includes(path.split('/').pop());
    return false;
  };

  // Animated counter for sidebar stats
  function useSidebarCounter(target, duration = 800) {
    const [val, setVal] = useState(0);
    useEffect(() => {
      if (!target) return;
      let start = 0;
      const step = target / (duration / 16);
      const timer = setInterval(() => {
        start += step;
        if (start >= target) { setVal(target); clearInterval(timer); }
        else setVal(Math.floor(start));
      }, 16);
      return () => clearInterval(timer);
    }, [target, duration]);
    return val;
  }

  const animatedGenerations = useSidebarCounter(stats.generations);

  const NavItem = ({ item, badge }) => {
    const active = isActive(item.path);
    const Icon = item.icon;
    return (
      <NavLink
        to={item.path}
        data-testid={`nav-${item.path.split('/').pop()}`}
        className={cn(
          "flex items-center gap-3 px-3 py-2.5 rounded-xl transition-all duration-300 group relative",
          "text-muted-foreground hover:text-foreground hover:bg-secondary/50 hover:translate-x-1",
          active && "bg-purple-500/10 text-purple-600 dark:text-purple-400 font-medium border-l-[3px] border-purple-500 ml-0 pl-[9px]"
        )}
      >
        <Icon className={cn("h-[18px] w-[18px] transition-colors duration-200", active ? "text-purple-500" : item.color)} />
        <span className="text-sm flex-1">{item.label}</span>
        {badge !== undefined && badge > 0 && (
          <Badge variant="secondary" className="h-5 min-w-[20px] px-1.5 text-[10px] font-semibold bg-purple-500/15 text-purple-600 dark:text-purple-400">
            {badge}
          </Badge>
        )}
      </NavLink>
    );
  };

  return (
    <div className="flex min-h-screen bg-[#F7F7F8] dark:bg-background">
      {/* Floating Sidebar */}
      <aside
        className="fixed left-0 top-0 z-40 h-screen w-[280px] p-3 pr-0 animate-fade-in"
        data-testid="sidebar"
      >
        <div className="h-full w-full bg-card rounded-3xl shadow-xl border border-border/50 flex flex-col overflow-hidden">
          {/* Gradient accent line */}
          <div className="h-[3px] w-full rounded-t-3xl bg-gradient-to-r from-purple-500 via-pink-500 to-indigo-500" />
          {/* User Profile */}
          {isAuthenticated && user ? (
            <div className="px-5 pt-5 pb-3">
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <button className="flex items-center gap-3 w-full p-2 rounded-xl hover:bg-secondary/50 transition-colors" data-testid="user-menu-trigger">
                    <Avatar className="h-11 w-11 ring-2 ring-purple-500/20">
                      <AvatarImage src={user.avatar_url} alt={user.name} />
                      <AvatarFallback className="bg-purple-500 text-white font-semibold">
                        {user.name?.charAt(0)?.toUpperCase() || 'U'}
                      </AvatarFallback>
                    </Avatar>
                    <div className="flex-1 text-left min-w-0">
                      <p className="text-sm font-semibold truncate">{user.name}</p>
                      <Badge variant="outline" className="text-[10px] px-1.5 py-0 h-4 font-medium border-purple-500/30 text-purple-600 dark:text-purple-400">
                        Free Plan
                      </Badge>
                    </div>
                    <ChevronDown className="h-4 w-4 text-muted-foreground shrink-0" />
                  </button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="start" className="w-56">
                  <DropdownMenuItem onClick={() => navigate('/dashboard/profile')}>
                    <User className="h-4 w-4 mr-2" /> Profil
                  </DropdownMenuItem>
                  <DropdownMenuItem onClick={() => setSettingsOpen(true)}>
                    <Settings className="h-4 w-4 mr-2" /> Ayarlar
                  </DropdownMenuItem>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem onClick={handleSignOut} className="text-red-500">
                    <LogOut className="h-4 w-4 mr-2" /> Çıkış Yap
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </div>
          ) : (
            <div className="px-5 pt-5 pb-3">
              <div className="flex items-center gap-3">
                <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-purple-500">
                  <Layers className="h-5 w-5 text-white" />
                </div>
                <span className="font-outfit text-lg font-bold">Type Hype</span>
              </div>
            </div>
          )}

          {/* Stats Card */}
          {isAuthenticated && (
            <div className="mx-4 mb-3 p-4 rounded-2xl bg-gradient-to-br from-purple-500/10 via-indigo-500/5 to-transparent border border-purple-500/10">
              <div className="flex items-end justify-between mb-2">
                <div>
                  <p className="text-[11px] text-muted-foreground font-medium uppercase tracking-wider">Toplam Üretim</p>
                  <p className="text-3xl font-outfit font-bold tracking-tight">{animatedGenerations.toLocaleString()}</p>
                </div>
                <MiniSparkline />
              </div>
              <div className="flex items-center gap-3 mb-3">
                <div className="flex items-center gap-1 text-xs text-muted-foreground">
                  <Heart className="h-3 w-3" />
                  <span>{stats.favorites} favori</span>
                </div>
              </div>
              <Button
                size="sm"
                className="w-full bg-purple-600 hover:bg-purple-700 text-white rounded-xl h-9 text-sm font-medium shimmer-btn"
                onClick={() => navigate('/dashboard/create?platform=twitter')}
              >
                <Sparkles className="h-4 w-4 mr-1.5" />
                Yeni İçerik Üret
              </Button>
            </div>
          )}

          {/* Navigation */}
          <nav className="flex-1 px-3 overflow-y-auto space-y-1 pb-2" data-testid="sidebar-nav">
            {/* Modules */}
            <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-widest px-3 pt-3 pb-1">Modüller</p>
            {moduleItems.map((item) => (
              <NavItem key={item.path} item={item} />
            ))}

            {/* Tools */}
            <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-widest px-3 pt-4 pb-1">Araçlar</p>
            {toolItems.map((item) => (
              <NavItem key={item.path} item={item} />
            ))}

            {/* Profile Section */}
            <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-widest px-3 pt-4 pb-1">Profilim</p>
            <NavItem
              item={{ path: "/dashboard/history", label: "Geçmiş", icon: History, color: "text-slate-400" }}
              badge={stats.generations}
            />
            <NavItem
              item={{ path: "/dashboard/favorites", label: "Favoriler", icon: Heart, color: "text-rose-400" }}
              badge={stats.favorites}
            />
          </nav>

          {/* Bottom: Theme Toggle + Settings */}
          <div className="p-4 border-t border-border/50 flex items-center justify-between">
            <button
              onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
              data-testid="theme-toggle"
              className="flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors"
            >
              {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
              <span className="text-xs">{theme === "dark" ? "Aydınlık" : "Karanlık"}</span>
            </button>
            <button
              onClick={() => setSettingsOpen(true)}
              data-testid="settings-btn"
              className="p-2 rounded-lg hover:bg-secondary/50 text-muted-foreground hover:text-foreground transition-colors"
            >
              <Settings className="h-4 w-4" />
            </button>
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 ml-[280px]">
        <div className="p-8">
          <Outlet />
        </div>
      </main>

      {/* Settings Dialog */}
      <Dialog open={settingsOpen} onOpenChange={setSettingsOpen}>
        <DialogContent className="sm:max-w-md" data-testid="settings-modal">
          <DialogHeader>
            <DialogTitle className="font-outfit">Ayarlar</DialogTitle>
            <DialogDescription>Uygulama ayarlarını yapılandırın</DialogDescription>
          </DialogHeader>
          <div className="space-y-6 py-4">
            <div className="space-y-2">
              <label className="text-sm font-medium">Tema</label>
              <div className="flex gap-2">
                <Button variant={theme === "dark" ? "default" : "outline"} size="sm" onClick={() => setTheme("dark")} data-testid="theme-dark-btn">
                  <Moon className="h-4 w-4 mr-2" /> Karanlık
                </Button>
                <Button variant={theme === "light" ? "default" : "outline"} size="sm" onClick={() => setTheme("light")} data-testid="theme-light-btn">
                  <Sun className="h-4 w-4 mr-2" /> Aydınlık
                </Button>
              </div>
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">API Durumu</label>
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <div className="h-2 w-2 rounded-full bg-green-500"></div>
                OpenAI Bağlı
              </div>
            </div>
            {user && (
              <div className="space-y-2">
                <label className="text-sm font-medium">Hesap</label>
                <div className="p-3 rounded-lg bg-secondary/50">
                  <p className="text-sm font-medium">{user.name}</p>
                  <p className="text-xs text-muted-foreground">{user.email}</p>
                </div>
              </div>
            )}
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
