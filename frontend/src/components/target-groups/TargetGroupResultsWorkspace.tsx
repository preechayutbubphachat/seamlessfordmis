"use client";

import { useEffect, useMemo, useRef, useState, useTransition } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";

import { JobProgressCard } from "@/components/common/JobProgressCard";
import { LoadingState } from "@/components/common/LoadingState";
import {
  addFilesToGroup,
  ApiError,
  confirmImport,
  exportGroupResults,
  generateResults,
  getGroupResults,
  getTargetGroup,
  runMatch,
  updateGroupName,
} from "@/lib/api";
import { formatDate, formatNumber } from "@/lib/format";
import type { GroupResultRow, GroupResultsResponse } from "@/types/result";
import type {
  ConfirmImportResponse,
  DiseaseOption,
  RunMatchResponse,
  TargetGroupDetail,
  TargetGroupImportSummary,
} from "@/types/target-group";
import { DiseaseFilter } from "./DiseaseFilter";
import { FileManagementPanel } from "./FileManagementPanel";
import { getTargetGroupFileKey, getValidationIssueKey } from "./keys";
import { PatientDetailModal } from "./PatientDetailModal";
import { ResultsTable } from "./ResultsTable";
import { TargetGroupPreviewTable } from "./TargetGroupPreviewTable";

// ─────────────────────────────────────────────────────────
// Constants
// ─────────────────────────────────────────────────────────

const STEP_LABELS = [
  "ตั้งชื่อกลุ่ม",
  "อัปโหลดไฟล์",
  "ตรวจสอบข้อมูล",
  "เลือกรายการคัดกรอง",
  "ดูผลลัพธ์",
];

const EMPTY_IMPORT_SUMMARY: TargetGroupImportSummary = {
  total_uploaded_files: 0,
  total_rows: 0,
  parsed_rows: 0,
  valid_cid_rows: 0,
  invalid_cid_rows: 0,
  missing_cid_rows: 0,
  duplicate_cid_rows: 0,
  warning_rows: 0,
  failed_rows: 0,
};

const VIEW_FILTERS = [
  { key: "all", label: "ทั้งหมด" },
  { key: "checked_but_overdue", label: "ตรวจแล้วแต่เกินกำหนด" },
  { key: "checked_and_within_threshold", label: "ตรวจแล้วและยังไม่เกินกำหนด" },
  { key: "never_checked", label: "ยังไม่เคยตรวจ" },
  { key: "invalid_identifier", label: "ตัวระบุไม่ถูกต้อง" },
  { key: "missing_identifier", label: "ไม่มีข้อมูลตัวระบุ" },
  { key: "review_required_identity", label: "ต้องตรวจสอบข้อมูลระบุตัวตน" },
  { key: "review_required", label: "รอยืนยันตัวตน" },
  { key: "insufficient_identity_data", label: "ข้อมูลระบุตัวตนไม่พอ" },
  { key: "non_thai_nationality", label: "ไม่ใช่คนไทย" },
  { key: "outside_target_scope", label: "นอกขอบเขตกลุ่มเป้าหมาย" },
  { key: "needs_review", label: "ต้องตรวจสอบ" },
] as const;

const OVERDUE_PRESETS = [1, 3, 5];
const DEFAULT_PAGE_SIZE = 100;
const PAGE_SIZE_OPTIONS = [10, 25, 50, 100, 250];
const MAX_SAFE_SHOW_ALL_ROWS = 1000;
const SEARCH_DEBOUNCE_MS = 350;

// localStorage filter persist keys — all values stored are strings
const FILTER_PERSIST_KEYS = [
  "services", "view", "overdue_enabled", "overdue_input",
  "page_size", "q", "sort_col", "sort_dir", "hidden_cols",
] as const;

type FilterPersistKey = (typeof FILTER_PERSIST_KEYS)[number];

// ─────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────

type ViewFilterKey = (typeof VIEW_FILTERS)[number]["key"];

type OperationBannerState = {
  title: string;
  status: "processing" | "success" | "failed";
  message: string;
  currentStage?: string | null;
  processedRows?: number | null;
  totalRows?: number | null;
} | null;

// ─────────────────────────────────────────────────────────
// localStorage helpers (keyed per groupId — never shared across groups)
// ─────────────────────────────────────────────────────────

/** Active filter state: restored on every page load. */
function makeStorageKey(groupId: string) {
  return `targetGroupResultFilters:${groupId}`;
}

/** Last manually-saved view snapshot: restored only via "กลับไปค่าล่าสุด" button. */
function makeLastSavedKey(groupId: string) {
  return `targetGroupResultFilters:${groupId}:lastSaved`;
}

function _writeStorage(key: string, params: Record<string, string | null>) {
  try {
    const toSave: Record<string, string> = {};
    for (const k of FILTER_PERSIST_KEYS) {
      const v = params[k as FilterPersistKey];
      if (v !== null && v !== undefined && v !== "") toSave[k] = v;
    }
    localStorage.setItem(key, JSON.stringify(toSave));
  } catch {
    // storage may be unavailable (private browsing, quota exceeded, etc.)
  }
}

function _readStorage(key: string): Record<string, string> {
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return {};
    const parsed = JSON.parse(raw) as unknown;
    if (typeof parsed !== "object" || parsed === null || Array.isArray(parsed)) return {};
    const result: Record<string, string> = {};
    for (const k of FILTER_PERSIST_KEYS) {
      const v = (parsed as Record<string, unknown>)[k];
      if (typeof v === "string") result[k] = v;
    }
    return result;
  } catch {
    return {};
  }
}

function saveFiltersToStorage(groupId: string, params: Record<string, string | null>) {
  _writeStorage(makeStorageKey(groupId), params);
}

function loadFiltersFromStorage(groupId: string): Record<string, string> {
  return _readStorage(makeStorageKey(groupId));
}

function saveLastViewToStorage(groupId: string, params: Record<string, string | null>) {
  _writeStorage(makeLastSavedKey(groupId), params);
}

function loadLastViewFromStorage(groupId: string): Record<string, string> {
  return _readStorage(makeLastSavedKey(groupId));
}

function hasLastSavedView(groupId: string): boolean {
  try { return localStorage.getItem(makeLastSavedKey(groupId)) !== null; } catch { return false; }
}

function clearStorageKey(groupId: string) {
  try {
    localStorage.removeItem(makeStorageKey(groupId));
    // Keep lastSaved intentionally — "กลับไปค่าล่าสุด" must survive a clearFilters()
  } catch { /* ignore */ }
}

// ─────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────

function sameSelection(left: string[], right: string[]) {
  return [...left].sort().join("|") === [...right].sort().join("|");
}

function readPositiveInteger(value: string | null, fallback: number) {
  if (!value) return fallback;
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed >= 1 ? Math.floor(parsed) : fallback;
}

// ─────────────────────────────────────────────────────────
// Sub-components
// ─────────────────────────────────────────────────────────

function WorkspaceStepper({
  activeStep,
  onStepClick,
}: {
  activeStep: number;
  onStepClick?: (stepIndex: number) => void;
}) {
  return (
    <nav className="hstepper" aria-label="ขั้นตอนการสร้างกลุ่มเป้าหมาย">
      {STEP_LABELS.map((label, index) => {
        const isDone = index < activeStep;
        const isActive = index === activeStep;
        const cls = [
          "hstepper-item",
          isDone ? "hstepper-item--done" : "",
          isActive ? "hstepper-item--active" : "",
        ].filter(Boolean).join(" ");
        return (
          <div
            key={label}
            className={cls + (onStepClick ? " hstepper-item--clickable" : "")}
            role={onStepClick ? "button" : undefined}
            tabIndex={onStepClick ? 0 : undefined}
            onClick={onStepClick ? () => onStepClick(index) : undefined}
            onKeyDown={onStepClick ? (e) => { if (e.key === "Enter" || e.key === " ") onStepClick(index); } : undefined}
          >
            <div className="hstepper-dot" aria-hidden="true">
              {isDone ? "✓" : String(index + 1)}
            </div>
            <span className="hstepper-label">{label}</span>
            {index < STEP_LABELS.length - 1 && (
              <div className="hstepper-connector" aria-hidden="true" />
            )}
          </div>
        );
      })}
    </nav>
  );
}

