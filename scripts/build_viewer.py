"""One portable, data-free dashboard HTML; same renderer as the live report UI."""
from pathlib import Path
import base64,re
BASE=Path(__file__).resolve().parents[1]

def build():
    html=(BASE/'static/dashboard.html').read_text().replace('<body>','<body data-mode="portable">')
    def css(match):
        text=(BASE/'static'/match.group(1)).read_text()
        for font in (BASE/'static/fonts').glob('*.woff2'):
            text=text.replace('/static/fonts/'+font.name,'data:font/woff2;base64,'+base64.b64encode(font.read_bytes()).decode())
        return '<style>'+text+'</style>'
    html=re.sub(r'<link\s+rel="stylesheet"\s+href="/static/([^"]+)"\s*/?>',css,html)
    scripts=[]
    def inline(m):
        scripts.append('<script>'+(BASE/'static'/m.group(1)).read_text()+'</script>');return ''
    html=re.sub(r'<script\s+src="/static/([^"]+)"\s+defer>\s*</script>',inline,html)
    html=html.replace('</body>',''.join(scripts)+'</body>')
    # Prints from a file-only viewer must not rely on /static/print.css.
    print_css=(BASE/'static/print.css').read_text()
    html=html.replace('<link rel="stylesheet" href="/static/print.css">','<style>'+print_css+'</style>')
    target=BASE/'docs/viewer/index.html';target.parent.mkdir(exist_ok=True,parents=True);target.write_text('\n'.join(line.rstrip() for line in html.splitlines())+'\n')
    return target
if __name__=='__main__':print(build())
