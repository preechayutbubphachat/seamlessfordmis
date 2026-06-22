import { GroupResultsWorkspace } from "@/components/group-results-workspace";
import { Shell } from "@/components/shell";
import { getDiseaseMappings, getGroupResults, getGroupedDiseaseSummary, getTargetGroup } from "@/lib/api";

export default async function GroupResultsPage({ params }: { params: Promise<{ jobId: string }> }) {
  const { jobId } = await params;
  let job;
  let diseaseOptions;

  try {
    [job, diseaseOptions] = await Promise.all([getTargetGroup(jobId), getDiseaseMappings()]);
  } catch (error) {
    return (
      <Shell>
        <div className="stack-lg">
          <section className="hero stack-md">
            <p className="eyebrow">ผลลัพธ์กลุ่มเป้าหมาย</p>
            <h2>ไม่พบงานกลุ่มเป้าหมายเลขที่ #{jobId}</h2>
            <p className="muted">
              กรุณาเปิดงานจากหน้าส่งไฟล์กลุ่มเป้าหมาย หรือใช้ตัวอย่างล่าสุดจากเมนูด้านซ้าย
            </p>
          </section>
          <section className="panel">
            <p className="error-text">{error instanceof Error ? error.message : "ไม่สามารถโหลดข้อมูลกลุ่มเป้าหมายได้"}</p>
          </section>
        </div>
      </Shell>
    );
  }

  const defaultOption =
    diseaseOptions.find((option) => option.normalized_disease_key === "cervical_screen") ??
    diseaseOptions.find((option) => option.group_type === "service") ??
    diseaseOptions[0];
  const initialDiseaseKeys = defaultOption?.normalized_disease_key ? [defaultOption.normalized_disease_key] : ["hep_b_screen"];
  const [initialResults, initialSummary] = await Promise.all([
    getGroupResults(jobId, initialDiseaseKeys),
    getGroupedDiseaseSummary(jobId)
  ]);

  return (
    <Shell>
      <div className="stack-lg">
        <section className="hero stack-md">
          <p className="eyebrow">ผลลัพธ์กลุ่มเป้าหมาย</p>
          <h2>พื้นที่ทำงานของงาน #{jobId}</h2>
          <p className="muted">
            ตรวจผลการจับคู่ เลือกมุมมองกลุ่มโรคหรือบริการ คัดกรองช่วงเวลารับบริการ และส่งออกผลลัพธ์ได้จากหน้านี้
          </p>
        </section>
        <GroupResultsWorkspace
          job={job}
          diseaseOptions={diseaseOptions}
          initialDiseaseKeys={initialDiseaseKeys}
          initialResults={initialResults.results}
          initialSummary={initialSummary}
        />
      </div>
    </Shell>
  );
}