function GroupNameEditor({
  name,
  onSave,
}: {
  name: string;
  onSave: (newName: string) => Promise<void>;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(name);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  function handleEdit() {
    setDraft(name);
    setSaveError(null);
    setEditing(true);
  }

  async function handleSave() {
    if (!draft.trim() || draft.trim() === name) { setEditing(false); return; }
    setSaving(true);
    setSaveError(null);
    try {
      await onSave(draft.trim());
      setEditing(false);
    } catch (err) {
      setSaveError(err instanceof ApiError ? err.detail : "บันทึกชื่อไม่สำเร็จ");
    } finally {
      setSaving(false);
    }
  }

  if (!editing) {
    return (
      <div className="name-editor-row">
        <h2 className="workspace-group-name">{name}</h2>
        <button type="button" className="ghost-button compact-button" onClick={handleEdit}>
          {"แก้ไขชื่อ"}
        </button>
      </div>
    );
  }

  return (
    <div className="name-editor-col">
      <div className="name-editor-row">
        <input
          className="name-editor-input"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") void handleSave();
            if (e.key === "Escape") setEditing(false);
          }}
          autoFocus
          disabled={saving}
          maxLength={200}
          aria-label="ชื่อกลุ่มเป้าหมาย"
        />
        <button
          type="button"
          className="primary-button compact-button"
          disabled={saving || !draft.trim()}
          onClick={() => void handleSave()}
        >
          {saving ? "กำลังบันทึก..." : "บันทึก"}
        </button>
        <button
          type="button"
          className="secondary-button compact-button"
          disabled={saving}
          onClick={() => setEditing(false)}
        >
          {"ยกเลิก"}
        </button>
      </div>
      {saveError ? <p className="feedback-line is-error">{saveError}</p> : null}
    </div>
  );
}

function SummaryCard({
  title,
  value,
  note,
  tone = "default",
}: {
  title: string;
  value: string | number;
  note?: string;
  tone?: "default" | "ready" | "warning" | "muted" | "accent";
}) {
  return (
    <article className={"summary-card " + tone}>
      <p className="summary-card-label">{title}</p>
      <p className="summary-card-value">{value}</p>
      {note ? <p className="summary-card-note">{note}</p> : null}
    </article>
  );
}

function ConfigDirtyBanner({
  selectedLabels,
  onRegenerate,
  isPending,
}: {
  selectedLabels: string[];
  onRegenerate: () => void;
  isPending: boolean;
}) {
  return (
    <div className="config-dirty-banner" role="alert">
      <div className="config-dirty-content">
        <span className="config-dirty-icon" aria-hidden="true">{"⚠"}</span>
        <div>
          <p className="config-dirty-title">{"ผลลัพธ์ที่แสดงอยู่ไม่ตรงกับรายการที่เลือกปัจจุบัน"}</p>
          <p className="config-dirty-note">
            {"รายการปัจจุบัน: " + (selectedLabels.join(", ") || "ยังไม่ได้เลือก")}
          </p>
        </div>
      </div>
      <button
        type="button"
        className="primary-button compact-button"
        disabled={isPending}
        onClick={onRegenerate}
      >
        {isPending ? "กำลังสร้างผลลัพธ์ใหม่..." : "สร้างผลลัพธ์ใหม่"}
      </button>
    </div>
  );
}

function SourceFileStaleBanner({
  onRegenerate,
  isPending,
  title = "มีการเพิ่ม/เปลี่ยนไฟล์ข้อมูลต้นทาง",
  note = "ผลลัพธ์ปัจจุบันยังไม่ได้คำนวณจากข้อมูลล่าสุด กรุณาสร้างผลลัพธ์ใหม่",
}: {
  onRegenerate: () => void;
  isPending: boolean;
  title?: string;
  note?: string;
}) {
  return (
    <div className="source-stale-banner" role="alert">
      <div className="source-stale-content">
        <span className="source-stale-icon" aria-hidden="true">{"📂"}</span>
        <div>
          <p className="source-stale-title">{title}</p>
          <p className="source-stale-note">{note}</p>
        </div>
      </div>
      <button
        type="button"
        className="primary-button compact-button"
        disabled={isPending}
        onClick={onRegenerate}
      >
        {isPending ? "กำลังสร้างผลลัพธ์ใหม่..." : "สร้างผลลัพธ์ใหม่จากข้อมูลล่าสุด"}
      </button>
    </div>
  );
}

// ─────────────────────────────────────────────────────────
// Main component
// ─────────────────────────────────────────────────────────

