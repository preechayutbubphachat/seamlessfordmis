"use client";

import type { DiseaseOption } from "@/types/target-group";

export function DiseaseFilter({
  options,
  selected,
  onChange,
}: {
  options: DiseaseOption[];
  selected: string[];
  onChange: (keys: string[]) => void;
}) {
  const selectedOptions = options.filter((option) => selected.includes(option.key));

  if (!options.length) {
    return <p className="summary-copy">ยังไม่พบรายการโรคหรือบริการจากฐานข้อมูลการตรวจโรค</p>;
  }

  return (
    <div className="stack-layout compact-stack">
      <div className="button-row">
        {options.map((option) => {
          const checked = selected.includes(option.key);
          return (
            <label key={option.key} className={`filter-pill ${checked ? "active" : ""}`}>
              <input
                type="checkbox"
                checked={checked}
                onChange={() => {
                  onChange(checked ? selected.filter((item) => item !== option.key) : [...selected, option.key]);
                }}
              />
              <span>{option.label}</span>
            </label>
          );
        })}
      </div>
      <div className="subtle-box">
        <p className="summary-copy">รายการที่เลือกตอนนี้</p>
        {selectedOptions.length ? (
          <div className="button-row">
            {selectedOptions.map((option) => (
              <span key={option.key} className="status-chip ready">{option.label}</span>
            ))}
          </div>
        ) : (
          <p className="summary-copy">ยังไม่ได้เลือกรายการ กรุณาเลือกอย่างน้อย 1 รายการก่อนสร้างผลลัพธ์</p>
        )}
      </div>
    </div>
  );
}
