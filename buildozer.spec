[app]
title = ExtraTag
package.name = extratag
package.domain = com.extratag
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,html,js,css,json

version = 1.0.6

# תלויות מותאמות לבניית אנדרואיד עם תקשורת מוצפנת (HTTPS)
requirements = python3,kivy,openssl,requests,urllib3,certifi

orientation = portrait
android.permissions = INTERNET
android.archs = arm64-v8a
android.api = 33
android.minapi = 24

[buildozer]
log_level = 2
