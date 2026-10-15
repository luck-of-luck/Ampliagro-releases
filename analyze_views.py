with open('app/views/cadastro.py','r',encoding='utf-8') as f:
    lines = f.readlines()

# Find all function definitions and their render/POST patterns
views = []
current_view = None
current_start = 0
for i in range(len(lines)):
    line = lines[i].strip()
    if line.startswith('def cadastro_') and '(' in line:
        if current_view is not None:
            views.append((current_view, current_start, i))
        current_view = line.split('def ')[1].split('(')[0]
        current_start = i
if current_view is not None:
    views.append((current_view, current_start, len(lines)))

for (name, start, end) in views:
    block = ''.join(lines[start:end])
    post_idx = block.find('if request.method == "POST"')
    render_idx = block.find('return render(')
    last_render_idx = block.rfind('return render(')
    
    status = 'OK'
    if post_idx == -1:
        status = 'NO POST HANDLER'
    elif post_idx > last_render_idx:
        status = 'POST AFTER RENDER (BROKEN)'
    
    print(f'{name:30s}: {status}')