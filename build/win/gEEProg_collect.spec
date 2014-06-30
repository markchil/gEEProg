# -*- mode: python -*-
a = Analysis(['..\\..\\src\\gEEProg_GUI_TK.py'],
             pathex=['C:\\Documents and Settings\\Administrator\\My Documents\\gEEProg\src'],
             hiddenimports=[],
             hookspath=None)
pyz = PYZ(a.pure)
exe = EXE(pyz,
          a.scripts,
          a.binaries,
          a.zipfiles,
          a.datas,
          [('graphics\\Icon.gif', '..\\..\\graphics\\Icon.gif', 'DATA')],
          name=os.path.join('dist', 'gEEProg.exe'),
          debug=False,
          strip=None,
          upx=True,
          console=False ,
          icon='..\\..\\graphics\\Icon.ico')

# for use with pyInstaller 2.0
# run with:
# python ..\pyinstaller-2.0\utils\Build.py gEEProg_collect.spec