export function TargetGroupResultsWorkspace({
  groupId,
  initialGroup,
  diseaseOptions,
  initialResults,
}: {
  groupId: string;
  initialGroup: TargetGroupDetail;
  diseaseOptions: DiseaseOption[];
  initialResults: GroupResultsResponse | null;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const [group, setGroup] = useState<TargetGroupDetail>(initialGroup);
  const [results, setResults] = useState<GroupResultsResponse | null>(initialResults);
  const [confirmState, setConfirmState] = useState<ConfirmImportResponse | null>(null);
  const [matchState, setMatchState] = useState<RunMatchResponse | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [resultsLoading, setResultsLoading] = useState<boolean>(!initialResults);
  const [operationBanner, setOperationBanner] = useState<OperationBannerState>(null);
  const [showFilePanel, setShowFilePanel] = useState(false);
  const [selectedRow, setSelectedRow] = useState<GroupResultRow | null>(null);
  const [searchInput, setSearchInput] = useState(searchParams.get("q") ?? "");
  const [viewSaved, setViewSaved] = useState(false);
  const [showExportPreview, setShowExportPreview] = useState(false);
  const viewSavedTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const storageRestoredRef = useRef(false);
  // Guards the one-time restore of the generated service selection into the URL
  // when a group is (re)opened without an explicit ?services= param.
  const selectionRestoredRef = useRef(false);
  const [isPending, startTransition] = useTransition();

  // URL-derived filter state
  const defaultKeys = useMemo(() => diseaseOptions.slice(0, 1).map((item) => item.key), [diseaseOptions]);
  const selectedKeys = useMemo(() => {
    const raw = searchParams.get("services");
    const parsed = raw ? raw.split(",").filter(Boolean) : [];
    return parsed.length ? parsed : defaultKeys;
  }, [defaultKeys, searchParams]);

  const activeFilter = (searchParams.get("view") as ViewFilterKey | null) ?? "all";
  const overdueEnabled = searchParams.get("overdue_enabled") === "1";
  const overdueInput = searchParams.get("overdue_input") ?? "1";
  const searchQuery = searchParams.get("q") ?? "";
  const page = readPositiveInteger(searchParams.get("page"), 1);
  const pageSize = readPositiveInteger(searchParams.get("page_size"), DEFAULT_PAGE_SIZE);
  const showAll = searchParams.get("show_all") === "1";
  const overdueYears = readPositiveInteger(overdueInput, 1);

  // Sort state from URL
  const sortCol = searchParams.get("sort_col") ?? null;
  const sortDir = (searchParams.get("sort_dir") as "asc" | "desc" | null) ?? null;

  // Hidden columns: comma-separated list stored in URL and localStorage
  const hiddenColsRaw = searchParams.get("hidden_cols") ?? "";
  const hiddenCols = useMemo(
    () => new Set(hiddenColsRaw ? hiddenColsRaw.split(",").filter(Boolean) : []),
    [hiddenColsRaw],
  );

  // Whether a "กลับไปค่าล่าสุด" snapshot exists in storage
  const [hasLastSaved, setHasLastSaved] = useState(() => hasLastSavedView(groupId));
  const importSummary = group.import_summary ?? EMPTY_IMPORT_SUMMARY;

  // Dirty/stale
  const isDirty = useMemo(() => {
    if (!results?.summary.selected_service_keys?.length) return false;
    return !sameSelection(selectedKeys, results.summary.selected_service_keys);
  }, [results, selectedKeys]);

  const isSourceStale = useMemo(() => {
    if (!results?.summary) return false;
    const genHash = results.summary.generated_source_set_hash;
    if (!genHash) return false;
    const currentHash = group.source_set_hash ?? group.source_file_hash;
    return genHash !== currentHash;
  }, [results, group]);

  // Backend flags a cached result generated with an older classification /
  // normalization logic version (source files may be unchanged) → prompt the
  // user to regenerate so the displayed result reflects current rules.
  const requiresRegeneration = Boolean(results?.summary?.requires_regeneration);

  const hasResults = Boolean(results?.summary);
  const activeStep = hasResults && !isDirty ? 4 : 3;

  // ── URL state helpers ──────────────────────────────────
  function buildParams(next: Record<string, string | null>) {
    const params = new URLSearchParams(searchParams.toString());
    Object.entries(next).forEach(([key, value]) => {
      if (!value) { params.delete(key); } else { params.set(key, value); }
    });
    return params;
  }

  function setQueryState(next: Record<string, string | null>) {
    const params = buildParams(next);
    const queryString = params.toString();
    router.replace(queryString ? pathname + "?" + queryString : pathname, { scroll: false });
  }

  function updateFilters(next: Record<string, string | null>, resetPage = false) {
    const merged: Record<string, string | null> = {
      services: selectedKeys.join(","),
      view: activeFilter,
      overdue_enabled: overdueEnabled ? "1" : null,
      overdue_input: overdueInput,
      q: searchQuery || null,
      page_size: String(pageSize),
      show_all: showAll ? "1" : null,
      page: resetPage ? "1" : String(page),
      sort_col: sortCol,
      sort_dir: sortDir,
      hidden_cols: hiddenColsRaw || null,
      ...next,
    };
    setQueryState(merged);
    // Persist filter state to localStorage (keyed per group, never across groups)
    saveFiltersToStorage(groupId, merged);
  }

  /** Toggle sort: clicking the same column flips direction; clicking a new column defaults to asc. */
  function handleSort(col: string) {
    if (col === sortCol) {
      updateFilters({ sort_col: col, sort_dir: sortDir === "asc" ? "desc" : "asc", page: "1" }, false);
    } else {
      updateFilters({ sort_col: col, sort_dir: "asc", page: "1" }, false);
    }
  }

  /** Toggle visibility of a hideable column. */
  function toggleColumn(col: string) {
    const next = new Set(hiddenCols);
    if (next.has(col)) { next.delete(col); } else { next.add(col); }
    updateFilters({ hidden_cols: next.size > 0 ? [...next].join(",") : null });
  }

  // ── Clear / Save-view / Restore-last-view ─────────────
  function clearFilters() {
    clearStorageKey(groupId);
    const defaultServicesStr = defaultKeys.join(",");
    setSearchInput("");
    setQueryState({
      services: defaultServicesStr,
      view: "all",
      overdue_enabled: null,
      overdue_input: "1",
      q: null,
      page_size: String(DEFAULT_PAGE_SIZE),
      show_all: null,
      page: "1",
      sort_col: null,
      sort_dir: null,
      hidden_cols: null,
    });
  }

  function saveCurrentView() {
    const current: Record<string, string | null> = {
      services: selectedKeys.join(","),
      view: activeFilter,
      overdue_enabled: overdueEnabled ? "1" : null,
      overdue_input: overdueInput,
      q: searchQuery || null,
      page_size: String(pageSize),
      sort_col: sortCol,
      sort_dir: sortDir,
      hidden_cols: hiddenColsRaw || null,
    };
    saveFiltersToStorage(groupId, current);
    // Also write to the "last saved" snapshot so "กลับไปค่าล่าสุด" can restore it
    saveLastViewToStorage(groupId, current);
    setHasLastSaved(true);
    // Show toast briefly
    if (viewSavedTimerRef.current) clearTimeout(viewSavedTimerRef.current);
    setViewSaved(true);
    viewSavedTimerRef.current = setTimeout(() => setViewSaved(false), 2200);
  }

  /** Restore to the last manually saved view snapshot. */
  function restoreLastView() {
    const last = loadLastViewFromStorage(groupId);
    if (!Object.keys(last).length) return;
    setSearchInput(last["q"] ?? "");
    setQueryState({
      services: last["services"] ?? defaultKeys.join(","),
      view: last["view"] ?? "all",
      overdue_enabled: last["overdue_enabled"] ?? null,
      overdue_input: last["overdue_input"] ?? "1",
      q: last["q"] ?? null,
      page_size: last["page_size"] ?? String(DEFAULT_PAGE_SIZE),
      show_all: null,
      page: "1",
      sort_col: last["sort_col"] ?? null,
      sort_dir: last["sort_dir"] ?? null,
      hidden_cols: last["hidden_cols"] ?? null,
    });
  }

  // ── Effects ────────────────────────────────────────────

  // On mount: if no URL services param, try restoring from localStorage
  useEffect(() => {
    if (storageRestoredRef.current) return;
    storageRestoredRef.current = true;
    if (searchParams.get("services")) return; // URL already has state — respect it
    const stored = loadFiltersFromStorage(groupId);
    if (Object.keys(stored).length > 0) {
      // Restore from storage — including sort and hidden columns
      setQueryState({
        services: stored["services"] ?? defaultKeys.join(","),
        view: stored["view"] ?? "all",
        overdue_enabled: stored["overdue_enabled"] ?? null,
        overdue_input: stored["overdue_input"] ?? "1",
        q: stored["q"] ?? null,
        page_size: stored["page_size"] ?? String(DEFAULT_PAGE_SIZE),
        show_all: null,
        page: "1",
        sort_col: stored["sort_col"] ?? null,
        sort_dir: stored["sort_dir"] ?? null,
        hidden_cols: stored["hidden_cols"] ?? null,
      });
      if (stored["q"]) setSearchInput(stored["q"]);
    } else if (defaultKeys.length) {
      setQueryState({
        services: defaultKeys.join(","),
        view: activeFilter,
        overdue_enabled: overdueEnabled ? "1" : null,
        overdue_input: overdueInput,
        q: searchQuery || null,
        page_size: String(pageSize),
        show_all: showAll ? "1" : null,
        page: "1",
      });
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => { setSearchInput(searchQuery); }, [searchQuery]);

  useEffect(() => {
    const handle = window.setTimeout(() => {
      const trimmedValue = searchInput.trim();
      const currentTrimmed = searchQuery.trim();
      if (trimmedValue === currentTrimmed) return;
      updateFilters({ q: trimmedValue || null, page: "1" }, true);
    }, SEARCH_DEBOUNCE_MS);
    return () => window.clearTimeout(handle);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchInput, searchQuery]);

  useEffect(() => {
    let cancelled = false;
    if (!selectedKeys.length) {
      setResults(null);
      setResultsLoading(false);
      return;
    }
    setResultsLoading(true);
    void (async () => {
      try {
        const response = await getGroupResults(groupId, {
          overdueYears,
          page,
          pageSize,
          includeAll: showAll,
          view: activeFilter,
          query: searchQuery,
          overdueEnabled,
          sortCol: sortCol ?? undefined,
          sortDir: (sortDir as "asc" | "desc" | undefined) ?? undefined,
        });
        if (!cancelled) { setResults(response); setMessage(null); }
      } catch (error) {
        if (!cancelled) { setMessage(error instanceof ApiError ? error.detail : "โหลดผลลัพธ์ล่าสุดไม่สำเร็จ"); }
      } finally {
        if (!cancelled) { setResultsLoading(false); }
      }
    })();
    return () => { cancelled = true; };
  }, [activeFilter, groupId, overdueEnabled, overdueYears, page, pageSize, searchQuery, selectedKeys, showAll, sortCol, sortDir]);

  // On (re)opening a group, the LAST GENERATED result is the source of truth for
  // the service selection. Restore it once per mount so the checkboxes + warning
  // reflect what the displayed result was actually generated with — regardless of
  // any stale/partial ?services= left in the URL (which previously caused a false
  // "mismatch" warning, e.g. URL=hpv_screen vs generated cervical/hpv/specimen).
  // After this one-time restore, genuine user changes diverge from the summary
  // and the warning shows correctly; F5/reopen re-restores from the summary.
  useEffect(() => {
    if (selectionRestoredRef.current) return;
    const generated = results?.summary.selected_service_keys ?? [];
    if (!generated.length) return; // wait until the generated summary has loaded
    selectionRestoredRef.current = true;
    const urlServices = searchParams.get("services");
    const current = urlServices ? urlServices.split(",").filter(Boolean) : [];
    // Only navigate if the URL selection doesn't already match the generated set
    // (set comparison, order-insensitive) — avoids a redundant URL write.
    if (!sameSelection(current, generated)) {
      setQueryState({ services: generated.join(",") });
    }
  }, [results, searchParams]);

  useEffect(() => {
    if (!showAll || !results) return;
    if (results.total_filtered_rows <= MAX_SAFE_SHOW_ALL_ROWS) return;
    setMessage("แสดงทั้งหมดได้เมื่อผลลัพธ์หลังกรองไม่เกิน " + formatNumber(MAX_SAFE_SHOW_ALL_ROWS) + " ราย");
    setQueryState({ show_all: null, page_size: String(DEFAULT_PAGE_SIZE), page: "1" });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [results, showAll]);

  // Cleanup toast timer on unmount
  useEffect(() => {
    return () => {
      if (viewSavedTimerRef.current) clearTimeout(viewSavedTimerRef.current);
    };
  }, []);

  // ── Async actions ──────────────────────────────────────
  async function refreshGroup() {
    const response = await getTargetGroup(groupId);
    setGroup(response);
    return response;
  }

  async function refreshResults(forcePage = page) {
    setResultsLoading(true);
    const response = await getGroupResults(groupId, {
      overdueYears, page: forcePage, pageSize,
      includeAll: showAll, view: activeFilter,
      query: searchQuery, overdueEnabled,
      sortCol: sortCol ?? undefined,
      sortDir: (sortDir as "asc" | "desc" | undefined) ?? undefined,
    });
    setResults(response);
    setResultsLoading(false);
    return response;
  }

  function readError(error: unknown, fallback: string) {
    return error instanceof ApiError ? error.detail : fallback;
  }

  async function handleSaveGroupName(newName: string) {
    const updated = await updateGroupName(groupId, newName);
    setGroup(updated);
  }

  function doGenerate() {
    startTransition(async () => {
      try {
        setOperationBanner({
          title: "สถานะการสร้างผลลัพธ์",
          status: "processing",
          message: "กำลังสร้างผลลัพธ์ตามรายการที่เลือก...",
          currentStage: "กำลังคัดกรองรายการบริการและสรุปผลรายบุคคล",
        });
        await generateResults(groupId, selectedKeys);
        const refreshed = await refreshResults(1);
        setQueryState({ page: "1" });
        setOperationBanner({
          title: "สถานะการสร้างผลลัพธ์",
          status: "success",
          message: "สร้างผลลัพธ์สำเร็จ",
          currentStage: "เสร็จสิ้น",
          processedRows: refreshed.summary.total_target_people,
          totalRows: refreshed.summary.total_target_people,
        });
        setMessage("สร้างผลลัพธ์สำเร็จ");
      } catch (error) {
        const detail = readError(error, "สร้างผลลัพธ์ไม่สำเร็จ");
        setOperationBanner({
          title: "สถานะการสร้างผลลัพธ์",
          status: "failed",
          message: detail,
          currentStage: "พบข้อผิดพลาด",
        });
        setMessage(detail);
      }
    });
  }

  function handleFollowUp(_row: GroupResultRow) {
    // Placeholder — follow-up API not yet built.
    // When ready: open a follow-up form modal, POST to /api/target-groups/:groupId/results/:resultId/followups
  }

  function doExportExcel() {
    startTransition(async () => {
      try {
        setOperationBanner({
          title: "สถานะการส่งออกรายงาน",
          status: "processing",
          message: "กำลังเตรียมไฟล์ Excel...",
          currentStage: "กำลังแปลงผลลัพธ์เป็นไฟล์รายงาน",
        });
        const response = await exportGroupResults(groupId, "xlsx", selectedKeys);
        setOperationBanner({
          title: "สถานะการส่งออกรายงาน",
          status: "success",
          message: "ดาวน์โหลด Excel สำเร็จ: " + response.filename,
          currentStage: "เสร็จสิ้น",
        });
        setMessage("ดาวน์โหลด Excel สำเร็จ: " + response.filename);
      } catch (error) {
        const detail = readError(error, "ดาวน์โหลด Excel ไม่สำเร็จ");
        setOperationBanner({ title: "สถานะการส่งออกรายงาน", status: "failed", message: detail, currentStage: "พบข้อผิดพลาด" });
        setMessage(detail);
      }
    });
  }

  function doRefreshResults() {
    startTransition(async () => {
      try {
        setOperationBanner({
          title: "สถานะการโหลดผลลัพธ์",
          status: "processing",
          message: "กำลังโหลดผลลัพธ์ล่าสุด...",
          currentStage: "กำลังดึงข้อมูลผลลัพธ์จากระบบ",
        });
        const refreshed = await refreshResults();
        setOperationBanner({
          title: "สถานะการโหลดผลลัพธ์",
          status: "success",
          message: "โหลดผลลัพธ์ล่าสุดสำเร็จ",
          currentStage: "เสร็จสิ้น",
          processedRows: refreshed.total_filtered_rows,
          totalRows: refreshed.summary.total_target_people,
        });
        setMessage("โหลดผลลัพธ์ล่าสุดสำเร็จ");
      } catch (error) {
        const detail = readError(error, "โหลดผลลัพธ์ล่าสุดไม่สำเร็จ");
        setOperationBanner({ title: "สถานะการโหลดผลลัพธ์", status: "failed", message: detail, currentStage: "พบข้อผิดพลาด" });
        setMessage(detail);
      }
    });
  }

  // ── Derived display values ─────────────────────────────
  const selectedLabels = diseaseOptions
    .filter((option) => selectedKeys.includes(option.key))
    .map((option) => option.label);

  // Human-readable labels for the services that the displayed result was
  // generated with (falls back to the raw key if no catalog label exists).
  const generatedServiceLabels = (results?.summary.selected_service_keys ?? []).map(
    (key) => diseaseOptions.find((option) => option.key === key)?.label ?? key,
  );

  const totalTargetPeople = results?.summary.total_target_people ?? 0;
  const totalFilteredRows = results?.total_filtered_rows ?? 0;
  const currentPageRowCount = results?.results.length ?? 0;
  const remainingCount = Math.max(totalTargetPeople - totalFilteredRows, 0);
  const filteredPercent = totalTargetPeople ? ((totalFilteredRows / totalTargetPeople) * 100).toFixed(2) : "0.00";
  const remainingPercent = totalTargetPeople ? ((remainingCount / totalTargetPeople) * 100).toFixed(2) : "0.00";
  const currentPage = results?.page ?? page;
  const totalPages = results?.total_pages ?? 0;
  const currentStart = totalFilteredRows === 0 ? 0 : showAll ? 1 : (currentPage - 1) * pageSize + 1;
  const currentEnd = showAll ? currentPageRowCount : Math.min(currentStart + currentPageRowCount - 1, totalFilteredRows);
  const canShowAll = totalFilteredRows > 0 && totalFilteredRows <= MAX_SAFE_SHOW_ALL_ROWS;
  const exportDisabled = isPending || !hasResults || isDirty || isSourceStale || requiresRegeneration;

  // Is any filter non-default?
  const isFiltered =
    activeFilter !== "all" ||
    overdueEnabled ||
    searchQuery.trim().length > 0;

  // ── Render ─────────────────────────────────────────────
  return (
    <div className="stack-layout">

      {/* Breadcrumb */}
      <nav className="workspace-breadcrumb" aria-label="breadcrumb">
        <Link href="/target-groups" className="breadcrumb-link">{"กลุ่มเป้าหมาย"}</Link>
        <span className="breadcrumb-sep" aria-hidden="true">{" / "}</span>
        <span className="breadcrumb-current" aria-current="page">{group.group_name}</span>
      </nav>

      {/* Horizontal stepper */}
      <WorkspaceStepper
        activeStep={activeStep}
        onStepClick={(i) => { if (i === 1) setShowFilePanel((prev) => !prev); }}
      />

      {/* File management panel */}
      {showFilePanel ? (
        <FileManagementPanel
          group={group}
          onFilesAdded={(updated) => {
            setGroup(updated);
            setShowFilePanel(false);
          }}
        />
      ) : null}

      {/* Source-file staleness warning */}
      {isSourceStale && !isDirty ? (
        <SourceFileStaleBanner onRegenerate={doGenerate} isPending={isPending} />
      ) : null}

      {/* Normalization-version staleness (result generated with older logic) */}
      {requiresRegeneration && !isSourceStale && !isDirty ? (
        <SourceFileStaleBanner
          onRegenerate={doGenerate}
          isPending={isPending}
          title="ผลลัพธ์นี้สร้างด้วยวิธีประมวลผลรุ่นก่อน"
          note="ระบบปรับปรุงการจัดหมวดประวัติ (เช่น ประวัติจากไฟล์กลุ่มเป้าหมาย) หลังจากผลลัพธ์นี้ถูกสร้าง กรุณาสร้างผลลัพธ์ใหม่เพื่อให้ตารางถูกต้อง"
        />
      ) : null}

      {/* Dirty/stale config warning */}
      {isDirty ? (
        <ConfigDirtyBanner selectedLabels={selectedLabels} onRegenerate={doGenerate} isPending={isPending} />
      ) : null}

      {/* Operation banner */}
      {operationBanner ? (
        <JobProgressCard
          title={operationBanner.title}
          status={operationBanner.status}
          message={operationBanner.message}
          currentStage={operationBanner.currentStage}
          processedRows={operationBanner.processedRows}
          totalRows={operationBanner.totalRows}
        />
      ) : null}

      {/* Group identity panel */}
      <section className="panel workspace-identity-panel">
        <p className="eyebrow">{"กลุ่มเป้าหมาย"}</p>
        <GroupNameEditor name={group.group_name} onSave={handleSaveGroupName} />
        <p className="summary-copy">
          {"อัปโหลดเมื่อ " + formatDate(group.uploaded_at) + " • ใช้ไฟล์ต้นทาง " + group.source_file_count + " ไฟล์"}
        </p>
        <div className="status-stack">
          <span className="status-chip ready">{"พร้อมใช้งาน"}</span>
          <span className={"status-chip " + (group.invalid_rows ? "warning" : "ready")}>
            {"ต้องตรวจสอบ " + formatNumber(group.invalid_rows) + " แถว"}
          </span>
          {results?.summary.generated_at ? (
            <span className="status-chip muted">
              {"ผลลัพธ์ล่าสุด: " + formatDate(results.summary.generated_at)}
            </span>
          ) : null}
          {isDirty ? (
            <span className="status-chip warning">{"ผลลัพธ์ไม่ตรงกับรายการที่เลือก"}</span>
          ) : null}
          {isSourceStale && !isDirty ? (
            <span className="status-chip warning">{"ผลลัพธ์ไม่ตรงกับข้อมูลล่าสุด"}</span>
          ) : null}
        </div>
      </section>

      {/* ── Screening config (collapsible) ── */}
      <details className="panel" open={!hasResults}>
        <summary className="panel-summary-toggle">
          <span>{"ขั้นที่ 4 — เลือกรายการคัดกรองและสร้างผลลัพธ์"}</span>
          {selectedLabels.length ? (
            <span className="status-chip muted compact-chip">{"เลือก: " + selectedLabels.join(", ")}</span>
          ) : null}
        </summary>
        <div className="section-block">
          <h3>{"รายการโรคหรือบริการ"}</h3>
          <DiseaseFilter
            options={diseaseOptions}
            selected={selectedKeys}
            onChange={(keys) =>
              setQueryState({
                services: keys.join(","),
                view: activeFilter,
                overdue_enabled: overdueEnabled ? "1" : null,
                overdue_input: overdueInput,
                q: searchQuery || null,
                page_size: String(pageSize),
                show_all: showAll ? "1" : null,
                page: "1",
              })
            }
          />
          {selectedLabels.length ? (
            <p className="summary-copy section-block">{"รายการที่เลือก: " + selectedLabels.join(", ")}</p>
          ) : null}
          <div className="button-row section-block">
            <button
              className="primary-button"
              disabled={isPending || selectedKeys.length === 0}
              onClick={doGenerate}
            >
              {isPending ? "กำลังสร้างผลลัพธ์..." : isDirty ? "สร้างผลลัพธ์ใหม่" : "สร้างผลลัพธ์"}
            </button>
          </div>
          {message ? <p className="feedback-line is-success">{message}</p> : null}
        </div>
      </details>

      {/* ── Result summary (collapsible) ── */}
      {results ? (
        <details className="panel" open>
          <summary className="panel-summary-toggle">
            <span>{"ภาพรวมผลลัพธ์"}</span>
            <span className="status-chip accent compact-chip">
              {"coverage " + formatNumber(results.summary.coverage_percent) + "%"}
            </span>
            <span className="status-chip muted compact-chip">
              {"ทั้งหมด " + formatNumber(results.summary.total_target_people) + " ราย"}
            </span>
          </summary>
          <div className="section-block">
            <div className="summary-grid">
              <SummaryCard title="จำนวนกลุ่มเป้าหมายทั้งหมด" value={formatNumber(results.summary.total_target_people)} />
              <SummaryCard title="จำนวนที่มีประวัติในรายการที่เลือก" value={formatNumber(results.summary.people_with_selected_history)} tone="ready" />
              <SummaryCard title="จำนวนที่ยังไม่พบประวัติ" value={formatNumber(results.summary.people_without_selected_history)} tone="muted" />
              <SummaryCard
                title="coverage %"
                value={formatNumber(results.summary.coverage_percent) + "%"}
                note={"ฐานคำนวณ " + formatNumber(results.summary.coverage_denominator_people) + " ราย"}
                tone="accent"
              />
              <SummaryCard title="ตัวระบุใช้ได้" value={formatNumber(results.summary.valid_identifier_people)} note="ใช้เป็นฐานคำนวณ coverage" tone="accent" />
            </div>
            <div className="summary-grid compact-summary-grid">
              <SummaryCard title="ตัวระบุไม่ถูกต้อง/ขาด" value={formatNumber(results.summary.invalid_identifier_people)} tone="warning" />
              <SummaryCard title="ไม่ใช่คนไทย" value={formatNumber(results.summary.non_thai_nationality_people)} tone="muted" />
              <SummaryCard title="ข้อมูลระบุตัวตนไม่พอ" value={formatNumber(results.summary.insufficient_identity_people)} tone="warning" />
            </div>
            <div className="summary-grid compact-summary-grid">
              <SummaryCard title="ต้องตรวจสอบข้อมูลระบุตัวตน" value={formatNumber(results.summary.review_required_identity_people)} tone="warning" />
              <SummaryCard title="นอกขอบเขตกลุ่มเป้าหมาย" value={formatNumber(results.summary.outside_target_scope_people)} tone="muted" />
              <SummaryCard title="ยังไม่เคยตรวจ" value={formatNumber(results.summary.never_checked_people)} tone="muted" />
            </div>
            <div className="summary-grid compact-summary-grid">
              <SummaryCard title="ตรวจแล้วแต่เกินกำหนด" value={formatNumber(results.summary.checked_but_overdue_people)} tone="warning" />
              <SummaryCard title="ตรวจแล้วและยังไม่เกินกำหนด" value={formatNumber(results.summary.checked_and_within_threshold_people)} tone="ready" />
              <SummaryCard
                title="บริการที่เลือก"
                value={formatNumber(results.summary.selected_service_count)}
                note={generatedServiceLabels.join(", ") || "-"}
              />
            </div>
          </div>
        </details>
      ) : null}

      {/* ── Results table panel (PRIMARY workspace) ── */}
      <section className="panel results-workspace-panel">

        {/* Sticky toolbar */}
        <div className="sticky-table-toolbar">
          {/* View tabs row */}
          <div className="sticky-table-toolbar-row view-tabs-row">
            <div className="mini-tab-row scrollable-tab-row">
              {VIEW_FILTERS.map((filter) => (
                <button
                  key={filter.key}
                  className={activeFilter === filter.key ? "mini-tab active" : "mini-tab"}
                  onClick={() => updateFilters({ view: filter.key, page: "1" }, true)}
                  type="button"
                  disabled={!hasResults && !resultsLoading}
                >
                  {filter.label}
                </button>
              ))}
            </div>
          </div>

          {/* Controls row */}
          <div className="sticky-table-toolbar-row controls-row">
            {/* Search */}
            <label className="search-control compact-control">
              <span>{"ค้นหา"}</span>
              <input
                type="search"
                value={searchInput}
                onChange={(event) => setSearchInput(event.target.value)}
                placeholder="CID หรือชื่อ-สกุล"
                disabled={!hasResults && !resultsLoading}
              />
            </label>

            {/* Overdue toggle + years */}
            <label className="toggle-control">
              <input
                type="checkbox"
                checked={overdueEnabled}
                onChange={(event) => updateFilters({ overdue_enabled: event.target.checked ? "1" : null }, true)}
                disabled={!hasResults && !resultsLoading}
              />
              <span>{"เกินกำหนด"}</span>
            </label>

            <div className="overdue-control-group">
              <label className="search-control compact-control">
                <span>{"ปี"}</span>
                <input
                  type="number"
                  min={1}
                  step={1}
                  value={overdueInput}
                  disabled={!overdueEnabled}
                  onChange={(event) => updateFilters({ overdue_input: event.target.value || "1" }, true)}
                  style={{ width: "4rem" }}
                />
              </label>
              <div className="mini-tab-row">
                {OVERDUE_PRESETS.map((option) => (
                  <button
                    key={option}
                    type="button"
                    className={String(option) === overdueInput ? "mini-tab active" : "mini-tab"}
                    disabled={!overdueEnabled}
                    onClick={() => updateFilters({ overdue_input: String(option) }, true)}
                  >
                    {String(option) + " ปี"}
                  </button>
                ))}
              </div>
            </div>

            {/* Page size */}
            <label className="search-control compact-control">
              <span>{"แถว/หน้า"}</span>
              <select
                value={showAll && canShowAll ? "all" : String(pageSize)}
                onChange={(event) => {
                  const nextValue = event.target.value;
                  if (nextValue === "all") { updateFilters({ show_all: "1", page: "1" }, true); return; }
                  updateFilters({ page_size: nextValue, show_all: null, page: "1" }, true);
                }}
                disabled={!hasResults && !resultsLoading}
              >
                {PAGE_SIZE_OPTIONS.map((option) => (
                  <option key={option} value={option}>{String(option)}</option>
                ))}
                <option value="all" disabled={!canShowAll}>{"ทั้งหมด"}</option>
              </select>
            </label>

            {/* Column visibility toggles */}
            <div className="col-toggle-group" title="เลือกคอลัมน์ที่จะแสดง">
              {(
                [
                  { key: "age",         label: "อายุ" },
                  { key: "sex",         label: "เพศ" },
                  { key: "match_count", label: "ครั้งที่พบ" },
                  { key: "last_visit",  label: "วันที่ล่าสุด" },
                  { key: "days_since",  label: "ผ่านมา" },
                  { key: "provenance",  label: "หลักฐาน" },
                ] as const
              ).map(({ key, label }) => (
                <button
                  key={key}
                  type="button"
                  className={`col-toggle-btn${hiddenCols.has(key) ? " col-hidden" : " col-visible"}`}
                  onClick={() => toggleColumn(key)}
                  title={hiddenCols.has(key) ? `แสดงคอลัมน์ "${label}"` : `ซ่อนคอลัมน์ "${label}"`}
                >
                  {hiddenCols.has(key) ? "○" : "●"} {label}
                </button>
              ))}
            </div>

            {/* Action buttons */}
            <div className="toolbar-actions">
              <button
                type="button"
                className="secondary-button compact-button"
                disabled={!hasResults}
                title="ดูตัวอย่างคอลัมน์และเลือกรูปแบบการส่งออก"
                onClick={() => setShowExportPreview((prev) => !prev)}
              >
                {showExportPreview ? "✕ ปิดตัวอย่าง" : "ดูตารางก่อนส่งออก"}
              </button>
              <button
                type="button"
                className="secondary-button compact-button"
                disabled={isPending}
                onClick={doRefreshResults}
                title="โหลดผลลัพธ์ล่าสุดจากระบบ"
              >
                {"↻ รีเฟรช"}
              </button>
              <button
                type="button"
                className="ghost-button compact-button"
                onClick={clearFilters}
                title="ล้างตัวกรองทั้งหมดกลับเป็นค่าเริ่มต้น"
              >
                {"✕ ล้างตัวกรอง"}
              </button>
              {hasLastSaved && (
                <button
                  type="button"
                  className="ghost-button compact-button"
                  onClick={restoreLastView}
                  title="กลับไปใช้มุมมองที่บันทึกไว้ล่าสุด"
                >
                  {"↩ กลับไปค่าล่าสุด"}
                </button>
              )}
              <button
                type="button"
                className="secondary-button compact-button"
                onClick={saveCurrentView}
                title="บันทึกมุมมองนี้ไว้ใช้ครั้งต่อไป"
              >
                {"⊙ บันทึกมุมมองนี้"}
              </button>
            </div>
          </div>
        </div>

        {/* View saved toast */}
        {viewSaved ? (
          <div className="view-saved-toast" role="status" aria-live="polite">
            {"✓ บันทึกมุมมองนี้แล้ว"}
          </div>
        ) : null}

        {/* Export preview panel */}
        {showExportPreview && results ? (
          <div className="export-preview-panel">
            <div className="export-preview-head">
              <div>
                <p className="eyebrow">{"ตัวอย่างก่อนส่งออก"}</p>
                <h4>{"คอลัมน์ไฟล์ที่จะส่งออก"}</h4>
                <p className="summary-copy">{"คอลัมน์ต้นทาง + คอลัมน์ผลลัพธ์ (เพิ่มโดยระบบ)"}</p>
              </div>
              <button
                type="button"
                className="ghost-button compact-button"
                onClick={() => setShowExportPreview(false)}
              >
                {"ปิดตัวอย่าง"}
              </button>
            </div>
            <div className="export-col-legend">
              <span className="export-col-tag export-col-tag-base">{"■ คอลัมน์ต้นทาง (จากไฟล์กลุ่มเป้าหมาย)"}</span>
              <span className="export-col-tag export-col-tag-appended">{"■ คอลัมน์ผลลัพธ์ (เพิ่มโดยระบบ)"}</span>
            </div>
            <div className="table-wrap export-preview-table-wrap">
              <table className="data-table compact-data-table">
                <thead>
                  <tr>
                    <th className="export-col-base-header">{"CID / ตัวระบุ"}</th>
                    <th className="export-col-base-header">{"ชื่อ-สกุล"}</th>
                    <th className="export-col-base-header">{"เพศ"}</th>
                    <th className="export-col-base-header">{"อายุ"}</th>
                    <th className="export-col-base-header">{"สัญชาติ"}</th>
                    <th className="export-col-base-header">{"ที่อยู่"}</th>
                    <th className="export-col-appended-header">{"สถานะการตรวจ"}</th>
                    <th className="export-col-appended-header">{"ผลลัพธ์"}</th>
                    <th className="export-col-appended-header">{"จำนวนครั้ง"}</th>
                    <th className="export-col-appended-header">{"วันที่ล่าสุด"}</th>
                    <th className="export-col-appended-header">{"ผ่านมา (ปี)"}</th>
                    <th className="export-col-appended-header">{"วิธีจับคู่"}</th>
                  </tr>
                </thead>
                <tbody>
                  {results.results.slice(0, 5).map((row) => (
                    <tr key={row.result_id}>
                      <td className="export-col-base-cell">
                        <code className="cid-text">{row.normalized_cid ?? row.matched_identifier ?? "-"}</code>
                      </td>
                      <td className="export-col-base-cell">{row.full_name ?? "-"}</td>
                      <td className="export-col-base-cell">{row.sex ?? "-"}</td>
                      <td className="export-col-base-cell">
                        {row.age !== null && row.age !== undefined ? String(row.age) : "-"}
                      </td>
                      <td className="export-col-base-cell">{row.target_group_nationality ?? "-"}</td>
                      <td className="export-col-base-cell">{row.target_group_address ?? "-"}</td>
                      <td className="export-col-appended-cell">{row.screening_status ?? "-"}</td>
                      <td className="export-col-appended-cell">{row.result_category ?? "-"}</td>
                      <td className="export-col-appended-cell">{formatNumber(row.matching_record_count)}</td>
                      <td className="export-col-appended-cell">{formatDate(row.last_visit_date)}</td>
                      <td className="export-col-appended-cell">
                        {row.years_since_last_visit !== null && row.years_since_last_visit !== undefined
                          ? `${formatNumber(row.years_since_last_visit)} ปี`
                          : "-"}
                      </td>
                      <td className="export-col-appended-cell">{row.match_method ?? "-"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {results.results.length > 5 ? (
              <p className="summary-copy section-block">
                {"แสดงตัวอย่าง 5 แถวแรก จากทั้งหมด " + formatNumber(totalFilteredRows) + " แถวที่กรองแล้ว"}
              </p>
            ) : null}
            <div className="button-row section-block">
              <button
                type="button"
                className="primary-button"
                disabled={exportDisabled}
                onClick={doExportExcel}
                title={
                  exportDisabled
                    ? "สร้างผลลัพธ์ก่อนจึงจะส่งออกได้"
                    : `ส่งออกเฉพาะรายการที่กรองแล้ว (${formatNumber(totalFilteredRows)} ราย)`
                }
              >
                {"📥 ส่งออก Excel (กรองแล้ว " + formatNumber(totalFilteredRows) + " ราย)"}
              </button>
              <button
                type="button"
                className="secondary-button"
                disabled
                title="ส่งออกทั้งหมดโดยไม่คำนึงถึงตัวกรอง — ยังไม่รองรับ"
              >
                {"ส่งออกทั้งหมด (" + formatNumber(totalTargetPeople) + " ราย) — เร็วๆ นี้"}
              </button>
            </div>
            <p className="export-privacy-note">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" aria-hidden="true" style={{ flexShrink: 0, marginTop: 1 }}>
                <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
                <line x1="12" y1="9" x2="12" y2="13" />
                <line x1="12" y1="17" x2="12.01" y2="17" />
              </svg>
              {"ไฟล์ Excel ที่ส่งออกมีข้อมูลส่วนบุคคลของผู้ป่วย — เก็บในพื้นที่ปลอดภัยภายในหน่วยงาน ห้ามส่งออกนอกเครือข่ายโรงพยาบาล"}
            </p>
          </div>
        ) : null}

        {/* Table head strip */}
        <div className="table-workspace-head">
          <div>
            <p className="eyebrow">{"ผลรายบุคคล"}</p>
            <h3>{"ตารางติดตามผล"}</h3>
          </div>
          <div className="table-summary-strip">
            {hasResults ? (
              <>
                <span className="status-chip muted">
                  {"แสดง " + formatNumber(totalFilteredRows) + " / " + formatNumber(totalTargetPeople) + " ราย (" + filteredPercent + "%)"}
                </span>
                <span className="status-chip muted">
                  {"เหลือ " + formatNumber(remainingCount) + " ราย (" + remainingPercent + "%)"}
                </span>
                {!showAll && totalFilteredRows > 0 ? (
                  <span className="status-chip muted">
                    {"รายการ " + formatNumber(currentStart) + "–" + formatNumber(currentEnd)}
                  </span>
                ) : null}
                {isFiltered ? (
                  <span className="status-chip accent compact-chip">{"กรองอยู่"}</span>
                ) : null}
              </>
            ) : null}
          </div>
        </div>

        {/* Table body */}
        {resultsLoading ? (
          <LoadingState compact title="โปรดรอสักครู่..." message="กำลังโหลดผลรายบุคคล..." />
        ) : !results ? (
          <div className="empty-state-box">
            <p className="summary-copy">{"ยังไม่มีข้อมูลให้แสดง"}</p>
            <p>{"เลือกรายการที่ต้องการ แล้วกด \"สร้างผลลัพธ์\" เพื่อดูรายชื่อทั้งหมด พร้อมแยกสถานะว่าใครยังไม่เคยตรวจ ใครเกินกำหนด และใครมีปัญหาเรื่องตัวระบุ"}</p>
          </div>
        ) : (
          <>
            {showAll && !canShowAll ? (
              <p className="summary-copy">{"การแสดงทั้งหมดเปิดได้เมื่อผลลัพธ์หลังกรองไม่เกิน " + formatNumber(MAX_SAFE_SHOW_ALL_ROWS) + " ราย"}</p>
            ) : null}
            {activeFilter !== "all" ? (
              <p className="summary-copy">
                {"กำลังดูหมวด "}<span className="inline-label">{VIEW_FILTERS.find((item) => item.key === activeFilter)?.label}</span>
              </p>
            ) : null}
            {overdueEnabled ? (
              <p className="summary-copy">
                {"ใช้ตัวกรองเพิ่มเติม: แสดงเฉพาะรายการที่มีประวัติและผ่านมาแล้วอย่างน้อย " + formatNumber(overdueYears) + " ปี"}
              </p>
            ) : null}

            <ResultsTable
              rows={results.results}
              onOpenDetails={setSelectedRow}
              onFollowUp={handleFollowUp}
              sortCol={sortCol}
              sortDir={sortDir}
              onSort={handleSort}
              hiddenCols={hiddenCols}
            />

            {!showAll && totalPages > 1 ? (
              <div className="button-row section-block">
                <button
                  className="secondary-button compact-button"
                  type="button"
                  disabled={currentPage <= 1}
                  onClick={() => updateFilters({ page: String(Math.max(currentPage - 1, 1)) })}
                >
                  {"หน้าก่อน"}
                </button>
                <span className="status-chip muted">
                  {"หน้า " + formatNumber(currentPage) + " / " + formatNumber(totalPages)}
                </span>
                <button
                  className="secondary-button compact-button"
                  type="button"
                  disabled={currentPage >= totalPages}
                  onClick={() => updateFilters({ page: String(Math.min(currentPage + 1, totalPages)) })}
                >
                  {"หน้าถัดไป"}
                </button>
              </div>
            ) : null}
          </>
        )}
      </section>

      {/* Technical details (collapsible) */}
      <details className="panel technical-panel">
        <summary>{"ข้อมูลเชิงเทคนิคและรายละเอียดงานนำเข้า"}</summary>
        <div className="stack-layout compact-stack section-block">
          <section className="subtle-box">
            <h4>{"รายละเอียดไฟล์และสถานะงาน"}</h4>
            <div className="key-grid">
              <div><dt>{"ไฟล์ต้นทางอ้างอิง"}</dt><dd>{group.source_file_name}</dd></div>
              <div><dt>{"จำนวนแถวทั้งหมด"}</dt><dd>{formatNumber(group.total_rows)}</dd></div>
              <div><dt>{"CID ซ้ำในงาน"}</dt><dd>{formatNumber(importSummary.duplicate_cid_rows)}</dd></div>
              <div><dt>{"จับคู่ได้"}</dt><dd>{formatNumber(group.match_summary.matched)}</dd></div>
              <div className="full-span">
                <dt>{"source-set hash"}</dt>
                <dd><code>{group.source_set_hash ?? group.source_file_hash}</code></dd>
              </div>
            </div>
            {group.uploaded_files.length ? (
              <div className="section-block">
                <p className="summary-copy">{"ไฟล์ที่อยู่ในงานนี้"}</p>
                {group.uploaded_files.map((file) => (
                  <div key={getTargetGroupFileKey(file)}>
                    <p>{file.file_name + " • " + file.file_type + " • " + (file.parse_status ?? "-") + " • " + formatNumber(file.row_count ?? 0) + " แถว"}</p>
                    {file.parse_error_summary ? <p className="summary-copy">{file.parse_error_summary}</p> : null}
                  </div>
                ))}
              </div>
            ) : null}
          </section>

          <section className="subtle-box">
            <h4>{"ขั้นตอนสนับสนุน"}</h4>
            <div className="button-row">
              <button
                className="secondary-button"
                disabled={isPending}
                onClick={() =>
                  startTransition(async () => {
                    try {
                      setOperationBanner({ title: "สถานะการยืนยันการนำเข้า", status: "processing", message: "กำลังยืนยันการนำเข้าข้อมูล...", currentStage: "กำลังตรวจสอบสถานะ staging และ production" });
                      const response = await confirmImport(groupId);
                      setConfirmState(response);
                      await refreshGroup();
                      setOperationBanner({ title: "สถานะการยืนยันการนำเข้า", status: "success", message: "ยืนยันการนำเข้าสำเร็จ", currentStage: "เสร็จสิ้น" });
                      setMessage("ยืนยันการนำเข้าสำเร็จ");
                    } catch (error) {
                      const detail = readError(error, "ยืนยันการนำเข้าไม่สำเร็จ");
                      setOperationBanner({ title: "สถานะการยืนยันการนำเข้า", status: "failed", message: detail, currentStage: "พบข้อผิดพลาด" });
                      setMessage(detail);
                    }
                  })
                }
              >
                {"ยืนยันการนำเข้า"}
              </button>
              <button
                className="secondary-button"
                disabled={isPending}
                onClick={() =>
                  startTransition(async () => {
                    try {
                      setOperationBanner({ title: "สถานะการจับคู่ผู้ป่วย", status: "processing", message: "กำลังจับคู่ข้อมูลผู้ป่วย...", currentStage: "กำลังจับคู่ตัวระบุและสรุปสถานะการ match" });
                      const response = await runMatch(groupId);
                      setMatchState(response);
                      await refreshGroup();
                      await refreshResults(1);
                      setQueryState({ page: "1" });
                      setOperationBanner({
                        title: "สถานะการจับคู่ผู้ป่วย", status: "success", message: "จับคู่ผู้ป่วยสำเร็จ", currentStage: "เสร็จสิ้น",
                        processedRows: response.matched_rows + response.not_found_rows + response.ambiguous_rows + response.needs_review_rows,
                        totalRows: group.total_rows,
                      });
                      setMessage("จับคู่ผู้ป่วยสำเร็จ");
                    } catch (error) {
                      const detail = readError(error, "จับคู่ไม่สำเร็จ");
                      setOperationBanner({ title: "สถานะการจับคู่ผู้ป่วย", status: "failed", message: detail, currentStage: "พบข้อผิดพลาด" });
                      setMessage(detail);
                    }
                  })
                }
              >
                {"เริ่มจับคู่ผู้ป่วย"}
              </button>
            </div>
            {confirmState ? <p className="summary-copy">{"parse status: " + confirmState.parse_status}</p> : null}
            {matchState ? (
              <div className="section-block">
                <p>{"matched: " + formatNumber(matchState.matched_rows)}</p>
                <p>{"not found: " + formatNumber(matchState.not_found_rows)}</p>
                <p>{"ambiguous: " + formatNumber(matchState.ambiguous_rows)}</p>
                <p>{"needs review: " + formatNumber(matchState.needs_review_rows)}</p>
              </div>
            ) : null}
          </section>

          <section className="subtle-box">
            <h4>{"ตัวอย่างข้อมูลนำเข้า"}</h4>
            <p className="summary-copy">{"แสดง " + formatNumber(group.preview_rows.length) + " แถวแรกจากหลายไฟล์รวมกัน"}</p>
            <TargetGroupPreviewTable rows={group.preview_rows} />
            {group.validation_issues.length ? (
              <div className="section-block">
                <p className="summary-copy">{"รายการที่ต้องตรวจสอบ"}</p>
                {group.validation_issues.map((issue) => (
                  <p key={getValidationIssueKey(issue)}>{"แถว " + formatNumber(issue.row_no) + ": " + issue.message}</p>
                ))}
              </div>
            ) : null}
          </section>
        </div>
      </details>

      <PatientDetailModal
        row={selectedRow}
        groupId={groupId}
        selectedServiceKeys={selectedKeys}
        onClose={() => setSelectedRow(null)}
      />
    </div>
  );
}
