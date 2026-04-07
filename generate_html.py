import markdown

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
            margin: 40px auto;
            max-width: 900px;
            color: #333;
            background: #f5f5f5;
            padding: 40px;
        }}
        .container {{
            background: white;
            padding: 40px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        h1 {{
            color: #667eea;
            border-bottom: 3px solid #667eea;
            padding-bottom: 10px;
            margin-bottom: 30px;
        }}
        h2 {{
            color: #764ba2;
            border-bottom: 2px solid #764ba2;
            padding-bottom: 8px;
            margin-top: 35px;
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
        .print-btn {{
            position: fixed;
            top: 20px;
            right: 20px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            padding: 15px 30px;
            font-size: 16px;
            border-radius: 8px;
            cursor: pointer;
            box-shadow: 0 4px 10px rgba(0,0,0,0.2);
        }}
        .print-btn:hover {{
            transform: translateY(-2px);
            box-shadow: 0 6px 15px rgba(0,0,0,0.3);
        }}
        @media print {{
            .print-btn {{
                display: none;
            }}
            body {{
                background: white;
                padding: 0;
                margin: 0;
            }}
            .container {{
                box-shadow: none;
                padding: 20px;
            }}
        }}
    </style>
</head>
<body>
    <button class="print-btn" onclick="window.print()">🖨️ 打印 / 保存为PDF</button>
    <div class="container">
        {html_content}
    </div>
</body>
</html>
'''

# 保存HTML文件
with open('使用说明.html', 'w', encoding='utf-8') as f:
    f.write(full_html)

print('✅ HTML文件生成成功：使用说明.html')
print('请在浏览器中打开此文件，然后点击右上角"打印 / 保存为PDF"按钮')
