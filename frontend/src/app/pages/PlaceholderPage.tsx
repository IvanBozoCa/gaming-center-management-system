interface PlaceholderPageProps {
  title: string;
  description: string;
}

export function PlaceholderPage({
  title,
  description,
}: PlaceholderPageProps) {
  return (
    <section className="page">
      <p className="eyebrow">
        GCMS Admin
      </p>

      <h1>{title}</h1>

      <p>{description}</p>
    </section>
  );
}