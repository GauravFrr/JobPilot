import fitz

doc = fitz.open('f:/JobPilot/resume/resume.pdf')
page = doc[0]
print(f"Page size: {page.rect.width:.0f} x {page.rect.height:.0f} pts")

blocks = page.get_text('dict')
for b in blocks['blocks'][:8]:
    for line in b.get('lines', []):
        for span in line.get('spans', []):
            txt = span['text'][:60]
            font = span['font']
            size = span['size']
            color = hex(span['color'])
            print(f"Text: {txt[:55]:55s} | Font: {font:30s} | Size: {size:.1f} | Color: {color}")
