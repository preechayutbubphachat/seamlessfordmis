"use client";

export function UploadCTAButton() {
  function handleClick() {
    document
      .querySelector(".db-dropzone")
      ?.scrollIntoView({ behavior: "smooth", block: "center" });
    setTimeout(() => {
      (document.querySelector(".db-dropzone") as HTMLElement | null)?.focus();
    }, 400);
  }

  return (
    <div className="db-header-cta">
      <button
        type="button"
        className="primary-button db-cta-btn"
        onClick={handleClick}
      >
        <svg
          width="26"
          height="26"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.8"
          style={{ flexShrink: 0 }}
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M12 16.5V9.75m0 0-3 3m3-3 3 3M6.75 19.5a4.5 4.5 0 0 1-1.41-8.775 5.25 5.25 0 0 1 10.233-2.33 3 3 0 0 1 3.758 3.848A3.752 3.752 0 0 1 18 19.5H6.75Z"
          />
        </svg>
        เพิ่มข้อมูลการคัดกรอง
      </button>
      <p className="db-cta-hint">รองรับไฟล์: Excel (.xlsx, .xls), CSV, PDF และอื่นๆ</p>
    </div>
  );
}
