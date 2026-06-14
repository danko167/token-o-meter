interface Props {
  className?: string;
}

export function BrandSignal({ className = '' }: Props) {
  return (
    <span className={`brandSignal ${className}`.trim()} aria-hidden="true">
      <span />
      <span />
      <span />
      <span />
      <span />
      <span />
    </span>
  );
}
