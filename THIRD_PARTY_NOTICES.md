# Third-party notices / 第三方声明

Arknights Recruit Helper is [MIT-licensed](LICENSE). It builds on the work below — thank you!
The full license texts of everything bundled in the Windows exe are in `THIRD_PARTY_LICENSES.txt`,
which ships inside the exe (Settings → 第三方许可 / Third-party licenses) and is attached to every
[release](../../releases/latest).

本项目基于以下开源项目和公开数据，感谢它们的作者。exe 内含的全部第三方许可证全文见
`THIRD_PARTY_LICENSES.txt`（程序内：设置 →「第三方许可」；每个 Release 也附带该文件）。

## Data / 数据

| Source | Used for | Notes |
|---|---|---|
| [ArknightsGameData](https://github.com/Kengxxiao/ArknightsGameData) | CN recruitment pool, tags, operators | Arknights data © Hypergryph |
| [ArknightsGameData_YoStar](https://github.com/Kengxxiao/ArknightsGameData_YoStar) | Global / JP / KR recruitment pool, tags, operators | Arknights data © Hypergryph / Yostar |

Recruitment rules (9-hour guarantees, Top/Senior Operator, Robot at 3:50) are game mechanics; the combo
calculation code is original. 公招规则来自游戏机制，组合计算代码为本项目原创。

## OCR / 文字识别

| Component | Used for | License |
|---|---|---|
| [RapidOCR](https://github.com/RapidAI/RapidOCR) (`rapidocr-onnxruntime`) | OCR engine | Apache-2.0 |
| [PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR) PP-OCR models | text detection / recognition (bundled zh/en; JP/KR downloaded on first use from RapidOCR's [ModelScope repo](https://www.modelscope.cn/models/RapidAI/RapidOCR)) | Apache-2.0 |
| [ONNX Runtime](https://onnxruntime.ai) | model inference | MIT |
| [OpenCV](https://opencv.org) (`opencv-python-headless`) | image processing | Apache-2.0 |

## Runtime libraries / 运行库

| Component | License |
|---|---|
| [pystray](https://github.com/moses-palmer/pystray) | **LGPL-3.0** — used unmodified as a separate module; the full source and build script of this program are public, so the exe can be rebuilt with a modified pystray |
| [Pillow](https://python-pillow.org) | MIT-CMU |
| [NumPy](https://numpy.org) | BSD-3-Clause (and bundled components' licenses) |
| [python-mss](https://github.com/BoboTiG/python-mss) | MIT |
| [keyboard](https://github.com/boppreh/keyboard) | MIT |
| [PyYAML](https://pyyaml.org), [six](https://github.com/benjaminp/six), [pyclipper](https://github.com/fonttools/pyclipper) | MIT |
| [Shapely](https://shapely.readthedocs.io), [protobuf](https://protobuf.dev), [colorama](https://github.com/tartley/colorama) | BSD |
| [FlatBuffers](https://github.com/google/flatbuffers) | Apache-2.0 |
| [tqdm](https://tqdm.github.io) | MPL-2.0 AND MIT |
| [Python](https://www.python.org) | PSF License |
| Tcl/Tk | BSD-style Tcl/Tk license |
| [PyInstaller](https://pyinstaller.org) bootloader | GPL-2.0 with bootloader exception (permits distributing the built exe under any license) |

## Not bundled / 未打包

- Fonts (Microsoft YaHei, Yu Gothic, Malgun Gothic, Bahnschrift) are read from your Windows installation; none are redistributed.
  字体直接使用系统自带字体，不随程序分发。
- The promo video's background music, if any, is chosen and credited by the uploader.
  宣传视频的背景音乐由上传者自行选择并署名。

## Trademarks / 商标

Arknights / 明日方舟 and related names, images and data are the property of Hypergryph and Yostar.
This is an unofficial fan-made tool and is not affiliated with or endorsed by them.
「明日方舟」及相关名称、图片、数据归鹰角网络、悠星所有。本项目为非官方玩家工具，与上述公司无关。
