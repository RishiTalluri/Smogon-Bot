import { useRef, useState } from "react";
import { MoreHorizontal, Pencil, Trash2, Check, X } from "lucide-react";
import { cn } from "../../lib/utils";
import { useClickOutside } from "../../hooks/useClickOutside";

export function ThreadListItem({ chat, isActive, onSelect, onRename, onDelete }) {
  const [menuOpen, setMenuOpen] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [draftTitle, setDraftTitle] = useState(chat.title);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const menuRef = useRef(null);

  useClickOutside(menuRef, () => {
    setMenuOpen(false);
    setConfirmDelete(false);
  });

  const commitRename = () => {
    setIsEditing(false);
    if (draftTitle.trim() && draftTitle.trim() !== chat.title) {
      onRename(draftTitle);
    } else {
      setDraftTitle(chat.title);
    }
  };

  if (isEditing) {
    return (
      <div className="flex items-center gap-1 rounded-lg bg-[var(--bg-surface-hover)] px-2 py-1.5">
        <input
          autoFocus
          value={draftTitle}
          onChange={(e) => setDraftTitle(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") commitRename();
            if (e.key === "Escape") {
              setDraftTitle(chat.title);
              setIsEditing(false);
            }
          }}
          className="min-w-0 flex-1 bg-transparent text-sm text-[var(--text-primary)] focus:outline-none"
        />
        <button onClick={commitRename} className="text-[var(--text-secondary)] hover:text-[var(--text-primary)]">
          <Check size={14} />
        </button>
        <button
          onClick={() => {
            setDraftTitle(chat.title);
            setIsEditing(false);
          }}
          className="text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
        >
          <X size={14} />
        </button>
      </div>
    );
  }

  return (
    <div
      className={cn(
        "group relative flex cursor-pointer items-center rounded-lg px-2.5 py-2 text-sm transition-colors duration-100",
        isActive
          ? "bg-[var(--bg-surface-hover)] text-[var(--text-primary)]"
          : "text-[var(--text-secondary)] hover:bg-[var(--bg-surface-hover)] hover:text-[var(--text-primary)]"
      )}
      onClick={onSelect}
    >
      <span className="min-w-0 flex-1 truncate">{chat.title || "New Chat"}</span>

      <div className="relative shrink-0" ref={menuRef}>
        <button
          onClick={(e) => {
            e.stopPropagation();
            setMenuOpen((v) => !v);
          }}
          className={cn(
            "flex h-6 w-6 items-center justify-center rounded-md opacity-0 transition-opacity",
            "hover:bg-[var(--border-subtle)] group-hover:opacity-100",
            menuOpen && "opacity-100 bg-[var(--border-subtle)]"
          )}
        >
          <MoreHorizontal size={14} />
        </button>

        {menuOpen && (
          <div
            className="absolute right-0 top-full z-20 mt-1 w-36 overflow-hidden rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-surface)] py-1 shadow-[var(--shadow-popover)]"
            onClick={(e) => e.stopPropagation()}
          >
            <button
              onClick={() => {
                setIsEditing(true);
                setMenuOpen(false);
              }}
              className="flex w-full items-center gap-2 px-3 py-1.5 text-left text-sm text-[var(--text-primary)] hover:bg-[var(--bg-surface-hover)]"
            >
              <Pencil size={13} /> Rename
            </button>
            <button
              onClick={() => {
                if (!confirmDelete) {
                  setConfirmDelete(true);
                  return;
                }
                onDelete();
                setMenuOpen(false);
              }}
              className="flex w-full items-center gap-2 px-3 py-1.5 text-left text-sm text-red-500 hover:bg-[var(--bg-surface-hover)]"
            >
              <Trash2 size={13} /> {confirmDelete ? "Confirm delete?" : "Delete"}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
