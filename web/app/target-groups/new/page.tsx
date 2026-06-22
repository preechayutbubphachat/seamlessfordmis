import { Shell } from "@/components/shell";
import { UploadForm } from "@/components/upload-form";

export default function TargetGroupUploadPage() {
  return (
    <Shell>
      <div className="stack-lg">
        <section className="hero stack-md">
          <p className="eyebrow">นำเข้ากลุ่มเป้าหมาย</p>
          <h2>อัปโหลดรายชื่อกลุ่มเป้าหมาย ตรวจปัญหาระดับแถว และยืนยันก่อนเริ่มจับคู่</h2>
          <p className="muted">
            ระบบจะแสดงค่าดิบที่นำเข้าและไม่เดาข้อมูลแทน เมื่อรหัสอ้างอิงไม่ครบหรือจับคู่ได้ไม่ชัดเจน
          </p>
        </section>

        <UploadForm />
      </div>
    </Shell>
  );
}
