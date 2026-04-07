import markdown
from weasyprint import HTML, CSS
import os

# 读取Markdown文件
with open('使用说明.md', 'r', encoding='utf-8') as f:
    md_content = f.read()

# 转换Markdown为HTML
html_content = markdown.markdown(md_content, extensions=['tables', 'fenced_code'])

# 完整的HTML模板
full_html = f'''
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>股票支撑位与压力位分析工具 - 使用说明</title>
    <style>
        body {{
            font-family: "Microsoft YaHei", "SimHei", sans-serif;
            line-height: 1.8;
            margin: 40px;
            color: #333;
        }}
        h1 {{
            color: #667eea;
            border-bottom: 3px solid #667eea;
            padding-bottom: 10px;
        }}
        h2 {{
            color: #764ba2;
            border-bottom: 2px solid #764ba2;
            padding-bottom: 8px;
            margin-top: 30px;
        }}
        h3 {{
            color: #667eea;
            margin-top: 25px;
        }}
        h4 {{
            color: #555;
            margin-top: 20px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }}
        th, td {{
            border: 1px solid #ddd;
            padding: 12px;
            text-align: left;
        }}
        th {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }}
        tr:nth-child(even) {{
            background-color: #f8f9fa;
        }}
        code {{
            background: #f0f0f0;
            padding: 2px 6px;
            border-radius: 4px;
        }}
        .page-break {{
            page-break-after: always;
        }}
    </style>
</head>
<body>
    {html_content}
</body>
</html>
'''

# 生成PDF
HTML(string=full_html).write_pdf('使用说明.pdf')
print('✅ PDF生成成功：使用说明.pdf')
