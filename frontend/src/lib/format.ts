function parseDate(value: string | null | undefined) {
  if (!value) return null;
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
}

export function formatDate(value: string | null | undefined): string {
  const date = parseDate(value);
  if (!date) return value ?? "-";
  return new Intl.DateTimeFormat("th-TH", { dateStyle: "medium" }).format(date);
}

export function formatNumber(value: number | null | undefined): string {
  if (value === null || value === undefined) return "-";
  return new Intl.NumberFormat("th-TH").format(value);
}

export function formatSexLabel(value: string | null | undefined): string {
  if (!value) return "-";
  if (value === "male") return "ชาย";
  if (value === "female") return "หญิง";
  return value;
}

export function formatAgeDisplay({
  age,
  rawAge,
  birthDate,
}: {
  age: number | null | undefined;
  rawAge?: string | null;
  birthDate?: string | null;
}): string {
  const birth = parseDate(birthDate);
  if (birth) {
    const today = new Date();
    let years = today.getFullYear() - birth.getFullYear();
    const currentYearBirthday = new Date(today.getFullYear(), birth.getMonth(), birth.getDate());
    if (today < currentYearBirthday) {
      years -= 1;
    }
    const lastBirthday = new Date(birth);
    lastBirthday.setFullYear(birth.getFullYear() + years);
    const days = Math.max(0, Math.floor((today.getTime() - lastBirthday.getTime()) / 86400000));
    if (years <= 0) {
      const totalDays = Math.max(0, Math.floor((today.getTime() - birth.getTime()) / 86400000));
      return `${formatNumber(totalDays)} วัน`;
    }
    if (days > 0) {
      return `${formatNumber(years)} ปี ${formatNumber(days)} วัน`;
    }
    return `${formatNumber(years)} ปี`;
  }

  if (rawAge) {
    const trimmed = rawAge.trim();
    if (trimmed.includes("วัน") || trimmed.includes("ปี")) {
      return trimmed;
    }
  }

  if (age !== null && age !== undefined) {
    return `${formatNumber(age)} ปี`;
  }

  return rawAge?.trim() || "-";
}
