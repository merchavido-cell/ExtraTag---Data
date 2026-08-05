[app]
title = ExtraTag Phone
package.name = extratagphone
package.domain = org.extratag
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,html,css,js
source.include_patterns = Extratag_Email/*,Extratag_Vcall/*
version = 0.1
requirements = python3,kivy,pyjnius
orientation = portrait
osx.python_version = 3
osx.kivy_version = 1.9.1
fullscreen = 0
android.permissions = INTERNET
android.api = 33
android.minapi = 21
android.ndk_api = 21
android.ndk = 25b
android.accept_sdk_license = True
p4a.branch = release-2024.01.21

[buildozer]
log_level = 2
warn_on_root = 1
