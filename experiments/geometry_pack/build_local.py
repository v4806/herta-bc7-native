from pathlib import Path
import subprocess
root=Path(__file__).resolve().parent
vc=Path(r'D:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools\MSVC\14.50.35717\bin\Hostx64\x64')
command=[str(vc/'cl.exe'),'/nologo','/O2','/LD','/W4','/Zl','/GS-',str(root/'geometry_pack.c'),
         '/Fo'+str(root/'geometry_pack.obj'),'/Fe'+str(root/'herta_geometry_windows_x64.dll'),
         '/link','/NODEFAULTLIB','/NOENTRY','/IMPLIB:'+str(root/'geometry_pack.lib')]
p=subprocess.run(command,cwd=root,capture_output=True)
(root/'build.log').write_bytes(p.stdout+p.stderr)
print((p.stdout+p.stderr).decode(errors='replace'))
raise SystemExit(p.returncode)
