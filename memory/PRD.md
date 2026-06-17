# ContentFactory PRD

## Original Problem Statement
Create a complete content generation platform called "ContentFactory" with a modern, sleek design similar to ContentOS. Turkish language UI with:
- Left sidebar navigation (6 modules)
- X AI module fully functional (Tweet, Quote, Reply, Article tabs)
- Other modules as placeholders
- Dark/Light mode support
- OpenAI integration for content generation
- Supabase Authentication
- Hybrid layout: Landing page + Dashboard
- Tweetle button (direct Twitter posting)
- Favorites and History system

## User Personas
- Content creators
- Social media managers
- Digital marketers
- Influencers needing AI-powered content

## Core Requirements (Static)
- Turkish language UI
- Dark mode default
- Module-specific color themes
- OpenAI GPT integration
- Supabase Authentication (to be configured)
- Favorites system
- Generation history

## What's Been Implemented (Jan 27, 2025)

### Authentication & Pages
- ✅ Landing page with hero, features, stats sections
- ✅ Login page with email/password, Google OAuth, Dev mode
- ✅ Signup page with registration form
- ✅ Supabase Auth integration (ready for user's credentials)
- ✅ Protected routes with dev mode fallback

### Frontend Dashboard
- ✅ DashboardLayout with sidebar navigation
- ✅ User profile display in sidebar
- ✅ Generation stats display (X üretim · Y favoriler)
- ✅ X AI Module (fully functional):
  - Tweet tab: Klasik/APEX modes, length selector, variant counter, persona/tone/language chips
  - Quote tab: URL input, tweet preview, generation
  - Reply tab: URL input, reply modes (Support/Challenge/Question/Expand/Joke)
  - Article tab: Title, topic, length, style, reference links
- ✅ "Tweetle" button - direct Twitter posting
- ✅ Favorites button with heart icon
- ✅ Copy button for each generated content
- ✅ YouTubeAI placeholder page
- ✅ InstaFlow AI placeholder page
- ✅ TikTrend AI placeholder page
- ✅ LinkShareAI placeholder page
- ✅ Blog Architect placeholder page
- ✅ History page with generation list
- ✅ Favorites page
- ✅ Settings modal
- ✅ Dark/Light theme toggle

### Backend
- ✅ FastAPI server with /api prefix
- ✅ POST /api/generate/tweet
- ✅ POST /api/generate/quote
- ✅ POST /api/generate/reply
- ✅ POST /api/generate/article
- ✅ GET /api/generations/history
- ✅ GET /api/user/stats
- ✅ GET /api/favorites
- ✅ POST /api/favorites
- ✅ DELETE /api/favorites/{id}
- ✅ GET /api/health
- ✅ Supabase integration

## Configuration Required by User

### Supabase Auth
Add to `/app/frontend/.env`:
```
REACT_APP_SUPABASE_URL=https://xxxxx.supabase.co
REACT_APP_SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIs...
```

### OpenAI API Key
Add to `/app/backend/.env`:
```
OPENAI_API_KEY=sk-...
```
Then restart backend: `sudo supervisorctl restart backend`

## Prioritized Backlog

### P0 (User Action Required)
- [ ] User adds OPENAI_API_KEY to /app/backend/.env
- [ ] User configures Supabase credentials

### P1 (Next Phase)
- [ ] YouTubeAI module full implementation
- [ ] InstaFlow AI module full implementation
- [ ] TikTrend AI module full implementation
- [ ] LinkShareAI module full implementation
- [ ] Blog Architect module full implementation

### P2 (Future)
- [ ] User-scoped favorites (per user)
- [ ] User-scoped history (per user)
- [ ] Export/download generated content
- [ ] Scheduled posts feature
- [ ] Team collaboration

## Tech Stack
- Frontend: React, Tailwind CSS, shadcn/ui
- Backend: FastAPI, Supabase
- Auth: Supabase (ready for configuration)
- AI: OpenAI GPT-4o

## Next Tasks
1. User adds API keys (OpenAI, Supabase)
2. Test full content generation flow
3. Implement YouTubeAI module
4. Implement remaining modules one by one
