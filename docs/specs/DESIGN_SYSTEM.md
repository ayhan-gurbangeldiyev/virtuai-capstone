# 🎨 ContentFactory — Design System

> **Bu dosya projenin TEK renk kaynağıdır.**  
> Herhangi bir renk değişikliği SADECE bu dosyadaki token'lar üzerinden yapılır.
> Hiçbir component'te hardcoded hex değeri kullanılmaz.

---

## Renk Tokenları (CSS Custom Properties)

Aşağıdaki tüm renkler `globals.css` içinde CSS custom property olarak tanımlanmalıdır.

### Light Mode (varsayılan)

```css
:root {
  /* ═══════════════════════════════════════════
     BACKGROUNDS
     ═══════════════════════════════════════════ */
  --bg-primary: #F5F5F0;           /* Sayfa ana arka planı — sıcak kırık beyaz */
  --bg-surface: #FFFFFF;           /* Kartlar, input'lar, yükseltilmiş yüzeyler */
  --bg-surface-hover: #FAFAF7;     /* Yüzey hover durumu */
  --bg-muted: #F0EFEB;             /* İkincil/sessiz arka planlar */
  --bg-elevated: #FFFFFF;          /* Modal, dropdown, popover */
  --bg-navbar: #1E1E1E;            /* Navbar arka planı — koyu */
  --bg-navbar-item: transparent;
  --bg-navbar-item-active: #3A3A3A;

  /* ═══════════════════════════════════════════
     TEXT
     ═══════════════════════════════════════════ */
  --text-primary: #1A1A1A;         /* Ana metin */
  --text-secondary: #6B6B6B;       /* İkincil/açıklama metni */
  --text-muted: #9CA3AF;           /* Placeholder, disabled metin */
  --text-inverse: #FFFFFF;         /* Koyu arka plan üzerindeki beyaz metin */
  --text-heading: #111111;         /* Başlıklar */

  /* ═══════════════════════════════════════════
     BORDERS
     ═══════════════════════════════════════════ */
  --border-default: #E5E5E0;       /* Varsayılan border */
  --border-subtle: #EDEDEA;        /* Hafif border (kartlar arası) */
  --border-strong: #D1D1CC;        /* Vurgulu border (input focus) */

  /* ═══════════════════════════════════════════
     BRAND / ACCENT
     ═══════════════════════════════════════════ */
  --color-accent: #8B5CF6;         /* Ana mor/purple accent */
  --color-accent-hover: #7C3AED;
  --color-accent-soft: rgba(139, 92, 246, 0.1);
  --color-success: #22C55E;
  --color-warning: #F59E0B;
  --color-error: #EF4444;

  /* ═══════════════════════════════════════════
     SHADOWS
     ═══════════════════════════════════════════ */
  --shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.04);
  --shadow-md: 0 2px 8px rgba(0, 0, 0, 0.06);
  --shadow-lg: 0 4px 16px rgba(0, 0, 0, 0.08);
  --shadow-card: 0 1px 3px rgba(0, 0, 0, 0.04), 0 4px 12px rgba(0, 0, 0, 0.03);
}
```

### Dark Mode

```css
[data-theme="dark"],
.dark {
  --bg-primary: #1A1A1A;
  --bg-surface: #242424;
  --bg-surface-hover: #2E2E2E;
  --bg-muted: #1F1F1F;
  --bg-elevated: #2A2A2A;
  --bg-navbar: #111111;
  --bg-navbar-item-active: #2A2A2A;

  --text-primary: #F5F5F5;
  --text-secondary: #A1A1A1;
  --text-muted: #666666;
  --text-inverse: #1A1A1A;
  --text-heading: #FFFFFF;

  --border-default: #333333;
  --border-subtle: #2A2A2A;
  --border-strong: #444444;

  --color-accent: #A78BFA;
  --color-accent-hover: #8B5CF6;
  --color-accent-soft: rgba(167, 139, 250, 0.15);

  --shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.2);
  --shadow-md: 0 2px 8px rgba(0, 0, 0, 0.3);
  --shadow-lg: 0 4px 16px rgba(0, 0, 0, 0.4);
  --shadow-card: 0 1px 3px rgba(0, 0, 0, 0.2), 0 4px 12px rgba(0, 0, 0, 0.15);
}
```

---

## Uygulama Kuralları

### ✅ Doğru Kullanım

```tsx
// Sayfa arka planı
<main className="min-h-screen" style={{ background: 'var(--bg-primary)' }}>

// Veya Tailwind config'te tanımlıysa:
<main className="min-h-screen bg-bg-primary">

// Kart
<div style={{ 
  background: 'var(--bg-surface)', 
  border: '1px solid var(--border-default)',
  boxShadow: 'var(--shadow-card)' 
}}>

// Input
<input style={{ 
  background: 'var(--bg-surface)',
  border: '1px solid var(--border-default)',
  color: 'var(--text-primary)' 
}} />

// Metin
<p style={{ color: 'var(--text-secondary)' }}>Açıklama metni</p>
```

