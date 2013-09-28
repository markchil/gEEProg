# -*- mode: python -*-
a = Analysis(['prog2801GuiWX.py'],
             pathex=['C:\\Documents and Settings\\Mark Chilenski\\My Documents\\2801Prog'],
             hiddenimports=[],
             hookspath=None)
pyz = PYZ(a.pure)
exe = EXE(pyz,
          a.scripts,
          a.binaries,
          a.zipfiles,
          a.datas,
          [('favicon.ico', 'favicon.ico', 'DATA')],
          name=os.path.join('dist', 'prog2801GuiWX.exe'),
          debug=False,
          strip=None,
          upx=True,
          console=False ,
          icon='favicon.ico')

# for use with pyInstaller 2.0
# run with:
# python ..\pyinstaller-2.0\utils\Build.py prog2801GuiWX_collect.spec
