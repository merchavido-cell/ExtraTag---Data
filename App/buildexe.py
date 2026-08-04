import subprocess

command = [
    "pyinstaller",
    "--noconfirm",
    "--onedir",
    "--windowed",
    "--collect-all", "win32com",
    "--collect-all", "winshell",
    "--collect-all", "certifi",
    "--collect-all", "requests",
    "--add-data", "legendsecret093.env;.",
    "--add-data", "Extratag - Apps;Extratag - Apps",
    "--add-data", "Extratag - CodeX;Extratag - CodeX",
    "--add-data", "Extratag - Email;Extratag - Email",
    "--add-data", "Extratag - Profile;Extratag - Profile",
    "--add-data", "Extratag - Setting;Extratag - Setting",
    "--add-data", "Extratag - Storage;Extratag - Storage",
    "--add-data", "Extratag - Vcall;Extratag - Vcall",
    "main.py"
]

subprocess.run(command)