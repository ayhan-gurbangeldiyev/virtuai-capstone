import { useState } from "react";
import { formatRelativeTime, formatNumber } from "@/lib/feedUtils";
import { Heart, MessageCircle, Repeat2, BarChart2, Share, Bookmark, MoreHorizontal, Play, BadgeCheck, Zap } from "lucide-react";

function Avatar({ item }) {
  const [imgError, setImgError] = useState(false);
  const letter = (item.display_name || item.username || "?").charAt(0).toUpperCase();
  const hue = (item.username.charCodeAt(0) * 37) % 360;

  if (item.avatar_url && !imgError) {
    return (
      <img
        src={item.avatar_url}
        alt=""
        className="h-10 w-10 shrink-0 rounded-full object-cover"
        onError={() => setImgError(true)}
      />
    );
  }
  return (
    <div
      className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-sm font-bold text-white"
      style={{ backgroundColor: `hsl(${hue}, 60%, 50%)` }}
    >
      {letter}
    </div>
  );
}

function EngagementButton({ type, value, alwaysShow = false }) {
  const [hovered, setHovered] = useState(false);
  if (!alwaysShow && value === 0) return null;

  const configs = {
    reply: { icon: MessageCircle, color: "#1D9BF0" },
    retweet: { icon: Repeat2, color: "#00BA7C" },
    like: { icon: Heart, color: "#F91880" },
    views: { icon: BarChart2, color: "#1D9BF0" },
    bookmark: { icon: Bookmark, color: "#1D9BF0" },
  };
  const { icon: Icon, color } = configs[type];

  return (
    <button
      className="group flex items-center gap-1 rounded-full p-2 text-[#71767B] transition-colors"
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        color: hovered ? color : undefined,
        backgroundColor: hovered ? `${color}1a` : undefined,
        opacity: value === 0 ? 0.5 : 1,
      }}
    >
      <Icon className="h-[18px] w-[18px]" strokeWidth={1.5} />
      {value > 0 && <span className="text-[13px]">{formatNumber(value)}</span>}
    </button>
  );
}

function SmallIconButton({ icon: Icon, hoverColor, onClick }) {
  const [hovered, setHovered] = useState(false);
  return (
    <button
      className="rounded-full p-2 text-[#71767B] transition-colors"
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        color: hovered ? hoverColor : undefined,
        backgroundColor: hovered ? `${hoverColor}1a` : undefined,
      }}
      onClick={(e) => {
        e.stopPropagation();
        onClick?.();
      }}
    >
      <Icon className="h-[18px] w-[18px]" strokeWidth={1.5} />
    </button>
  );
}

function MediaGallery({ media }) {
  if (!media || media.length === 0) return null;

  const photos = media.filter((m) => m.type === "photo");
  const videos = media.filter((m) => m.type === "video" || m.type === "animated_gif");

  if (photos.length === 0 && videos.length === 0) return null;

  return (
    <div className="mt-3 overflow-hidden rounded-2xl border border-border" onClick={(e) => e.stopPropagation()}>
      {videos.length > 0 ? (
        <div className="relative">
          <img
            src={videos[0].preview_url || videos[0].url}
            alt=""
            className="w-full max-h-[512px] object-cover"
            loading="lazy"
          />
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="rounded-full bg-black/60 p-3">
              <Play className="h-6 w-6 text-white fill-white" />
            </div>
          </div>
        </div>
      ) : photos.length === 1 ? (
        <img
          src={photos[0].url}
          alt=""
          className="w-full max-h-[512px] object-cover"
          loading="lazy"
        />
      ) : (
        <div className={`grid gap-0.5 ${photos.length === 2 ? "grid-cols-2" : "grid-cols-2"}`}>
          {photos.slice(0, 4).map((p, i) => (
            <img
              key={i}
              src={p.url}
              alt=""
              className="w-full h-[200px] object-cover"
              loading="lazy"
            />
          ))}
        </div>
      )}
    </div>
  );
}

