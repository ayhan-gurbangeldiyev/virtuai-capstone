import { useState, useEffect } from "react";
import { Search } from "lucide-react";
import { fetchFeed } from "@/services/feedService";
import { formatNumber } from "@/lib/feedUtils";

export function RightSidebar() {
  const [popularItems, setPopularItems] = useState([]);

  useEffect(() => {
    fetchFeed({ limit: 5, sort: "popular" })
      .then((res) => setPopularItems(res.items || []))
      .catch(() => setPopularItems([]));
  }, []);

  return (
    <aside className="sticky top-0 hidden h-screen w-[350px] shrink-0 overflow-y-auto pl-7 pt-2 xl:block">
      <div className="mb-4 mt-1">
        <div className="relative">
          <Search
            size={16}
            className="absolute left-4 top-1/2 -translate-y-1/2 text-[#71767B]"
          />
          <input
            type="text"
            placeholder="Ara"
            className="h-[40px] w-full rounded-full bg-[#202327] pl-11 pr-4 text-[15px] text-[#E7E9EA] placeholder:text-[#71767B] outline-none border border-transparent focus:border-[#1D9BF0] focus:bg-black"
          />
        </div>
      </div>

      <div className="rounded-2xl bg-[#16181C]">
        <h2 className="px-4 pt-3 pb-3 text-xl font-extrabold text-[#E7E9EA]">
          Neler oluyor
        </h2>
        {popularItems.map((item, idx) => (
          <a
            key={item.id}
            href={item.tweet_url}
            target="_blank"
            rel="noopener noreferrer"
            className={`block px-4 py-3 transition-colors hover:bg-[rgba(231,233,234,0.08)] ${
              idx < popularItems.length - 1 ? "border-b border-[#2F3336]" : ""
            }`}
          >
            <p className="text-[13px] leading-4 text-[#71767B]">
              @{item.username}
            </p>
            <p className="mt-0.5 text-[15px] font-bold leading-5 text-[#E7E9EA] line-clamp-2">
              {(item.content || "").slice(0, 80)}
            </p>
            {item.likes > 0 && (
              <p className="mt-0.5 text-[13px] text-[#71767B]">
                {formatNumber(item.likes)} likes
              </p>
            )}
          </a>
        ))}
      </div>
    </aside>
  );
}
