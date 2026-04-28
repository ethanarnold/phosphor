type BrandMarkProps = {
  size?: 'sidebar' | 'full'
  showWord?: boolean
}

export default function BrandMark({ size = 'sidebar', showWord = true }: BrandMarkProps) {
  const isFull = size === 'full'
  return (
    <div className={`brandmark brandmark-${size}`} aria-label="Phosphor">
      <div className="brandmark-card" aria-hidden="true">
        {isFull && <span className="brandmark-num">15</span>}
        <span className="brandmark-glyph">P</span>
        {isFull && <span className="brandmark-mass">30.97</span>}
      </div>
      {showWord && <span className="brandmark-word">Phosphor</span>}
    </div>
  )
}
