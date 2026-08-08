import { formatRelativeDate } from "../../lib/utils";
import { ThreadListItem } from "./ThreadListItem";

function groupChats(chats) {
  const groups = new Map();
  for (const chat of chats) {
    const label = formatRelativeDate(chat.created_at) || "Earlier";
    if (!groups.has(label)) groups.set(label, []);
    groups.get(label).push(chat);
  }
  return groups;
}

export function ThreadList({ chats, activeChatId, onSelect, onRename, onDelete, emptyLabel }) {
  if (chats.length === 0) {
    return (
      <p className="px-2.5 py-6 text-center text-xs text-[var(--text-tertiary)]">{emptyLabel}</p>
    );
  }

  const groups = groupChats(chats);

  return (
    <div className="flex flex-col gap-4">
      {[...groups.entries()].map(([label, groupChats_]) => (
        <div key={label}>
          <p className="px-2.5 pb-1 text-xs font-medium text-[var(--text-tertiary)]">{label}</p>
          <div className="flex flex-col gap-0.5">
            {groupChats_.map((chat) => (
              <ThreadListItem
                key={chat.id}
                chat={chat}
                isActive={chat.id === activeChatId}
                onSelect={() => onSelect(chat.id)}
                onRename={(title) => onRename(chat.id, title)}
                onDelete={() => onDelete(chat.id)}
              />
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
