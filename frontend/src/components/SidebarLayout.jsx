/**
 * @deprecated KULLANILMIYOR (2026-06-14) — hicbir yerden import edilmiyor; route/nav yok.
 * Referans icin tutuluyor; aktif uygulama akisinin parcasi DEGIL. Bkz: docs/DEPRECATED_MODULES.md
 */
import { useState } from "react";
import { Outlet, NavLink, useLocation } from "react-router-dom";
import { 
  Twitter, 
  Youtube, 
  Instagram, 
  Music2, 
  Linkedin, 
  FileText,
  Sun,
  Moon,
  Settings,
  Layers
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { useTheme } from "@/components/ThemeProvider";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { cn } from "@/lib/utils";

const navItems = [
  { 
    path: "/youtube", 
    label: "YouTubeAI", 
    icon: Youtube,
    color: "text-red-500",
    bgColor: "bg-red-500/10",
    borderColor: "border-red-500/30"
  },
  { 
    path: "/instaflow", 
    label: "InstaFlow AI", 
    icon: Instagram,
    color: "text-pink-500",
    bgColor: "bg-gradient-to-r from-purple-500/10 via-pink-500/10 to-orange-500/10",
    borderColor: "border-pink-500/30"
  },
  { 
    path: "/x-ai", 
    label: "X AI", 
    icon: Twitter,
    color: "text-sky-400",
    bgColor: "bg-sky-500/10",
    borderColor: "border-sky-500/30"
  },
  { 
    path: "/tiktrend", 
    label: "TikTrend AI", 
    icon: Music2,
    color: "text-cyan-400",
    bgColor: "bg-cyan-500/10",
    borderColor: "border-cyan-500/30"
  },
  { 
    path: "/linkshare", 
    label: "LinkShareAI", 
    icon: Linkedin,
    color: "text-blue-500",
    bgColor: "bg-blue-500/10",
    borderColor: "border-blue-500/30"
  },
  { 
    path: "/blog", 
    label: "Blog Architect", 
    icon: FileText,
    color: "text-orange-500",
    bgColor: "bg-orange-500/10",
    borderColor: "border-orange-500/30"
  },
];

export default function SidebarLayout() {
  const { theme, setTheme } = useTheme();
  const location = useLocation();
  const [settingsOpen, setSettingsOpen] = useState(false);

  const currentModule = navItems.find(item => location.pathname === item.path);

  return (
    <div className="flex min-h-screen">
      {/* Sidebar */}
      <aside 
        className="fixed left-0 top-0 z-40 h-screen w-[260px] border-r border-border bg-card"
        data-testid="sidebar"
      >
        <div className="flex h-full flex-col">
          {/* Logo */}
          <div className="flex items-center gap-3 px-6 py-6 border-b border-border">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-white">
              <Layers className="h-5 w-5 text-black" />
            </div>
            <span className="font-outfit text-xl font-bold tracking-tight">
              ContentFactory
            </span>
          </div>

          {/* Navigation */}
          <nav className="flex-1 space-y-1 p-4" data-testid="sidebar-nav">
            {navItems.map((item) => {
              const isActive = location.pathname === item.path;
              const Icon = item.icon;
              
              return (
                <NavLink
                  key={item.path}
                  to={item.path}
                  data-testid={`nav-${item.path.slice(1)}`}
                  className={cn(
                    "flex items-center gap-3 px-4 py-3 rounded-lg transition-all duration-200",
                    "text-muted-foreground hover:text-foreground",
                    isActive && [
                      item.bgColor,
                      item.color,
                      "font-medium",
                      "border",
                      item.borderColor
                    ]
                  )}
                >
                  <Icon className={cn("h-5 w-5", isActive && item.color)} />
                  <span>{item.label}</span>
                </NavLink>
              );
            })}
          </nav>

          {/* Footer */}
          <div className="border-t border-border p-4">
            <p className="text-xs text-muted-foreground text-center">
              © 2025 ContentFactory
            </p>
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 ml-[260px]">
        {/* Top Bar */}
        <header className="sticky top-0 z-30 flex items-center justify-end gap-3 border-b border-border bg-background/80 backdrop-blur-sm px-8 py-4">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setSettingsOpen(true)}
            data-testid="settings-btn"
            className="gap-2"
          >
            <Settings className="h-4 w-4" />
            Ayarlar
          </Button>
          
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
            data-testid="theme-toggle"
            className="h-9 w-9"
          >
            {theme === "dark" ? (
              <Sun className="h-5 w-5" />
            ) : (
              <Moon className="h-5 w-5" />
            )}
          </Button>
        </header>

        {/* Page Content */}
        <div className="p-8">
          <Outlet />
        </div>
      </main>

      {/* Settings Dialog */}
      <Dialog open={settingsOpen} onOpenChange={setSettingsOpen}>
        <DialogContent className="sm:max-w-md" data-testid="settings-modal">
          <DialogHeader>
            <DialogTitle className="font-outfit">Ayarlar</DialogTitle>
            <DialogDescription className="sr-only">
              Uygulama ayarlarını yapılandırın
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-6 py-4">
            <div className="space-y-2">
              <label className="text-sm font-medium">Tema</label>
              <div className="flex gap-2">
                <Button
                  variant={theme === "dark" ? "default" : "outline"}
                  size="sm"
                  onClick={() => setTheme("dark")}
                  data-testid="theme-dark-btn"
                >
                  <Moon className="h-4 w-4 mr-2" />
                  Karanlık
                </Button>
                <Button
                  variant={theme === "light" ? "default" : "outline"}
                  size="sm"
                  onClick={() => setTheme("light")}
                  data-testid="theme-light-btn"
                >
                  <Sun className="h-4 w-4 mr-2" />
                  Aydınlık
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
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
