import type { TargetGroupPreviewRow } from "@/types/target-group";
import { getPreviewRowKey } from "./keys";

export function TargetGroupPreviewTable({ rows }: { rows: TargetGroupPreviewRow[] }) {
  if (!rows.length) {
    return <p className="summary-copy">ยังไม่มีข้อมูลตัวอย่าง</p>;
  }

  const columns = Object.keys(rows[0].values);
  return (
    <div className="table-wrap">
      <table className="data-table">
        <thead>
          <tr>
            <th>แถว</th>
            {columns.slice(0, 5).map((column) => (
              <th key={column}>{column}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={getPreviewRowKey(row)}>
              <td>{row.row_no}</td>
              {columns.slice(0, 5).map((column) => (
                <td key={column}>{String(row.values[column] ?? "-")}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
