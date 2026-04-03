export default function PageHeader({ breadcrumb, title, subtitle }) {
  return (
    <div className="mb-6">
      {breadcrumb && (
        <p className="text-[#555] text-xs uppercase tracking-widest mb-1">{breadcrumb}</p>
      )}
      <h1 className="text-white text-2xl font-bold">{title}</h1>
      {subtitle && (
        <p className="text-[#555] text-sm mt-1">{subtitle}</p>
      )}
    </div>
  );
}
