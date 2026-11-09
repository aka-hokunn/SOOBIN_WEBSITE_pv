import os

images_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "app", "static", "images")
os.makedirs(images_dir, exist_ok=True)

def create_svg(path, title, subtitle, bg_color1, bg_color2, accent):
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="600" height="750" viewBox="0 0 600 750">
  <defs>
    <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="{bg_color1}"/>
      <stop offset="100%" stop-color="{bg_color2}"/>
    </linearGradient>
    <filter id="shadow" x="-10%" y="-10%" width="120%" height="120%">
      <feDropShadow dx="0" dy="12" stdDeviation="16" flood-opacity="0.25"/>
    </filter>
  </defs>
  <rect width="600" height="750" fill="url(#bg)"/>
  
  <!-- Wave pattern -->
  <path d="M 0,550 Q 150,520 300,550 T 600,550 L 600,750 L 0,750 Z" fill="rgba(255,255,255,0.08)"/>
  <path d="M 0,600 Q 150,570 300,600 T 600,600 L 600,750 L 0,750 Z" fill="rgba(255,255,255,0.12)"/>

  <!-- Center Badge / Emblem -->
  <g transform="translate(300, 320)" filter="url(#shadow)">
    <circle cx="0" cy="0" r="110" fill="rgba(255,255,255,0.15)" stroke="rgba(255,255,255,0.3)" stroke-width="2"/>
    <path d="M -50,-20 C -25,-40 25,-40 50,-20 C 60,10 40,50 0,65 C -40,50 -60,10 -50,-20 Z" fill="{accent}" opacity="0.95"/>
    <circle cx="0" cy="-2" r="12" fill="#ffffff" opacity="0.9"/>
  </g>

  <!-- Typography -->
  <text x="300" y="490" font-family="'Plus Jakarta Sans', Arial, sans-serif" font-size="24" font-weight="800" fill="#ffffff" text-anchor="middle" letter-spacing="1">
    {title.upper()}
  </text>
  <text x="300" y="525" font-family="'Plus Jakarta Sans', Arial, sans-serif" font-size="14" font-weight="600" fill="rgba(255,255,255,0.8)" text-anchor="middle" letter-spacing="2">
    {subtitle.upper()}
  </text>
  <text x="300" y="700" font-family="'Plus Jakarta Sans', Arial, sans-serif" font-size="12" font-weight="700" fill="rgba(255,255,255,0.5)" text-anchor="middle" letter-spacing="3">
    SOOBIN SWIMWEAR • PREMIUM FABRIC
  </text>
</svg>"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(svg)

assets = [
    ("swim-w01-black.webp", "Áo Tắm Elegance Đen", "1 Mảnh Liền Thân", "#18181b", "#09090b", "#38bdf8"),
    ("swim-w01-navy.webp", "Áo Tắm Elegance Navy", "1 Mảnh Khoét Lưng", "#0f172a", "#1e3a8a", "#06b6d4"),
    ("swim-w02-coral.webp", "Bikini Coral Beach", "2 Mảnh Cạp Cao", "#fb7185", "#e11d48", "#fef08a"),
    ("swim-m01-black.webp", "Quần Bơi Speed Pro", "Thể Thao Nam", "#1e293b", "#0f172a", "#38bdf8"),
    ("swim-m02-cyan.webp", "Boxer Sóng Biển", "Boxer Nam Đi Biển", "#0e7490", "#0891b2", "#67e8f9"),
    ("swim-acc01.webp", "Kính Bơi Góc Rộng", "Chống Đọng Sương", "#0369a1", "#0284c7", "#38bdf8"),
    ("swim-acc02.webp", "Mũ Bơi Silicone", "Kháng Clo Cao Cấp", "#1d4ed8", "#2563eb", "#60a5fa"),
    ("placeholder.webp", "Soobin Swimwear", "BST Hè 2026", "#0f172a", "#0284c7", "#38bdf8")
]

for filename, title, sub, c1, c2, acc in assets:
    p = os.path.join(images_dir, filename)
    create_svg(p, title, sub, c1, c2, acc)

print("Generated all visual assets successfully!")
