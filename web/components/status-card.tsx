type StatusCardProps = {
  label: string;
  value: string;
  tone?: "default" | "success" | "warning";
  helper?: string;
};

export function StatusCard({ label, value, tone = "default", helper }: StatusCardProps) {
  return (
    <section className={`panel tone-${tone}`}>
      <p className="panel-label">{label}</p>
      <h3>{value}</h3>
      {helper ? <p className="muted">{helper}</p> : null}
    </section>
  );
}
