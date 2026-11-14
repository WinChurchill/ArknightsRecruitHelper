"""打包时运行：把 exe 里包含的所有第三方组件的许可证全文收集成一个文件 THIRD_PARTY_LICENSES.txt。

用法（用打包用的 venv 运行）：.venv-build\\Scripts\\python tools\\collect_licenses.py build\\THIRD_PARTY_LICENSES.txt
"""
from __future__ import annotations

import glob
import importlib.metadata as md
import os
import sys
import urllib.request

# 只在打包时用、不进入 exe 的包
BUILD_ONLY = {"pip", "setuptools", "wheel", "pyinstaller", "pyinstaller-hooks-contrib", "altgraph", "pefile",
              "pywin32-ctypes", "packaging"}
# 包里没有附带许可证文件、但声明为 Apache-2.0 的组件
APACHE_URL = "https://www.apache.org/licenses/LICENSE-2.0.txt"
HOMEPAGES = {
    "rapidocr-onnxruntime": "https://github.com/RapidAI/RapidOCR",
    "flatbuffers": "https://github.com/google/flatbuffers",
}

HEADER = """THIRD-PARTY SOFTWARE LICENSES / 第三方软件许可
=================================================

Arknights Recruit Helper (明日方舟 公招助手) is MIT-licensed. The Windows executable bundles the
third-party components listed below; their copyright notices and full license texts follow.

OCR models: the bundled Chinese/English models and the optional Japanese/Korean models (downloaded on
first use) are PaddleOCR PP-OCR models (Apache-2.0, https://github.com/PaddlePaddle/PaddleOCR),
converted to ONNX and distributed by RapidOCR (Apache-2.0, https://github.com/RapidAI/RapidOCR).

pystray is licensed under the GNU LGPL v3. This program uses it unmodified as a separate Python module.
The complete source code of this program and its build script are public at
https://github.com/WinChurchill/ArknightsRecruitHelper, so you can rebuild the executable with a
modified or different version of pystray.

Game data (operator names, tags, recruitment pool) comes from ArknightsGameData and
ArknightsGameData_YoStar (https://github.com/Kengxxiao). Arknights and its data are (c) Hypergryph /
Yostar. This is an unofficial fan tool, not affiliated with Hypergryph or Yostar.
"""


def license_texts(dist):
    out = []
    for f in dist.files or []:
        name = os.path.basename(str(f)).upper()
        if any(k in name for k in ("LICENSE", "LICENCE", "COPYING", "NOTICE", "AUTHORS")) and not name.endswith((".PY", ".PYC")):
            try:
                out.append((str(f), dist.locate_file(f).read_text(encoding="utf-8", errors="replace")))
            except OSError:
                pass
    return out


def main(dest):
    parts = [HEADER]
    apache = None
    dists = sorted((d for d in md.distributions() if d.metadata["Name"].lower() not in BUILD_ONLY),
                   key=lambda d: d.metadata["Name"].lower())
    # 先列清单
    parts.append("\nCOMPONENTS\n----------")
    for d in dists:
        lic = d.metadata.get("License-Expression") or (d.metadata.get("License") or "").splitlines()[0:1]
        lic = lic if isinstance(lic, str) else (lic[0] if lic else "")
        cls = [c.split("::")[-1].strip() for c in (d.metadata.get_all("Classifier") or []) if c.startswith("License ::")]
        url = d.metadata.get("Home-page") or HOMEPAGES.get(d.metadata["Name"].lower(), "")
        if not url:
            for u in d.metadata.get_all("Project-URL") or []:
                url = u.split(",", 1)[-1].strip()
                break
        parts.append(f"- {d.metadata['Name']} {d.version}  [{(lic or '; '.join(cls))[:60]}]  {url}")
    parts.append("- Python " + sys.version.split()[0] + "  [PSF License]  https://www.python.org")
    parts.append("- Tcl/Tk  [Tcl/Tk License (BSD-style)]  https://www.tcl.tk")
    parts.append("- PyInstaller bootloader  [GPL-2.0 with bootloader exception]  https://pyinstaller.org")

    for d in dists:
        name = d.metadata["Name"]
        texts = license_texts(d)
        parts.append("\n" + "=" * 78 + f"\n{name} {d.version}\n" + "=" * 78)
        if texts:
            for fname, txt in texts:
                parts.append(f"--- {fname} ---\n{txt.strip()}\n")
        else:
            lic = (d.metadata.get("License-Expression") or d.metadata.get("License") or "")
            if "apache" in lic.lower() or any("Apache" in c for c in d.metadata.get_all("Classifier") or []):
                if apache is None:
                    apache = urllib.request.urlopen(APACHE_URL, timeout=60).read().decode("utf-8")
                parts.append(f"(No license file shipped in the package; it is licensed under Apache-2.0.)\n\n{apache.strip()}\n")
            else:
                parts.append(f"License: {lic or 'see project page'}\n")

    # Python / Tcl/Tk / PyInstaller
    extra = [("Python", os.path.join(sys.base_prefix, "LICENSE.txt"))]
    extra += [("Tcl/Tk", p) for p in glob.glob(os.path.join(sys.base_prefix, "tcl", "*", "license.terms"))[:1]]
    import PyInstaller
    for p in glob.glob(os.path.join(os.path.dirname(PyInstaller.__file__), "..", "pyinstaller-*.dist-info", "licenses", "*")):
        extra.append(("PyInstaller", p))
    for title, path in extra:
        try:
            txt = open(path, encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        parts.append("\n" + "=" * 78 + f"\n{title}\n" + "=" * 78 + f"\n{txt.strip()}\n")

    os.makedirs(os.path.dirname(os.path.abspath(dest)), exist_ok=True)
    with open(dest, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(parts))
    print(f"wrote {dest}: {len(dists)} packages")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join("build", "THIRD_PARTY_LICENSES.txt"))
