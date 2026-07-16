import resvg_py

svg = "<svg xmlns='http://www.w3.org/2000/svg' width='400' height='300'><rect x='10' y='10' width='180' height='130' fill='none' stroke='black' stroke-width='3'/></svg>"
png_bytes = resvg_py.svg_to_bytes(svg_string=svg, width=800)
print("type:", type(png_bytes))
print("length:", len(png_bytes))
print("PNG header:", png_bytes[:4] == b"\x89PNG")
