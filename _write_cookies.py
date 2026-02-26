import json
d = json.loads(open(r'C:\Users\Michael\.notebooklm-mcp\auth.json', encoding='utf-8').read())
cookies = d['cookies']
cookie_str = '; '.join(f'{k}={v}' for k,v in cookies.items())
open(r'C:\PROJECTS\notebooklm-mcp\cookies.txt', 'w', encoding='utf-8').write(cookie_str)
print(f'Written {len(cookie_str)} chars to cookies.txt')
sid_keys = [k for k in cookies if 'SID' in k]
print('SID keys:', sid_keys)