### ❌ Yanlış Kullanım

```tsx
// YASAK — Tailwind varsayılan renkleri
<div className="bg-white">           // ❌
<div className="bg-gray-50">         // ❌
<div className="text-gray-500">      // ❌
<div className="border-gray-200">    // ❌

// YASAK — Hardcoded hex
<div style={{ background: '#F5F5F0' }}>     // ❌
<div style={{ background: '#FFFFFF' }}>     // ❌
<div style={{ color: '#1A1A1A' }}>          // ❌

// YASAK — Tailwind arbitrary hardcoded
<div className="bg-[#F5F5F0]">       // ❌
```

---

## globals.css Tam Şablon

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

:root {
  --bg-primary: #F5F5F0;
  --bg-surface: #FFFFFF;
  --bg-surface-hover: #FAFAF7;
  --bg-muted: #F0EFEB;
  --bg-elevated: #FFFFFF;
  --bg-navbar: #1E1E1E;
  --bg-navbar-item: transparent;
  --bg-navbar-item-active: #3A3A3A;
  
  --text-primary: #1A1A1A;
  --text-secondary: #6B6B6B;
  --text-muted: #9CA3AF;
  --text-inverse: #FFFFFF;
  --text-heading: #111111;
  
  --border-default: #E5E5E0;
  --border-subtle: #EDEDEA;
  --border-strong: #D1D1CC;
  
  --color-accent: #8B5CF6;
  --color-accent-hover: #7C3AED;
  --color-accent-soft: rgba(139, 92, 246, 0.1);
  
  --shadow-card: 0 1px 3px rgba(0,0,0,0.04), 0 4px 12px rgba(0,0,0,0.03);
}

.dark {
  --bg-primary: #1A1A1A;
  --bg-surface: #242424;
  --bg-surface-hover: #2E2E2E;
  --bg-muted: #1F1F1F;
  --bg-elevated: #2A2A2A;
  --bg-navbar: #111111;
  --bg-navbar-item-active: #2A2A2A;
  
  --text-primary: #F5F5F5;
  --text-secondary: #A1A1A1;
  --text-muted: #666666;
  --text-inverse: #1A1A1A;
  --text-heading: #FFFFFF;
  
  --border-default: #333333;
  --border-subtle: #2A2A2A;
  --border-strong: #444444;
  
  --color-accent: #A78BFA;
  --color-accent-hover: #8B5CF6;
  --color-accent-soft: rgba(167, 139, 250, 0.15);
  
  --shadow-card: 0 1px 3px rgba(0,0,0,0.2), 0 4px 12px rgba(0,0,0,0.15);
}

/* Ana arka plan — body seviyesinde */
html, body {
  background: var(--bg-primary);
  color: var(--text-primary);
}
```

---

## tailwind.config.js Şablon

```js
/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: 'class',
  content: ['./src/**/*.{js,ts,jsx,tsx}', './app/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        bg: {
          primary: 'var(--bg-primary)',
          surface: 'var(--bg-surface)',
          'surface-hover': 'var(--bg-surface-hover)',
          muted: 'var(--bg-muted)',
          elevated: 'var(--bg-elevated)',
        },
        text: {
          primary: 'var(--text-primary)',
          secondary: 'var(--text-secondary)',
          muted: 'var(--text-muted)',
        },
        border: {
          DEFAULT: 'var(--border-default)',
          subtle: 'var(--border-subtle)',
          strong: 'var(--border-strong)',
        },
        accent: {
          DEFAULT: 'var(--color-accent)',
          hover: 'var(--color-accent-hover)',
          soft: 'var(--color-accent-soft)',
        },
      },
      boxShadow: {
        card: 'var(--shadow-card)',
      },
    },
  },
  plugins: [],
};
```

Bu config ile Tailwind kullanımı:
```tsx
<div className="bg-bg-primary text-text-primary">
<div className="bg-bg-surface border-border shadow-card">
<span className="text-text-secondary">
<button className="bg-accent hover:bg-accent-hover">
```

---

## Renk Değiştirme Prosedürü

Eğer arka plan rengini değiştirmek istiyorsan:

1. `globals.css` aç
2. `--bg-primary` değerini değiştir (örn: `#F5F5F0` → `#FAFAF5`)
3. Kaydet. Bitti. Tüm sayfa otomatik güncellenir.

**ASLA** tek tek component'lere gidip renk ekleme/değiştirme.

---

## Sorun Giderme

### "Arka plan iki farklı renk görünüyor"
→ `grep -rn "bg-white\|#FFFFFF\|#fff" --include="*.tsx"` çalıştır ve bulunan yerleri `var(--bg-primary)` veya `var(--bg-surface)` ile değiştir.

### "Renk değiştirdim ama bir yerde eski kaldı"  
→ O component inline style veya hardcoded Tailwind class kullanıyor. Bul ve CSS variable'a çevir.

### "Dark mode'da renkler bozuk"
→ `.dark` selector'ı altında tüm `--` variable'lar tanımlanmış mı kontrol et.