export function TweetCard({ item, onGenerate }) {
  const [expanded, setExpanded] = useState(false);
  const truncated = item.content.length > 280 && !expanded;

  return (
    <>
    <style>{`
      @property --ultra-angle {
        syntax: '<angle>';
        initial-value: 0deg;
        inherits: false;
      }
      @keyframes ultra-rotate {
        from { --ultra-angle: 0deg; }
        to   { --ultra-angle: 360deg; }
      }
      .zap-rainbow {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 20px;
        height: 20px;
        background: conic-gradient(
          from var(--ultra-angle, 0deg),
          #a855f7, #3b82f6, #06b6d4, #ec4899, #ef4444, #f97316, #a855f7
        );
        animation: ultra-rotate 4s linear infinite;
        -webkit-mask-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='18' height='18' viewBox='0 0 24 24' fill='rgba(0,0,0,0.3)' stroke='black' stroke-width='1.5' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M4 14a1 1 0 0 1-.78-1.63l9.9-10.2a.5.5 0 0 1 .86.46l-1.92 6.02A1 1 0 0 0 13 10h7a1 1 0 0 1 .78 1.63l-9.9 10.2a.5.5 0 0 1-.86-.46l1.92-6.02A1 1 0 0 0 11 14z'/%3E%3C/svg%3E");
        -webkit-mask-size: contain;
        -webkit-mask-repeat: no-repeat;
        mask-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='18' height='18' viewBox='0 0 24 24' fill='rgba(0,0,0,0.3)' stroke='black' stroke-width='1.5' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M4 14a1 1 0 0 1-.78-1.63l9.9-10.2a.5.5 0 0 1 .86.46l-1.92 6.02A1 1 0 0 0 13 10h7a1 1 0 0 1 .78 1.63l-9.9 10.2a.5.5 0 0 1-.86-.46l1.92-6.02A1 1 0 0 0 11 14z'/%3E%3C/svg%3E");
        mask-size: contain;
        mask-repeat: no-repeat;
      }
    `}</style>
    <article
      className="group flex gap-3 border-b border-border px-4 py-3 transition-colors hover:bg-white/[0.03] cursor-pointer"
      onClick={() => window.open(item.tweet_url, "_blank")}
    >
      <Avatar item={item} />
      <div className="min-w-0 flex-1">
        <div className="flex items-start justify-between">
          <div className="flex min-w-0 items-center gap-1 text-[15px] leading-5">
            <span className="truncate font-bold text-foreground">{item.display_name}</span>
            {item.verified && (
              <BadgeCheck className="h-[18px] w-[18px] shrink-0 text-[#1D9BF0] fill-[#1D9BF0] stroke-white" strokeWidth={2} />
            )}
            <span className="truncate text-[#71767B]">@{item.username}</span>
            <span className="text-[#71767B]">·</span>
            <time className="shrink-0 text-[#71767B] hover:underline">
              {formatRelativeTime(item.tweet_created_at)}
            </time>
          </div>
          <button
            className="ml-1 -mt-1 flex h-[34px] w-[34px] shrink-0 items-center justify-center rounded-full text-[#71767B] transition-colors hover:bg-[#1D9BF01a] hover:text-[#1D9BF0] opacity-0 group-hover:opacity-100"
            onClick={(e) => e.stopPropagation()}
          >
            <MoreHorizontal className="h-[18px] w-[18px]" strokeWidth={1.5} />
          </button>
        </div>

        <div className="mt-0.5 text-[15px] leading-5 text-foreground whitespace-pre-wrap">
          {truncated ? item.content.slice(0, 280) + "..." : item.content}
          {truncated && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                setExpanded(true);
              }}
              className="ml-1 text-[hsl(var(--primary))] hover:underline"
            >
              devamını gör
            </button>
          )}
        </div>

        <MediaGallery media={item.media} />

        <div className="-ml-2 mt-1 flex items-center justify-between">
          <EngagementButton type="reply" value={item.replies} alwaysShow />
          <EngagementButton type="retweet" value={item.retweets} alwaysShow />
          <EngagementButton type="like" value={item.likes} alwaysShow />
          <EngagementButton type="views" value={item.views} alwaysShow />
          <EngagementButton type="bookmark" value={item.bookmarks || 0} />
          <button
            className="rounded-full p-2 transition-all hover:scale-110 hover:bg-purple-500/10 active:scale-95"
            onClick={(e) => {
              e.stopPropagation();
              onGenerate?.(item);
            }}
          >
            <div className="zap-rainbow" />
          </button>
          <SmallIconButton
            icon={Share}
            hoverColor="#1D9BF0"
            onClick={() => window.open(item.tweet_url, "_blank")}
          />
        </div>
      </div>
    </article>
    </>
  );
}
